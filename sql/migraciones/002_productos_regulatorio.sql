-- 002: registro sanitario y categoría de dispensación (convive con requiere_receta/control_especial).
ALTER TABLE productos
    ADD COLUMN registro_sanitario VARCHAR(60) NULL,
    ADD COLUMN categoria_dispensacion ENUM('Venta libre','Con receta','Receta retenida','Controlado') NOT NULL DEFAULT 'Venta libre';
UPDATE productos SET categoria_dispensacion='Controlado' WHERE control_especial=TRUE;
UPDATE productos SET categoria_dispensacion='Con receta' WHERE requiere_receta=TRUE AND control_especial=FALSE;

CREATE TABLE historial_precios (
    id INT NOT NULL AUTO_INCREMENT,
    producto_id INT NOT NULL,
    precio_anterior DECIMAL(12,2) NOT NULL,
    precio_nuevo DECIMAL(12,2) NOT NULL,
    usuario_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_historial_precios PRIMARY KEY (id),
    CONSTRAINT fk_hp_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_hp_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
