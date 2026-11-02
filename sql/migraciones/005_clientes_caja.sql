-- 005: clientes, turnos de caja, forma de pago, notas de crédito y abonos.
CREATE TABLE clientes (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(140) NOT NULL,
    documento VARCHAR(40) NULL,
    ruc VARCHAR(30) NULL,
    telefono VARCHAR(25) NULL,
    direccion VARCHAR(255) NULL,
    limite_credito DECIMAL(12,2) NOT NULL DEFAULT 0,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_clientes PRIMARY KEY (id)
) ENGINE=InnoDB;
CREATE INDEX idx_clientes_nombre ON clientes (nombre);

CREATE TABLE turnos_caja (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    apertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    monto_inicial DECIMAL(12,2) NOT NULL,
    cierre TIMESTAMP NULL,
    efectivo_esperado DECIMAL(12,2) NULL,
    efectivo_contado DECIMAL(12,2) NULL,
    diferencia DECIMAL(12,2) NULL,
    estado ENUM('Abierto','Cerrado') NOT NULL DEFAULT 'Abierto',
    CONSTRAINT pk_turnos_caja PRIMARY KEY (id),
    CONSTRAINT fk_turno_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

ALTER TABLE ventas
    ADD COLUMN cliente_id INT NULL,
    ADD COLUMN turno_id INT NULL,
    ADD COLUMN metodo_pago ENUM('Efectivo','Tarjeta','Transferencia','Crédito') NOT NULL DEFAULT 'Efectivo',
    ADD COLUMN numero_factura VARCHAR(30) NULL,
    ADD COLUMN anulada_por INT NULL,
    ADD COLUMN motivo_anulacion VARCHAR(255) NULL,
    ADD CONSTRAINT fk_ventas_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON UPDATE CASCADE ON DELETE SET NULL,
    ADD CONSTRAINT fk_ventas_turno FOREIGN KEY (turno_id) REFERENCES turnos_caja(id) ON UPDATE CASCADE ON DELETE SET NULL;

CREATE TABLE abonos_cliente (
    id INT NOT NULL AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    venta_id INT NULL,
    monto DECIMAL(12,2) NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT NOT NULL,
    CONSTRAINT pk_abonos_cliente PRIMARY KEY (id),
    CONSTRAINT fk_ab_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ab_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE notas_credito (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    detalle_venta_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    usuario_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_notas_credito PRIMARY KEY (id),
    CONSTRAINT fk_nc_venta FOREIGN KEY (venta_id) REFERENCES ventas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_nc_detalle FOREIGN KEY (detalle_venta_id) REFERENCES detalle_venta(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_nc_lote FOREIGN KEY (lote_id) REFERENCES lotes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_nc_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
