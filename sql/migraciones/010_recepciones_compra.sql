-- 010: recepciones de compra (parciales, varios lotes por línea) y estado "Parcial".
-- Idempotente. Una orden puede recibirse en varias recepciones; cada recepción registra
-- sus lotes y genera su propia cuenta por pagar. Lo ya recibido con el flujo anterior
-- (recepción total) se migra como una recepción por orden.

-- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ordenes_compra' AND column_name='estado' AND column_type LIKE '%Parcial%'
ALTER TABLE ordenes_compra MODIFY estado ENUM('Pendiente','Parcial','Recibida','Anulada') NOT NULL DEFAULT 'Pendiente';

CREATE TABLE IF NOT EXISTS recepciones_compra (
    id INT NOT NULL AUTO_INCREMENT,
    orden_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT NOT NULL,
    numero_documento VARCHAR(60) NULL,
    observaciones VARCHAR(255) NULL,
    CONSTRAINT pk_recepciones_compra PRIMARY KEY (id),
    CONSTRAINT fk_rc_orden FOREIGN KEY (orden_id) REFERENCES ordenes_compra(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rc_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_rc_orden (orden_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS recepcion_detalle (
    id INT NOT NULL AUTO_INCREMENT,
    recepcion_id INT NOT NULL,
    detalle_orden_id INT NOT NULL,
    producto_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad INT NOT NULL,
    costo_unitario DECIMAL(12,2) NOT NULL,
    CONSTRAINT pk_recepcion_detalle PRIMARY KEY (id),
    CONSTRAINT chk_rd_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_rd_costo CHECK (costo_unitario >= 0),
    CONSTRAINT fk_rd_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rd_detalle FOREIGN KEY (detalle_orden_id) REFERENCES detalle_orden_compra(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rd_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rd_lote FOREIGN KEY (lote_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_rd_recepcion (recepcion_id),
    INDEX idx_rd_detalle (detalle_orden_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cada cuenta por pagar nace de una recepción
-- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='cuentas_por_pagar' AND column_name='recepcion_id'
ALTER TABLE cuentas_por_pagar ADD COLUMN recepcion_id INT NULL AFTER orden_id;

-- @skip_if: SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='cuentas_por_pagar' AND constraint_name='fk_cxp_recepcion'
ALTER TABLE cuentas_por_pagar ADD CONSTRAINT fk_cxp_recepcion FOREIGN KEY (recepcion_id) REFERENCES recepciones_compra(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- Migración de lo recibido con el flujo anterior (una recepción por orden)
INSERT INTO recepciones_compra (orden_id, fecha, usuario_id, observaciones)
SELECT o.id, o.fecha, o.usuario_id, 'Migrada de la recepción total anterior'
FROM ordenes_compra o
WHERE o.estado = 'Recibida' AND NOT EXISTS (SELECT 1 FROM recepciones_compra r WHERE r.orden_id = o.id);

INSERT INTO recepcion_detalle (recepcion_id, detalle_orden_id, producto_id, lote_id, cantidad, costo_unitario)
SELECT r.id, d.id, d.producto_id, d.lote_id, d.cantidad, d.costo_unitario
FROM detalle_orden_compra d JOIN recepciones_compra r ON r.orden_id = d.orden_id
WHERE d.lote_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM recepcion_detalle x WHERE x.detalle_orden_id = d.id);

UPDATE cuentas_por_pagar c JOIN recepciones_compra r ON r.orden_id = c.orden_id SET c.recepcion_id = r.id WHERE c.recepcion_id IS NULL;
