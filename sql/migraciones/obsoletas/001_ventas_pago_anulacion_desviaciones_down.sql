-- Deshace la migración 001 (borra los datos de pago/anulación/desviaciones/recetas).
USE farmastock;
DROP TABLE IF EXISTS recetas_venta;
DROP TABLE IF EXISTS desviaciones_fefo;
ALTER TABLE ventas
    DROP FOREIGN KEY fk_ventas_anulada_por,
    DROP COLUMN motivo_anulacion,
    DROP COLUMN fecha_anulacion,
    DROP COLUMN anulada_por,
    DROP COLUMN monto_recibido,
    DROP COLUMN metodo_pago;
