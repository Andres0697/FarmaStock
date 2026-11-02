-- 001: rol Regente, bitácora de auditoría y desviaciones FEFO. Solo agrega.
ALTER TABLE usuarios MODIFY rol ENUM('Administrador','Vendedor','Regente') NOT NULL;

CREATE TABLE bitacora_auditoria (
    id BIGINT NOT NULL AUTO_INCREMENT,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT NULL,
    accion VARCHAR(60) NOT NULL,
    entidad VARCHAR(60) NOT NULL,
    entidad_id VARCHAR(40) NULL,
    detalle VARCHAR(500) NULL,
    CONSTRAINT pk_bitacora PRIMARY KEY (id),
    CONSTRAINT fk_bitacora_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX idx_bitacora_fecha ON bitacora_auditoria (fecha);
CREATE INDEX idx_bitacora_accion ON bitacora_auditoria (accion);

CREATE TABLE desviaciones_fefo (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    usuario_id INT NOT NULL,
    lote_sugerido_id INT NOT NULL,
    lote_vendido_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR(255) NULL,
    CONSTRAINT pk_desviaciones_fefo PRIMARY KEY (id),
    CONSTRAINT fk_desv_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_sugerido FOREIGN KEY (lote_sugerido_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_desv_vendido FOREIGN KEY (lote_vendido_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

INSERT INTO usuarios(nombre,usuario,password_hash,rol,estado)
SELECT 'Regente Farmacéutico','regente','pbkdf2_sha256$120000$eeaad6cf8d91f8083bf2afc11942bbc6$c637a0074b9727b7074e13b41262de159bde2e478a5676085b892434534794a9','Regente','Activo'
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE usuario='regente');
