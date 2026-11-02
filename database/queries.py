DASHBOARD_STATS = """
SELECT
 (SELECT COUNT(*) FROM productos WHERE estado='Activo') total_productos,
 (SELECT COALESCE(SUM(cantidad_actual),0) FROM lotes WHERE estado='Disponible' AND fecha_vencimiento >= CURDATE()) unidades_disponibles,
 (SELECT COUNT(*) FROM productos p WHERE p.estado='Activo' AND p.stock_minimo > 0 AND COALESCE((SELECT SUM(l.cantidad_actual) FROM lotes l WHERE l.producto_id=p.id AND l.estado='Disponible' AND l.fecha_vencimiento >= CURDATE()),0) <= p.stock_minimo) stock_bajo,
 (SELECT COUNT(*) FROM lotes WHERE fecha_vencimiento < CURDATE() AND cantidad_actual > 0) vencidos,
 (SELECT COUNT(*) FROM lotes WHERE estado='Disponible' AND fecha_vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 90 DAY) AND cantidad_actual > 0) por_vencer,
 (SELECT COALESCE(SUM(total),0) FROM ventas WHERE estado='Completada' AND DATE(fecha)=CURDATE()) ventas_dia
"""

PRODUCT_LIST = """
SELECT p.id, p.codigo, p.codigo_barras, p.nombre_comercial, p.concentracion,
       p.unidad_concentracion, p.forma_farmaceutica, p.presentacion,
       COALESCE(pa.nombre,'Sin principio activo') principio_activo,
       COALESCE(m.nombre,'Sin marca') marca,
       COALESCE(c.nombre,'Sin categoría') categoria,
       p.precio_venta, p.stock_minimo, p.estado,
       COALESCE(SUM(CASE WHEN l.estado='Disponible' AND l.fecha_vencimiento >= CURDATE() THEN l.cantidad_actual ELSE 0 END),0) stock,
       MIN(CASE WHEN l.estado='Disponible' AND l.cantidad_actual > 0 THEN l.fecha_vencimiento END) proximo_vencimiento
FROM productos p
LEFT JOIN principios_activos pa ON pa.id=p.principio_activo_id
LEFT JOIN marcas m ON m.id=p.marca_id
LEFT JOIN categorias c ON c.id=p.categoria_id
LEFT JOIN lotes l ON l.producto_id=p.id
WHERE (%s='' OR p.codigo LIKE CONCAT('%',%s,'%')
       OR p.codigo_barras LIKE CONCAT('%',%s,'%')
       OR p.nombre_comercial LIKE CONCAT('%',%s,'%')
       OR pa.nombre LIKE CONCAT('%',%s,'%')
       OR m.nombre LIKE CONCAT('%',%s,'%')
       OR EXISTS (SELECT 1 FROM nombres_alternativos na WHERE na.producto_id=p.id AND na.nombre LIKE CONCAT('%',%s,'%')))
GROUP BY p.id, p.codigo, p.codigo_barras, p.nombre_comercial, p.concentracion,
         p.unidad_concentracion, p.forma_farmaceutica, p.presentacion,
         pa.nombre, m.nombre, c.nombre, p.precio_venta, p.stock_minimo, p.estado
HAVING (%s='Todos'
 OR (%s='Stock bajo' AND stock > 0 AND stock <= p.stock_minimo)
 OR (%s='Sin stock' AND stock=0)
 OR (%s='Próximos a vencer' AND proximo_vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(),INTERVAL 90 DAY))
 OR (%s='Vencidos' AND EXISTS (SELECT 1 FROM lotes lx WHERE lx.producto_id=p.id AND lx.cantidad_actual>0 AND lx.fecha_vencimiento<CURDATE()))
 OR (%s='Activos' AND p.estado='Activo'))
ORDER BY p.nombre_comercial
"""

CATEGORY_LIST = "SELECT id,nombre,descripcion,estado FROM categorias WHERE (%s='' OR nombre LIKE CONCAT('%',%s,'%')) ORDER BY nombre"
PROVIDER_LIST = "SELECT id,nombre,telefono,correo,direccion,estado FROM proveedores WHERE (%s='' OR nombre LIKE CONCAT('%',%s,'%')) ORDER BY nombre"
USER_LIST = "SELECT id,nombre,usuario,rol,estado,fecha_creacion FROM usuarios ORDER BY id DESC"
SALE_LIST = """
SELECT v.id,v.fecha,u.nombre usuario,v.subtotal,v.descuento,v.total,v.estado
FROM ventas v INNER JOIN usuarios u ON u.id=v.usuario_id ORDER BY v.id DESC LIMIT 100
"""
SALE_DETAIL = """
SELECT dv.id,p.codigo,p.nombre_comercial,dv.lote_id,l.numero_lote,dv.cantidad,dv.precio_unitario,dv.subtotal
FROM detalle_venta dv INNER JOIN productos p ON p.id=dv.producto_id
LEFT JOIN lotes l ON l.id=dv.lote_id WHERE dv.venta_id=%s ORDER BY dv.id
"""

# ---------------------------------------------------------------------------
# Pantalla de ventas
# ---------------------------------------------------------------------------
# Condición de "lote vendible": disponible, con unidades y no vencido.
_LOTE_VENDIBLE = (
    "l.estado='Disponible' AND l.cantidad_actual>0 AND l.fecha_vencimiento>=CURDATE()"
)

SALE_PRODUCT_SEARCH_TEMPLATE = f"""
SELECT p.id, p.codigo, p.codigo_barras, p.nombre_comercial, p.concentracion,
       p.unidad_concentracion, p.forma_farmaceutica, p.presentacion,
       p.precio_venta, p.requiere_receta, p.control_especial,
       COALESCE(pa.nombre,'') principio_activo,
       COALESCE(m.nombre,'') marca,
       COALESCE(m.laboratorio,'') laboratorio,
       COALESCE((SELECT SUM(l.cantidad_actual) FROM lotes l
                 WHERE l.producto_id=p.id AND {_LOTE_VENDIBLE}),0) stock,
       (SELECT l.numero_lote FROM lotes l WHERE l.producto_id=p.id AND {_LOTE_VENDIBLE}
        ORDER BY l.fecha_vencimiento, l.id LIMIT 1) lote_sugerido,
       (SELECT l.fecha_vencimiento FROM lotes l WHERE l.producto_id=p.id AND {_LOTE_VENDIBLE}
        ORDER BY l.fecha_vencimiento, l.id LIMIT 1) vence
FROM productos p
LEFT JOIN principios_activos pa ON pa.id=p.principio_activo_id
LEFT JOIN marcas m ON m.id=p.marca_id
WHERE p.estado='Activo'
  {{where}}
ORDER BY p.nombre_comercial
LIMIT %s
"""

# Una palabra buscada: debe aparecer en alguno de estos campos.
SALE_SEARCH_TOKEN = """(p.codigo LIKE %s OR p.codigo_barras LIKE %s
       OR p.nombre_comercial LIKE %s OR CAST(p.concentracion AS CHAR) LIKE %s
       OR pa.nombre LIKE %s OR m.nombre LIKE %s
       OR EXISTS (SELECT 1 FROM nombres_alternativos n
                  WHERE n.producto_id=p.id AND n.nombre LIKE %s))"""
SALE_SEARCH_TOKEN_PARAMS = 7

SALE_PRODUCT_EXACT = "SELECT id FROM productos WHERE estado='Activo' AND (codigo=%s OR codigo_barras=%s) LIMIT 1"

SALE_VALID_LOTS = f"""
SELECT l.id, l.numero_lote, l.fecha_vencimiento, l.cantidad_actual
FROM lotes l
WHERE l.producto_id=%s AND {_LOTE_VENDIBLE}
ORDER BY l.fecha_vencimiento, l.id
"""

SALE_HEADER = """
SELECT v.id, v.fecha, v.subtotal, v.descuento, v.total, v.estado,
       v.metodo_pago, v.monto_recibido, v.motivo_anulacion, v.fecha_anulacion,
       u.nombre usuario, ua.nombre anulada_por
FROM ventas v
INNER JOIN usuarios u ON u.id=v.usuario_id
LEFT JOIN usuarios ua ON ua.id=v.anulada_por
WHERE v.id=%s
"""

SALE_HISTORY = """
SELECT v.id, v.fecha, u.nombre usuario, v.total, v.estado, v.metodo_pago
FROM ventas v INNER JOIN usuarios u ON u.id=v.usuario_id
WHERE (%s=0 OR DATE(v.fecha)=CURDATE())
ORDER BY v.id DESC LIMIT %s
"""
