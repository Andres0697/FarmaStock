-- 004: órdenes de compra, recepción (genera lotes) y cuentas por pagar.
CREATE TABLE ordenes_compra (
    id INT NOT NULL AUTO_INCREMENT,
    proveedor_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado ENUM('Pendiente','Recibida','Anulada') NOT NULL DEFAULT 'Pendiente',
    total DECIMAL(12,2) NOT NULL DEFAULT 0,
    dias_credito INT NOT NULL DEFAULT 0,
    usuario_id INT NOT NULL,
    CONSTRAINT pk_ordenes_compra PRIMARY KEY (id),
    CONSTRAINT fk_oc_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_oc_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE detalle_orden_compra (
    id INT NOT NULL AUTO_INCREMENT,
    orden_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    costo_unitario DECIMAL(12,2) NOT NULL,
    numero_lote VARCHAR(80) NULL,
    fecha_vencimiento DATE NULL,
    lote_id INT NULL,
    CONSTRAINT pk_detalle_oc PRIMARY KEY (id),
    CONSTRAINT fk_doc_orden FOREIGN KEY (orden_id) REFERENCES ordenes_compra(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_doc_producto FOREIGN KEY (producto_id) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_doc_lote FOREIGN KEY (lote_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_doc_cantidad CHECK (cantidad > 0)
) ENGINE=InnoDB;

CREATE TABLE cuentas_por_pagar (
    id INT NOT NULL AUTO_INCREMENT,
    orden_id INT NOT NULL,
    proveedor_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    saldo DECIMAL(12,2) NOT NULL,
    fecha_emision DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado ENUM('Pendiente','Pagada') NOT NULL DEFAULT 'Pendiente',
    CONSTRAINT pk_cxp PRIMARY KEY (id),
    CONSTRAINT fk_cxp_orden FOREIGN KEY (orden_id) REFERENCES ordenes_compra(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cxp_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE pagos_proveedor (
    id INT NOT NULL AUTO_INCREMENT,
    cuenta_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT NOT NULL,
    CONSTRAINT pk_pagos_proveedor PRIMARY KEY (id),
    CONSTRAINT fk_pp_cuenta FOREIGN KEY (cuenta_id) REFERENCES cuentas_por_pagar(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pp_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
