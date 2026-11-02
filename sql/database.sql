DROP DATABASE IF EXISTS farmastock;
CREATE DATABASE farmastock
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE farmastock;

CREATE TABLE usuarios (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    usuario VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('Administrador','Vendedor') NOT NULL,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_usuarios PRIMARY KEY (id),
    CONSTRAINT uq_usuarios_usuario UNIQUE (usuario)
) ENGINE=InnoDB;

CREATE TABLE categorias (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    descripcion VARCHAR(255) NULL,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_categorias PRIMARY KEY (id),
    CONSTRAINT uq_categorias_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

CREATE TABLE proveedores (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    telefono VARCHAR(25) NULL,
    correo VARCHAR(120) NULL,
    direccion VARCHAR(255) NULL,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_proveedores PRIMARY KEY (id),
    CONSTRAINT uq_proveedores_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

CREATE TABLE principios_activos (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(160) NOT NULL,
    descripcion VARCHAR(255) NULL,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_principios_activos PRIMARY KEY (id),
    CONSTRAINT uq_principios_activos_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

CREATE TABLE marcas (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    laboratorio VARCHAR(160) NULL,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_marcas PRIMARY KEY (id),
    CONSTRAINT uq_marcas_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

CREATE TABLE productos (
    id INT NOT NULL AUTO_INCREMENT,
    codigo VARCHAR(50) NOT NULL,
    codigo_barras VARCHAR(50) NULL,
    nombre_comercial VARCHAR(160) NOT NULL,
    principio_activo_id INT NOT NULL,
    marca_id INT NULL,
    concentracion DECIMAL(12,3) NULL,
    unidad_concentracion VARCHAR(30) NULL,
    forma_farmaceutica VARCHAR(60) NULL,
    via_administracion VARCHAR(80) NULL,
    presentacion VARCHAR(100) NULL,
    cantidad_presentacion INT NOT NULL DEFAULT 1,
    unidad_presentacion VARCHAR(40) NOT NULL DEFAULT 'unidades',
    descripcion VARCHAR(500) NULL,
    categoria_id INT NOT NULL,
    precio_venta DECIMAL(12,2) NOT NULL,
    stock_minimo INT NOT NULL DEFAULT 0,
    requiere_receta BOOLEAN NOT NULL DEFAULT FALSE,
    control_especial BOOLEAN NOT NULL DEFAULT FALSE,
    estado ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_productos PRIMARY KEY (id),
    CONSTRAINT uq_productos_codigo UNIQUE (codigo),
    CONSTRAINT uq_productos_codigo_barras UNIQUE (codigo_barras),
    CONSTRAINT fk_productos_principio
        FOREIGN KEY (principio_activo_id) REFERENCES principios_activos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_productos_marca
        FOREIGN KEY (marca_id) REFERENCES marcas(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_productos_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_productos_precio CHECK (precio_venta > 0),
    CONSTRAINT chk_productos_stock_minimo CHECK (stock_minimo >= 0),
    CONSTRAINT chk_productos_cantidad_presentacion CHECK (cantidad_presentacion > 0)
) ENGINE=InnoDB;

CREATE TABLE nombres_alternativos (
    id INT NOT NULL AUTO_INCREMENT,
    producto_id INT NOT NULL,
    nombre VARCHAR(160) NOT NULL,
    CONSTRAINT pk_nombres_alternativos PRIMARY KEY (id),
    CONSTRAINT uq_nombres_alternativos_producto_nombre UNIQUE (producto_id, nombre),
    CONSTRAINT fk_nombres_alternativos_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE lotes (
    id INT NOT NULL AUTO_INCREMENT,
    producto_id INT NOT NULL,
    numero_lote VARCHAR(80) NOT NULL,
    fecha_fabricacion DATE NULL,
    fecha_vencimiento DATE NOT NULL,
    cantidad_inicial INT NOT NULL,
    cantidad_actual INT NOT NULL,
    precio_compra DECIMAL(12,2) NOT NULL DEFAULT 0,
    proveedor_id INT NULL,
    fecha_recepcion DATE NOT NULL,
    estado ENUM('Disponible','Agotado','Cuarentena','Vencido','Retirado') NOT NULL DEFAULT 'Disponible',
    ubicacion VARCHAR(80) NULL,
    CONSTRAINT pk_lotes PRIMARY KEY (id),
    CONSTRAINT uq_lotes_producto_numero UNIQUE (producto_id, numero_lote),
    CONSTRAINT fk_lotes_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_lotes_proveedor
        FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_lotes_cantidad CHECK (cantidad_inicial > 0 AND cantidad_actual >= 0),
    CONSTRAINT chk_lotes_precio_compra CHECK (precio_compra >= 0)
) ENGINE=InnoDB;

CREATE TABLE ventas (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(12,2) NOT NULL,
    descuento DECIMAL(12,2) NOT NULL DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    estado ENUM('Completada','Anulada') NOT NULL DEFAULT 'Completada',
    CONSTRAINT pk_ventas PRIMARY KEY (id),
    CONSTRAINT fk_ventas_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_ventas_valores CHECK (
        subtotal >= 0 AND descuento >= 0 AND total >= 0 AND descuento <= subtotal
    )
) ENGINE=InnoDB;

CREATE TABLE detalle_venta (
    id INT NOT NULL AUTO_INCREMENT,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    lote_id INT NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    CONSTRAINT pk_detalle_venta PRIMARY KEY (id),
    CONSTRAINT fk_detalle_venta_venta
        FOREIGN KEY (venta_id) REFERENCES ventas(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_detalle_venta_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_detalle_venta_lote
        FOREIGN KEY (lote_id) REFERENCES lotes(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_detalle_venta_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_detalle_venta_precio CHECK (precio_unitario >= 0),
    CONSTRAINT chk_detalle_venta_subtotal CHECK (subtotal >= 0)
) ENGINE=InnoDB;

CREATE TABLE movimientos_inventario (
    id BIGINT NOT NULL AUTO_INCREMENT,
    producto_id INT NOT NULL,
    lote_id INT NULL,
    tipo_movimiento ENUM(
        'Entrada','Venta','Ajuste','Devolución','Merma','Vencimiento','Retiro'
    ) NOT NULL,
    cantidad INT NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    referencia VARCHAR(100) NULL,
    usuario_id INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_movimientos_inventario PRIMARY KEY (id),
    CONSTRAINT fk_movimientos_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_movimientos_lote
        FOREIGN KEY (lote_id) REFERENCES lotes(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_movimientos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Índices de consulta y apoyo a las relaciones.
CREATE INDEX idx_productos_nombre
    ON productos (nombre_comercial);
CREATE INDEX idx_productos_principio_categoria
    ON productos (principio_activo_id, categoria_id);
CREATE INDEX idx_productos_codigo_barras
    ON productos (codigo_barras);

CREATE INDEX idx_lotes_producto_estado_vencimiento
    ON lotes (producto_id, estado, fecha_vencimiento);
CREATE INDEX idx_lotes_vencimiento
    ON lotes (fecha_vencimiento);
CREATE INDEX idx_lotes_proveedor
    ON lotes (proveedor_id);

CREATE INDEX idx_nombres_alternativos_nombre
    ON nombres_alternativos (nombre);

CREATE INDEX idx_ventas_usuario_fecha
    ON ventas (usuario_id, fecha);
CREATE INDEX idx_ventas_fecha
    ON ventas (fecha);

CREATE INDEX idx_detalle_venta_producto
    ON detalle_venta (producto_id);
CREATE INDEX idx_detalle_venta_lote
    ON detalle_venta (lote_id);

CREATE INDEX idx_movimientos_producto_fecha
    ON movimientos_inventario (producto_id, fecha);
CREATE INDEX idx_movimientos_lote
    ON movimientos_inventario (lote_id);
CREATE INDEX idx_movimientos_usuario_fecha
    ON movimientos_inventario (usuario_id, fecha);
