DROP TABLE IF EXISTS notas_credito;
DROP TABLE IF EXISTS abonos_cliente;
ALTER TABLE ventas
    DROP FOREIGN KEY fk_ventas_turno,
    DROP FOREIGN KEY fk_ventas_cliente;
ALTER TABLE ventas
    DROP COLUMN motivo_anulacion, DROP COLUMN anulada_por, DROP COLUMN numero_factura,
    DROP COLUMN metodo_pago, DROP COLUMN turno_id, DROP COLUMN cliente_id;
DROP TABLE IF EXISTS turnos_caja;
DROP TABLE IF EXISTS clientes;
