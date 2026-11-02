-- 003: libro de psicotrópicos y estupefacientes.
CREATE TABLE libro_controlados (
    id INT NOT NULL AUTO_INCREMENT,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad INT NOT NULL,
    paciente_nombre VARCHAR(140) NOT NULL,
    paciente_documento VARCHAR(40) NULL,
    medico_nombre VARCHAR(140) NOT NULL,
    medico_codigo VARCHAR(40) NULL,
    numero_receta VARCHAR(60) NOT NULL,
    usuario_id INT NOT NULL,
    CONSTRAINT pk_libro_controlados PRIMARY KEY (id),
    CONSTRAINT fk_lc_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_lc_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_lc_lote FOREIGN KEY (lote_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_lc_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX idx_lc_fecha ON libro_controlados (fecha);
