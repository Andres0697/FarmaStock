-- Migración 001: pago, anulación, desviaciones FEFO y recetas.
-- Solo AGREGA columnas (con valor por defecto) y tablas. No borra nada.
-- Ejecutar sobre la base `farmastock`. Para deshacer: 001_ventas_..._down.sql
USE farmastock;

-- 1) Datos de pago y anulación en ventas
ALTER TABLE ventas
    ADD COLUMN metodo_pago ENUM('Efectivo','Tarjeta','Transferencia')
        NOT NULL DEFAULT 'Efectivo' AFTER total,
    ADD COLUMN monto_recibido DECIMAL(12,2) NULL AFTER metodo_pago,
    ADD COLUMN anulada_por INT NULL,
    ADD COLUMN fecha_anulacion DATETIME NULL,
    ADD COLUMN motivo_anulacion VARCHAR(255) NULL,
    ADD CONSTRAINT fk_ventas_anulada_por
        FOREIGN KEY (anulada_por) REFERENCES usuarios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- 2) Cuando el vendedor toma un lote distinto al sugerido por FEFO
CREATE TABLE desviaciones_fefo (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    usuario_id INT NOT NULL,
    producto_id INT NOT NULL,
    lote_sugerido_id INT NOT NULL,
    lote_vendido_id INT NOT NULL,
    motivo VARCHAR(255) NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_desviaciones_fefo PRIMARY KEY (id),
    CONSTRAINT fk_desv_venta FOREIGN KEY (venta_id) REFERENCES ventas(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_lote_sugerido FOREIGN KEY (lote_sugerido_id) REFERENCES lotes(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_lote_vendido FOREIGN KEY (lote_vendido_id) REFERENCES lotes(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX idx_desviaciones_fecha ON desviaciones_fefo (fecha);
CREATE INDEX idx_desviaciones_usuario ON desviaciones_fefo (usuario_id);

-- 3) Datos de receta para productos con receta retenida o control especial
CREATE TABLE recetas_venta (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    paciente VARCHAR(160) NOT NULL,
    medico VARCHAR(160) NOT NULL,
    numero_receta VARCHAR(60) NOT NULL,
    CONSTRAINT pk_recetas_venta PRIMARY KEY (id),
    CONSTRAINT fk_receta_venta FOREIGN KEY (venta_id) REFERENCES ventas(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_receta_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX idx_recetas_venta ON recetas_venta (venta_id);
