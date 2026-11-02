USE farmastock;

-- Corrección para una base FarmaStock ya existente.
-- Inserta los lotes de demostración que falten, sin duplicarlos.

INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT p.id,'PAR-A01',DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 5 MONTH),12,12,2.30,pr.id,CURDATE(),'Disponible','Estante A-01'
FROM productos p JOIN proveedores pr ON pr.nombre='Distribuidora Salud S.A.'
WHERE p.codigo='FAR-001' AND NOT EXISTS (SELECT 1 FROM lotes l WHERE l.producto_id=p.id AND l.numero_lote='PAR-A01');

INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT p.id,'PAR-B02',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 18 MONTH),30,30,2.50,pr.id,CURDATE(),'Disponible','Estante A-01'
FROM productos p JOIN proveedores pr ON pr.nombre='Farmacéutica Central'
WHERE p.codigo='FAR-001' AND NOT EXISTS (SELECT 1 FROM lotes l WHERE l.producto_id=p.id AND l.numero_lote='PAR-B02');

INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT p.id,'IBU-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 10 MONTH),8,8,3.20,pr.id,CURDATE(),'Disponible','Estante A-02'
FROM productos p JOIN proveedores pr ON pr.nombre='Farmacéutica Central'
WHERE p.codigo='FAR-002' AND NOT EXISTS (SELECT 1 FROM lotes l WHERE l.producto_id=p.id AND l.numero_lote='IBU-A01');

INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT p.id,CONCAT(p.codigo,'-A01'),DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 18 MONTH),20,20,4.00,pr.id,CURDATE(),'Disponible','Almacén general'
FROM productos p JOIN proveedores pr ON pr.nombre='Distribuidora Salud S.A.'
WHERE NOT EXISTS (SELECT 1 FROM lotes l WHERE l.producto_id=p.id);

INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id)
SELECT l.producto_id,l.id,'Entrada',l.cantidad_inicial,'Carga de corrección de lotes','ACTUALIZAR_LOTES_V2',1
FROM lotes l
WHERE l.numero_lote LIKE CONCAT(l.producto_id,'-A01')
  AND NOT EXISTS (SELECT 1 FROM movimientos_inventario m WHERE m.lote_id=l.id AND m.referencia='ACTUALIZAR_LOTES_V2');
