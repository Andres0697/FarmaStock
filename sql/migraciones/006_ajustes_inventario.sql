-- 006: ajustes tipificados (merma, vencido, devolución a proveedor, conteo físico).
CREATE TABLE ajustes_inventario (
    id INT NOT NULL AUTO_INCREMENT,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo ENUM('Merma','Vencido','Devolución a proveedor','Conteo físico') NOT NULL,
    producto_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad_antes INT NOT NULL,
    cantidad_despues INT NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    usuario_id INT NOT NULL,
    CONSTRAINT pk_ajustes_inventario PRIMARY KEY (id),
    CONSTRAINT fk_aj_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_aj_lote FOREIGN KEY (lote_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_aj_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
