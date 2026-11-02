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


-- DATOS DE DEMOSTRACION --
USE farmastock;

INSERT INTO usuarios(nombre,usuario,password_hash,rol,estado) VALUES
('Administrador General','admin','pbkdf2_sha256$120000$00112233445566778899aabbccddeeff$48375c481b3fb108a8a8ee8299290b3fe4f349646b4f9e7ce6749ef645cd5760','Administrador','Activo'),
('Vendedor Principal','vendedor','pbkdf2_sha256$120000$e7e3a7909abc12fb72c75bcdf8b42e5a$2479944d7c4659bbe3a1051b4e1d4d5a5c1624a93eb9475bf593704e4133b125','Vendedor','Activo');

INSERT INTO categorias(nombre,descripcion) VALUES
('Analgésicos','Productos para alivio del dolor y fiebre.'),('Antiinflamatorios','Productos de uso antiinflamatorio.'),('Antibióticos','Medicamentos antibacterianos para gestión de inventario.'),('Vitaminas','Vitaminas y suplementos.'),('Antisépticos','Productos para higiene y antisepsia.'),('Gastrointestinal','Productos para molestias gastrointestinales.'),('Respiratorio','Productos de uso respiratorio.'),('Dermatología','Productos de cuidado de la piel.'),('Higiene personal','Cuidado e higiene personal.'),('Primeros auxilios','Materiales de primeros auxilios.');

INSERT INTO proveedores(nombre,telefono,correo,direccion) VALUES
('Distribuidora Salud S.A.','2255-1000','ventas@disalud.example','Managua'),('Farmacéutica Central','2277-2000','contacto@fcentral.example','Managua'),('MedSupply Nicaragua','2266-3000','ventas@medsupply.example','Masaya'),('Comercial Farmacéutica Norte','2713-4400','ventas@comfar.example','Estelí'),('Importadora Médica Nacional','2220-5500','contacto@imn.example','Managua');

INSERT INTO principios_activos(nombre) VALUES
('Paracetamol'),('Ibuprofeno'),('Amoxicilina'),('Ácido ascórbico'),('Omeprazol'),('Loratadina'),('Clotrimazol'),('Sales de rehidratación oral'),('Benzalconio'),('Dextrometorfano'),('Carbonato de calcio'),('Sulfato ferroso'),('Miconazol'),('Simeticona'),('Diclofenaco');

INSERT INTO marcas(nombre,laboratorio) VALUES
('Genfar','Genfar'),('MK','Tecnoquímicas'),('Bayer','Bayer'),('La Santé','La Santé'),('Medipharma','Medipharma'),('FarmaPlus','FarmaPlus'),('Nacional','Laboratorios Nacionales'),('Genérico','Presentación genérica');

INSERT INTO productos(codigo,codigo_barras,nombre_comercial,principio_activo_id,marca_id,concentracion,unidad_concentracion,forma_farmaceutica,via_administracion,presentacion,cantidad_presentacion,unidad_presentacion,descripcion,categoria_id,precio_venta,stock_minimo,requiere_receta,control_especial)
SELECT 'FAR-001','7501000000011','Paracetamol',pa.id,m.id,500,'mg','Tableta','Oral','Caja',20,'tabletas','Analgésico de venta en presentación de ejemplo.',c.id,4.50,15,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Paracetamol' AND m.nombre='Genérico' AND c.nombre='Analgésicos'
UNION ALL SELECT 'FAR-002','7501000000012','Ibuprofeno',pa.id,m.id,400,'mg','Tableta','Oral','Caja',20,'tabletas','Presentación de ejemplo.',c.id,6.00,10,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Ibuprofeno' AND m.nombre='MK' AND c.nombre='Antiinflamatorios'
UNION ALL SELECT 'FAR-003','7501000000013','Amoxicilina',pa.id,m.id,500,'mg','Cápsula','Oral','Caja',20,'cápsulas','Producto de ejemplo para control de lotes.',c.id,8.50,8,1,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Amoxicilina' AND m.nombre='Genfar' AND c.nombre='Antibióticos'
UNION ALL SELECT 'FAR-004','7501000000014','Vitamina C',pa.id,m.id,500,'mg','Tableta','Oral','Frasco',30,'tabletas','Suplemento de ejemplo.',c.id,7.50,12,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Ácido ascórbico' AND m.nombre='FarmaPlus' AND c.nombre='Vitaminas'
UNION ALL SELECT 'FAR-005','7501000000015','Omeprazol',pa.id,m.id,20,'mg','Cápsula','Oral','Caja',14,'cápsulas','Presentación de ejemplo.',c.id,9.75,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Omeprazol' AND m.nombre='Genfar' AND c.nombre='Gastrointestinal'
UNION ALL SELECT 'FAR-006','7501000000016','Loratadina',pa.id,m.id,10,'mg','Tableta','Oral','Caja',10,'tabletas','Presentación de ejemplo.',c.id,6.75,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Loratadina' AND m.nombre='MK' AND c.nombre='Respiratorio'
UNION ALL SELECT 'FAR-007','7501000000017','Clotrimazol crema',pa.id,m.id,1,'%','Crema','Tópica','Tubo',20,'g','Presentación de ejemplo.',c.id,8.25,6,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Clotrimazol' AND m.nombre='Genérico' AND c.nombre='Dermatología'
UNION ALL SELECT 'FAR-008','7501000000018','Sales de rehidratación',pa.id,m.id,20,'g','Polvo','Oral','Caja',10,'sobres','Presentación de ejemplo.',c.id,5.50,10,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Sales de rehidratación oral' AND m.nombre='Nacional' AND c.nombre='Gastrointestinal'
UNION ALL SELECT 'FAR-009','7501000000019','Solución antiséptica',pa.id,m.id,0.1,'%','Solución','Tópica','Frasco',120,'mL','Presentación de ejemplo.',c.id,6.25,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Benzalconio' AND m.nombre='FarmaPlus' AND c.nombre='Antisépticos'
UNION ALL SELECT 'FAR-010','7501000000020','Jarabe para la tos',pa.id,m.id,15,'mg/5 mL','Jarabe','Oral','Frasco',120,'mL','Presentación de ejemplo.',c.id,10.50,6,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Dextrometorfano' AND m.nombre='Nacional' AND c.nombre='Respiratorio'
UNION ALL SELECT 'FAR-011','7501000000021','Carbonato de calcio',pa.id,m.id,500,'mg','Tableta','Oral','Frasco',60,'tabletas','Presentación de ejemplo.',c.id,11.00,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Carbonato de calcio' AND m.nombre='Bayer' AND c.nombre='Vitaminas'
UNION ALL SELECT 'FAR-012','7501000000022','Sulfato ferroso',pa.id,m.id,300,'mg','Tableta','Oral','Frasco',30,'tabletas','Presentación de ejemplo.',c.id,8.80,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Sulfato ferroso' AND m.nombre='Genérico' AND c.nombre='Vitaminas'
UNION ALL SELECT 'FAR-013','7501000000023','Miconazol crema',pa.id,m.id,2,'%','Crema','Tópica','Tubo',20,'g','Presentación de ejemplo.',c.id,9.20,5,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Miconazol' AND m.nombre='Genfar' AND c.nombre='Dermatología'
UNION ALL SELECT 'FAR-014','7501000000024','Simeticona',pa.id,m.id,40,'mg','Tableta','Oral','Caja',20,'tabletas','Presentación de ejemplo.',c.id,7.90,6,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Simeticona' AND m.nombre='MK' AND c.nombre='Gastrointestinal'
UNION ALL SELECT 'FAR-015','7501000000025','Diclofenaco',pa.id,m.id,50,'mg','Tableta','Oral','Caja',20,'tabletas','Presentación de ejemplo.',c.id,7.25,10,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Diclofenaco' AND m.nombre='Genérico' AND c.nombre='Antiinflamatorios'
UNION ALL SELECT 'FAR-016','7501000000026','Alcohol antiséptico',pa.id,m.id,70,'%','Solución','Tópica','Frasco',250,'mL','Presentación de ejemplo.',c.id,5.00,10,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Benzalconio' AND m.nombre='Nacional' AND c.nombre='Antisépticos'
UNION ALL SELECT 'FAR-017','7501000000027','Paracetamol pediátrico',pa.id,m.id,160,'mg/5 mL','Suspensión','Oral','Frasco',120,'mL','Presentación de ejemplo.',c.id,9.50,5,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Paracetamol' AND m.nombre='Genfar' AND c.nombre='Analgésicos'
UNION ALL SELECT 'FAR-018','7501000000028','Ibuprofeno suspensión',pa.id,m.id,100,'mg/5 mL','Suspensión','Oral','Frasco',120,'mL','Presentación de ejemplo.',c.id,10.25,5,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Ibuprofeno' AND m.nombre='La Santé' AND c.nombre='Antiinflamatorios'
UNION ALL SELECT 'FAR-019','7501000000029','Gel de clotrimazol',pa.id,m.id,1,'%','Gel','Tópica','Tubo',30,'g','Presentación de ejemplo.',c.id,10.00,4,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Clotrimazol' AND m.nombre='La Santé' AND c.nombre='Dermatología'
UNION ALL SELECT 'FAR-020','7501000000030','Tabletas digestivas',pa.id,m.id,40,'mg','Tableta','Oral','Caja',30,'tabletas','Presentación de ejemplo.',c.id,6.90,8,0,0 FROM principios_activos pa,marcas m,categorias c WHERE pa.nombre='Simeticona' AND m.nombre='FarmaPlus' AND c.nombre='Gastrointestinal';

INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Acetaminofén' FROM productos WHERE codigo='FAR-001';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Acetaminofen 500' FROM productos WHERE codigo='FAR-001';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Paracetamol genérico' FROM productos WHERE codigo='FAR-001';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Vitamina C' FROM productos WHERE codigo='FAR-004';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Ácido ascórbico' FROM productos WHERE codigo='FAR-004';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Omeprazol 20' FROM productos WHERE codigo='FAR-005';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Antifúngico crema' FROM productos WHERE codigo='FAR-007';
INSERT INTO nombres_alternativos(producto_id,nombre) SELECT id,'Sales ORS' FROM productos WHERE codigo='FAR-008';

INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT p.id,'PAR-A01',DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 5 MONTH),12,12,2.30,pr.id,CURDATE(),'Disponible','Estante A-01' FROM productos p,proveedores pr WHERE p.codigo='FAR-001' AND pr.nombre='Distribuidora Salud S.A.';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-001'),'PAR-B02',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 18 MONTH),30,30,2.50,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante A-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-002'),'IBU-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 10 MONTH),8,8,3.20,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante A-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-003'),'AMO-A01',DATE_SUB(CURDATE(),INTERVAL 4 MONTH),DATE_ADD(CURDATE(),INTERVAL 14 MONTH),24,24,5.00,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante B-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-004'),'VIT-A01',DATE_SUB(CURDATE(),INTERVAL 5 MONTH),DATE_ADD(CURDATE(),INTERVAL 45 DAY),5,5,4.00,(SELECT id FROM proveedores WHERE nombre='MedSupply Nicaragua'),CURDATE(),'Disponible','Estante C-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-005'),'OME-A01',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 16 MONTH),18,18,6.00,(SELECT id FROM proveedores WHERE nombre='Importadora Médica Nacional') ,CURDATE(),'Disponible','Estante D-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion)
SELECT id,'LOR-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 20 MONTH),20,20,4.20,(SELECT id FROM proveedores WHERE nombre='Distribuidora Salud S.A.'),CURDATE(),'Disponible','Estante E-01' FROM productos WHERE codigo='FAR-006';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-007'),'CLO-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 15 MONTH),12,12,5.50,(SELECT id FROM proveedores WHERE nombre='MedSupply Nicaragua'),CURDATE(),'Disponible','Estante F-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-008'),'SRO-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 24 MONTH),25,25,3.00,(SELECT id FROM proveedores WHERE nombre='Comercial Farmacéutica Norte'),CURDATE(),'Disponible','Estante G-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-009'),'ANT-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 20 MONTH),15,15,3.50,(SELECT id FROM proveedores WHERE nombre='MedSupply Nicaragua'),CURDATE(),'Disponible','Estante H-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-010'),'TOS-A01',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 11 MONTH),8,8,6.80,(SELECT id FROM proveedores WHERE nombre='Comercial Farmacéutica Norte'),CURDATE(),'Disponible','Estante I-01';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-011'),'CAL-A01',DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 18 MONTH),22,22,6.00,(SELECT id FROM proveedores WHERE nombre='Importadora Médica Nacional'),CURDATE(),'Disponible','Estante C-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-012'),'FER-A01',DATE_SUB(CURDATE(),INTERVAL 4 MONTH),DATE_ADD(CURDATE(),INTERVAL 13 MONTH),4,4,5.00,(SELECT id FROM proveedores WHERE nombre='Comercial Farmacéutica Norte'),CURDATE(),'Disponible','Estante C-03';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-013'),'MIC-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 14 MONTH),9,9,6.20,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante F-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-014'),'SIM-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 17 MONTH),18,18,4.80,(SELECT id FROM proveedores WHERE nombre='Distribuidora Salud S.A.'),CURDATE(),'Disponible','Estante D-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-015'),'DIC-A01',DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 9 MONTH),10,10,4.10,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante B-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-016'),'ALC-A01',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 30 MONTH),20,20,2.80,(SELECT id FROM proveedores WHERE nombre='MedSupply Nicaragua'),CURDATE(),'Disponible','Estante H-02';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-017'),'PARP-A01',DATE_SUB(CURDATE(),INTERVAL 1 MONTH),DATE_ADD(CURDATE(),INTERVAL 12 MONTH),10,10,6.20,(SELECT id FROM proveedores WHERE nombre='Comercial Farmacéutica Norte'),CURDATE(),'Disponible','Estante A-03';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-018'),'IBUP-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 8 MONTH),6,6,6.50,(SELECT id FROM proveedores WHERE nombre='Importadora Médica Nacional'),CURDATE(),'Disponible','Estante A-04';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-019'),'GEL-A01',DATE_SUB(CURDATE(),INTERVAL 2 MONTH),DATE_ADD(CURDATE(),INTERVAL 10 MONTH),3,3,6.40,(SELECT id FROM proveedores WHERE nombre='Farmacéutica Central'),CURDATE(),'Disponible','Estante F-03';
INSERT INTO lotes(producto_id,numero_lote,fecha_fabricacion,fecha_vencimiento,cantidad_inicial,cantidad_actual,precio_compra,proveedor_id,fecha_recepcion,estado,ubicacion) SELECT (SELECT id FROM productos WHERE codigo='FAR-020'),'DIG-A01',DATE_SUB(CURDATE(),INTERVAL 3 MONTH),DATE_ADD(CURDATE(),INTERVAL 16 MONTH),14,14,4.30,(SELECT id FROM proveedores WHERE nombre='Distribuidora Salud S.A.'),CURDATE(),'Disponible','Estante D-03';

INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id)
SELECT l.producto_id,l.id,'Entrada',l.cantidad_inicial,'Carga inicial de inventario','SEED',1 FROM lotes l
WHERE NOT EXISTS (SELECT 1 FROM movimientos_inventario m WHERE m.lote_id=l.id AND m.referencia='SEED');
