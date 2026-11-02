class ReporteModel:
    """Consultas de reportes. Cada reporte devuelve (columnas, filas) listos para tabla/exportación."""

    def __init__(self, db):
        self.db = db
        self.reports = {
            "Ventas por día": self.sales_by_day,
            "Ventas por producto": self.sales_by_product,
            "Ventas por vendedor": self.sales_by_seller,
            "Productos por vencer (90 días)": self.expiring,
            "Kardex por producto y lote": self.kardex,
            "Desviaciones FEFO": self.fefo,
            "Cierres de caja": self.cash_closings,
            "Libro de controlados": self.controlled_book,
        }

    def _run(self, sql, params=(), headers=None):
        with self.db.cursor(dictionary=False) as (_, c):
            c.execute(sql, params)
            rows = c.fetchall()
            return headers or [d[0] for d in c.description], [[("" if v is None else v) for v in r] for r in rows]

    def sales_by_day(self, desde, hasta):
        return self._run("""SELECT DATE(fecha),COUNT(*),SUM(subtotal),SUM(descuento),SUM(total) FROM ventas
            WHERE estado='Completada' AND DATE(fecha) BETWEEN %s AND %s GROUP BY DATE(fecha) ORDER BY 1""", (desde, hasta),
            ["Fecha", "Ventas", "Subtotal", "Descuento", "Total"])

    def sales_by_product(self, desde, hasta):
        return self._run("""SELECT p.codigo,p.nombre_comercial,SUM(dv.cantidad),SUM(dv.subtotal),SUM(dv.subtotal-dv.cantidad*l.precio_compra)
            FROM detalle_venta dv JOIN ventas v ON v.id=dv.venta_id JOIN productos p ON p.id=dv.producto_id JOIN lotes l ON l.id=dv.lote_id
            WHERE v.estado='Completada' AND DATE(v.fecha) BETWEEN %s AND %s GROUP BY p.id ORDER BY 4 DESC""", (desde, hasta),
            ["Código", "Producto", "Unidades", "Ventas", "Margen"])

    def sales_by_seller(self, desde, hasta):
        return self._run("""SELECT u.nombre,COUNT(*),SUM(v.total) FROM ventas v JOIN usuarios u ON u.id=v.usuario_id
            WHERE v.estado='Completada' AND DATE(v.fecha) BETWEEN %s AND %s GROUP BY u.id ORDER BY 3 DESC""", (desde, hasta),
            ["Vendedor", "Ventas", "Total"])

    def expiring(self, desde=None, hasta=None):
        return self._run("""SELECT p.codigo,p.nombre_comercial,l.numero_lote,l.fecha_vencimiento,l.cantidad_actual,DATEDIFF(l.fecha_vencimiento,CURDATE())
            FROM lotes l JOIN productos p ON p.id=l.producto_id WHERE l.cantidad_actual>0 AND l.fecha_vencimiento<=DATE_ADD(CURDATE(),INTERVAL 90 DAY)
            ORDER BY l.fecha_vencimiento""", (), ["Código", "Producto", "Lote", "Vence", "Cantidad", "Días"])

    def kardex(self, desde, hasta):
        return self._run("""SELECT mi.fecha,p.nombre_comercial,COALESCE(l.numero_lote,'—'),mi.tipo_movimiento,mi.cantidad,mi.motivo,u.nombre
            FROM movimientos_inventario mi JOIN productos p ON p.id=mi.producto_id LEFT JOIN lotes l ON l.id=mi.lote_id JOIN usuarios u ON u.id=mi.usuario_id
            WHERE DATE(mi.fecha) BETWEEN %s AND %s ORDER BY p.nombre_comercial,l.numero_lote,mi.id""", (desde, hasta),
            ["Fecha", "Producto", "Lote", "Movimiento", "Cantidad", "Motivo", "Usuario"])

    def fefo(self, desde, hasta):
        return self._run("""SELECT d.fecha,d.venta_id,u.nombre,p.nombre_comercial,ls.numero_lote,lv.numero_lote,COALESCE(d.motivo,'—')
            FROM desviaciones_fefo d JOIN usuarios u ON u.id=d.usuario_id JOIN lotes ls ON ls.id=d.lote_sugerido_id
            JOIN lotes lv ON lv.id=d.lote_vendido_id JOIN productos p ON p.id=lv.producto_id
            WHERE DATE(d.fecha) BETWEEN %s AND %s ORDER BY d.id DESC""", (desde, hasta),
            ["Fecha", "Venta", "Usuario", "Producto", "Lote sugerido", "Lote vendido", "Motivo"])

    def cash_closings(self, desde, hasta):
        return self._run("""SELECT t.id,u.nombre,t.apertura,t.cierre,t.monto_inicial,t.efectivo_esperado,t.efectivo_contado,t.diferencia
            FROM turnos_caja t JOIN usuarios u ON u.id=t.usuario_id WHERE t.estado='Cerrado' AND DATE(t.apertura) BETWEEN %s AND %s ORDER BY t.id DESC""",
            (desde, hasta), ["Turno", "Cajero", "Apertura", "Cierre", "Inicial", "Esperado", "Contado", "Diferencia"])

    def controlled_book(self, desde, hasta):
        return self._run("""SELECT lc.fecha,p.nombre_comercial,pa.nombre,l.numero_lote,lc.cantidad,lc.paciente_nombre,COALESCE(lc.paciente_documento,''),
            lc.medico_nombre,COALESCE(lc.medico_codigo,''),lc.numero_receta,u.nombre
            FROM libro_controlados lc JOIN productos p ON p.id=lc.producto_id JOIN principios_activos pa ON pa.id=p.principio_activo_id
            JOIN lotes l ON l.id=lc.lote_id JOIN usuarios u ON u.id=lc.usuario_id WHERE DATE(lc.fecha) BETWEEN %s AND %s ORDER BY lc.id""", (desde, hasta),
            ["Fecha", "Producto", "Principio activo", "Lote", "Cantidad", "Paciente", "Documento", "Médico", "Cód. médico", "Receta", "Despachó"])
