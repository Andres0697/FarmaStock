-- 009: pagos de una venta en tabla propia (permite pago combinado, referencias y reportes
-- por método). `ventas.metodo_pago` se conserva como resumen por compatibilidad.
CREATE TABLE IF NOT EXISTS pagos_venta (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    metodo ENUM('Efectivo','Tarjeta','Transferencia','Crédito') NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    monto_recibido DECIMAL(12,2) NULL,
    cambio DECIMAL(12,2) NOT NULL DEFAULT 0,
    referencia VARCHAR(80) NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_pagos_venta PRIMARY KEY (id),
    CONSTRAINT fk_pagos_venta_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pagos_venta_monto CHECK (monto > 0 AND cambio >= 0),
    INDEX idx_pagos_venta_venta (venta_id),
    INDEX idx_pagos_venta_metodo_fecha (metodo, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Ventas que ya existían: un pago por venta con su método y total
INSERT INTO pagos_venta (venta_id, metodo, monto, monto_recibido, cambio, fecha)
SELECT v.id, v.metodo_pago, v.total, v.monto_recibido,
       GREATEST(COALESCE(v.monto_recibido, v.total) - v.total, 0), v.fecha
FROM ventas v
WHERE v.total > 0 AND NOT EXISTS (SELECT 1 FROM pagos_venta p WHERE p.venta_id = v.id);
