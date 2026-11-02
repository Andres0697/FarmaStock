-- Migración 002: entradas de mercadería por documento (factura del proveedor).
-- Solo AGREGA tablas. No modifica ni borra nada existente.
-- Una entrada = un documento (proveedor + factura + fecha) con varias líneas.
-- Cada línea crea (o suma a) un lote en `lotes`. Para deshacer: 002_..._down.sql
USE farmastock;

CREATE TABLE entradas_inventario (
    id INT NOT NULL AUTO_INCREMENT,
    proveedor_id INT NOT NULL,
    numero_factura VARCHAR(60) NOT NULL,
    fecha_factura DATE NOT NULL,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT NOT NULL,
    total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    observaciones VARCHAR(255) NULL,
    CONSTRAINT pk_entradas_inventario PRIMARY KEY (id),
    -- La misma factura de un proveedor no se puede registrar dos veces
    CONSTRAINT uq_entradas_factura UNIQUE (proveedor_id, numero_factura),
    CONSTRAINT chk_entradas_total CHECK (total >= 0),
    CONSTRAINT fk_entradas_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entradas_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX idx_entradas_fecha ON entradas_inventario (fecha_factura);

CREATE TABLE entrada_detalle (
    id INT NOT NULL AUTO_INCREMENT,
    entrada_id INT NOT NULL,
    producto_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad INT NOT NULL,
    costo_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    CONSTRAINT pk_entrada_detalle PRIMARY KEY (id),
    CONSTRAINT chk_entrada_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_entrada_costo CHECK (costo_unitario >= 0),
    CONSTRAINT fk_entdet_entrada FOREIGN KEY (entrada_id) REFERENCES entradas_inventario(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entdet_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entdet_lote FOREIGN KEY (lote_id) REFERENCES lotes(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX idx_entdet_entrada ON entrada_detalle (entrada_id);
