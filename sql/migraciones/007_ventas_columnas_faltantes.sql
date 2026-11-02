-- 007: migración CORRECTIVA e idempotente. Agrega lo que el código de ventas necesita
-- y que no existía en bases creadas con las migraciones 001-006 (la antigua 001_ventas
-- nunca se aplicó). No borra ni modifica datos existentes; se puede repetir sin riesgo.

-- Importe recibido y fecha de anulación en ventas
-- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ventas' AND column_name='monto_recibido'
ALTER TABLE ventas ADD COLUMN monto_recibido DECIMAL(12,2) NULL AFTER metodo_pago;

-- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ventas' AND column_name='fecha_anulacion'
ALTER TABLE ventas ADD COLUMN fecha_anulacion DATETIME NULL AFTER anulada_por;

-- @skip_if: SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='ventas' AND constraint_name='fk_ventas_anulada_por'
ALTER TABLE ventas ADD CONSTRAINT fk_ventas_anulada_por FOREIGN KEY (anulada_por) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- Desviaciones FEFO: el producto afectado (se rellena desde el lote vendido)
-- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='desviaciones_fefo' AND column_name='producto_id'
ALTER TABLE desviaciones_fefo ADD COLUMN producto_id INT NULL AFTER usuario_id;

UPDATE desviaciones_fefo d JOIN lotes l ON l.id = d.lote_vendido_id SET d.producto_id = l.producto_id WHERE d.producto_id IS NULL;

ALTER TABLE desviaciones_fefo MODIFY producto_id INT NOT NULL;

-- @skip_if: SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='desviaciones_fefo' AND constraint_name='fk_desv_producto'
ALTER TABLE desviaciones_fefo ADD CONSTRAINT fk_desv_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- Datos de receta por línea vendida
CREATE TABLE IF NOT EXISTS recetas_venta (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    paciente VARCHAR(160) NOT NULL,
    medico VARCHAR(160) NOT NULL,
    numero_receta VARCHAR(60) NOT NULL,
    CONSTRAINT pk_recetas_venta PRIMARY KEY (id),
    CONSTRAINT fk_receta_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_receta_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_recetas_venta (venta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
