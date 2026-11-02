"""Mapeo declarativo SQLAlchemy de todas las tablas de FarmaStock.

Los nombres, columnas, tipos y claves foráneas reflejan sql/database.sql y
las migraciones numeradas vigentes. No crea ni modifica tablas por sí mismo.
"""
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, UniqueConstraint, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.orm import Base

ESTADOS = ("Activo", "Inactivo")

class AbonoCliente(Base):
    __tablename__ = "abonos_cliente"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    cliente_id: Mapped[object] = mapped_column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, nullable=True)
    monto: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    cliente = relationship("Cliente", foreign_keys=[cliente_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class AjusteInventario(Base):
    __tablename__ = "ajustes_inventario"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    tipo: Mapped[object] = mapped_column(Enum('Merma', 'Vencido', 'Devolución a proveedor', 'Conteo físico', native_enum=True), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad_antes: Mapped[object] = mapped_column(Integer, nullable=False)
    cantidad_despues: Mapped[object] = mapped_column(Integer, nullable=False)
    motivo: Mapped[object] = mapped_column(String(255), nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"
    id: Mapped[object] = mapped_column(BigInteger, autoincrement=True, primary_key=True, nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    accion: Mapped[object] = mapped_column(String(60), nullable=False)
    entidad: Mapped[object] = mapped_column(String(60), nullable=False)
    entidad_id: Mapped[object] = mapped_column(String(40), nullable=True)
    detalle: Mapped[object] = mapped_column(String(500), nullable=True)
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = (UniqueConstraint('nombre', name="uq_categorias_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[object] = mapped_column(String(255), nullable=True)
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))

    def as_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "descripcion": self.descripcion, "estado": self.estado}

class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(140), nullable=False)
    documento: Mapped[object] = mapped_column(String(40), nullable=True)
    ruc: Mapped[object] = mapped_column(String(30), nullable=True)
    telefono: Mapped[object] = mapped_column(String(25), nullable=True)
    direccion: Mapped[object] = mapped_column(String(255), nullable=True)
    limite_credito: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))

class CuentaPorPagar(Base):
    __tablename__ = "cuentas_por_pagar"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    orden_id: Mapped[object] = mapped_column(Integer, ForeignKey("ordenes_compra.id", ondelete="RESTRICT"), nullable=False)
    proveedor_id: Mapped[object] = mapped_column(Integer, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False)
    monto: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    saldo: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_emision: Mapped[object] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[object] = mapped_column(Date, nullable=False)
    estado: Mapped[object] = mapped_column(Enum('Pendiente', 'Pagada', native_enum=True), nullable=False, server_default=text("'Pendiente'"))
    recepcion_id: Mapped[object] = mapped_column(Integer, ForeignKey("recepciones_compra.id", ondelete="RESTRICT"), nullable=True)
    orden = relationship("OrdenCompra", foreign_keys=[orden_id])
    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])
    recepcion = relationship("RecepcionCompra", foreign_keys=[recepcion_id])


class DesviacionFefo(Base):
    __tablename__ = "desviaciones_fefo"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    lote_sugerido_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    lote_vendido_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    motivo: Mapped[object] = mapped_column(String(255), nullable=True)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    venta = relationship("Venta", foreign_keys=[venta_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    lote_sugerido = relationship("Lote", foreign_keys=[lote_sugerido_id])
    lote_vendido = relationship("Lote", foreign_keys=[lote_vendido_id])
    producto = relationship("Producto", foreign_keys=[producto_id])


class DetalleOrdenCompra(Base):
    __tablename__ = "detalle_orden_compra"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    orden_id: Mapped[object] = mapped_column(Integer, ForeignKey("ordenes_compra.id", ondelete="CASCADE"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    numero_lote: Mapped[object] = mapped_column(String(80), nullable=True)
    fecha_vencimiento: Mapped[object] = mapped_column(Date, nullable=True)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="SET NULL"), nullable=True)
    orden = relationship("OrdenCompra", foreign_keys=[orden_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])


class DetalleVenta(Base):
    __tablename__ = "detalle_venta"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    venta = relationship("Venta", foreign_keys=[venta_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])


class EntradaDetalle(Base):
    __tablename__ = "entrada_detalle"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    entrada_id: Mapped[object] = mapped_column(Integer, ForeignKey("entradas_inventario.id", ondelete="RESTRICT"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    entrada = relationship("EntradaInventario", foreign_keys=[entrada_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])


class EntradaInventario(Base):
    __tablename__ = "entradas_inventario"
    __table_args__ = (UniqueConstraint('proveedor_id', 'numero_factura', name="uq_entradas_inventario_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    proveedor_id: Mapped[object] = mapped_column(Integer, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False)
    numero_factura: Mapped[object] = mapped_column(String(60), nullable=False)
    fecha_factura: Mapped[object] = mapped_column(Date, nullable=False)
    fecha_registro: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0.00'))
    observaciones: Mapped[object] = mapped_column(String(255), nullable=True)
    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class HistorialPrecio(Base):
    __tablename__ = "historial_precios"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    precio_anterior: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    precio_nuevo: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    producto = relationship("Producto", foreign_keys=[producto_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class LibroControlado(Base):
    __tablename__ = "libro_controlados"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    paciente_nombre: Mapped[object] = mapped_column(String(140), nullable=False)
    paciente_documento: Mapped[object] = mapped_column(String(40), nullable=True)
    medico_nombre: Mapped[object] = mapped_column(String(140), nullable=False)
    medico_codigo: Mapped[object] = mapped_column(String(40), nullable=True)
    numero_receta: Mapped[object] = mapped_column(String(60), nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    venta = relationship("Venta", foreign_keys=[venta_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (UniqueConstraint('producto_id', 'numero_lote', name="uq_lotes_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    numero_lote: Mapped[object] = mapped_column(String(80), nullable=False)
    fecha_fabricacion: Mapped[object] = mapped_column(Date, nullable=True)
    fecha_vencimiento: Mapped[object] = mapped_column(Date, nullable=False)
    cantidad_inicial: Mapped[object] = mapped_column(Integer, nullable=False)
    cantidad_actual: Mapped[object] = mapped_column(Integer, nullable=False)
    precio_compra: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    proveedor_id: Mapped[object] = mapped_column(Integer, ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True)
    fecha_recepcion: Mapped[object] = mapped_column(Date, nullable=False)
    estado: Mapped[object] = mapped_column(Enum('Disponible', 'Agotado', 'Cuarentena', 'Vencido', 'Retirado', native_enum=True), nullable=False, server_default=text("'Disponible'"))
    ubicacion: Mapped[object] = mapped_column(String(80), nullable=True)
    producto = relationship("Producto", foreign_keys=[producto_id])
    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])


class Marca(Base):
    __tablename__ = "marcas"
    __table_args__ = (UniqueConstraint('nombre', name="uq_marcas_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(120), nullable=False)
    laboratorio: Mapped[object] = mapped_column(String(160), nullable=True)
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))

class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    id: Mapped[object] = mapped_column(BigInteger, autoincrement=True, primary_key=True, nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="SET NULL"), nullable=True)
    tipo_movimiento: Mapped[object] = mapped_column(Enum('Entrada', 'Venta', 'Ajuste', 'Devolución', 'Merma', 'Vencimiento', 'Retiro', native_enum=True), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    motivo: Mapped[object] = mapped_column(String(255), nullable=False)
    referencia: Mapped[object] = mapped_column(String(100), nullable=True)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class NombreAlternativo(Base):
    __tablename__ = "nombres_alternativos"
    __table_args__ = (UniqueConstraint('producto_id', 'nombre', name="uq_nombres_alternativos_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    nombre: Mapped[object] = mapped_column(String(160), nullable=False)
    producto = relationship("Producto", foreign_keys=[producto_id])


class NotaCredito(Base):
    __tablename__ = "notas_credito"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    detalle_venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("detalle_venta.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    monto: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    motivo: Mapped[object] = mapped_column(String(255), nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    venta = relationship("Venta", foreign_keys=[venta_id])
    detalle_venta = relationship("DetalleVenta", foreign_keys=[detalle_venta_id])
    lote = relationship("Lote", foreign_keys=[lote_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class OrdenCompra(Base):
    __tablename__ = "ordenes_compra"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    proveedor_id: Mapped[object] = mapped_column(Integer, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    estado: Mapped[object] = mapped_column(Enum('Pendiente', 'Recibida', 'Anulada', native_enum=True), nullable=False, server_default=text("'Pendiente'"))
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    dias_credito: Mapped[object] = mapped_column(Integer, nullable=False, server_default=text('0'))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class PagoProveedor(Base):
    __tablename__ = "pagos_proveedor"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    cuenta_id: Mapped[object] = mapped_column(Integer, ForeignKey("cuentas_por_pagar.id", ondelete="RESTRICT"), nullable=False)
    monto: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    cuenta = relationship("CuentaPorPagar", foreign_keys=[cuenta_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class PagoVenta(Base):
    __tablename__ = "pagos_venta"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    metodo: Mapped[object] = mapped_column(Enum('Efectivo', 'Tarjeta', 'Transferencia', 'Crédito', native_enum=True), nullable=False)
    monto: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    monto_recibido: Mapped[object] = mapped_column(Numeric(12, 2), nullable=True)
    cambio: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    referencia: Mapped[object] = mapped_column(String(80), nullable=True)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    venta = relationship("Venta", foreign_keys=[venta_id])


class PrincipioActivo(Base):
    __tablename__ = "principios_activos"
    __table_args__ = (UniqueConstraint('nombre', name="uq_principios_activos_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[object] = mapped_column(String(255), nullable=True)
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))

class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = (UniqueConstraint('codigo', name="uq_productos_0"), UniqueConstraint('codigo_barras', name="uq_productos_1"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    codigo: Mapped[object] = mapped_column(String(50), nullable=False)
    codigo_barras: Mapped[object] = mapped_column(String(50), nullable=True)
    nombre_comercial: Mapped[object] = mapped_column(String(160), nullable=False)
    principio_activo_id: Mapped[object] = mapped_column(Integer, ForeignKey("principios_activos.id", ondelete="RESTRICT"), nullable=False)
    marca_id: Mapped[object] = mapped_column(Integer, ForeignKey("marcas.id", ondelete="SET NULL"), nullable=True)
    concentracion: Mapped[object] = mapped_column(Numeric(12, 3), nullable=True)
    unidad_concentracion: Mapped[object] = mapped_column(String(30), nullable=True)
    forma_farmaceutica: Mapped[object] = mapped_column(String(60), nullable=True)
    via_administracion: Mapped[object] = mapped_column(String(80), nullable=True)
    presentacion: Mapped[object] = mapped_column(String(100), nullable=True)
    cantidad_presentacion: Mapped[object] = mapped_column(Integer, nullable=False, server_default=text('1'))
    unidad_presentacion: Mapped[object] = mapped_column(String(40), nullable=False, server_default=text("'unidades'"))
    descripcion: Mapped[object] = mapped_column(String(500), nullable=True)
    categoria_id: Mapped[object] = mapped_column(Integer, ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False)
    precio_venta: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    stock_minimo: Mapped[object] = mapped_column(Integer, nullable=False, server_default=text('0'))
    requiere_receta: Mapped[object] = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    control_especial: Mapped[object] = mapped_column(Boolean, nullable=False, server_default=text('FALSE'))
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))
    fecha_creacion: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    registro_sanitario: Mapped[object] = mapped_column(String(60), nullable=True)
    categoria_dispensacion: Mapped[object] = mapped_column(Enum('Venta libre', 'Con receta', 'Receta retenida', 'Controlado', native_enum=True), nullable=False, server_default=text("'Venta libre'"))
    principio_activo = relationship("PrincipioActivo", foreign_keys=[principio_activo_id])
    marca = relationship("Marca", foreign_keys=[marca_id])
    categoria = relationship("Categoria", foreign_keys=[categoria_id])


class Proveedor(Base):
    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint('nombre', name="uq_proveedores_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(120), nullable=False)
    telefono: Mapped[object] = mapped_column(String(25), nullable=True)
    correo: Mapped[object] = mapped_column(String(120), nullable=True)
    direccion: Mapped[object] = mapped_column(String(255), nullable=True)
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))

    def as_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "telefono": self.telefono, "correo": self.correo,
                "direccion": self.direccion, "estado": self.estado}

class RecepcionDetalle(Base):
    __tablename__ = "recepcion_detalle"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    recepcion_id: Mapped[object] = mapped_column(Integer, ForeignKey("recepciones_compra.id", ondelete="RESTRICT"), nullable=False)
    detalle_orden_id: Mapped[object] = mapped_column(Integer, ForeignKey("detalle_orden_compra.id", ondelete="RESTRICT"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    lote_id: Mapped[object] = mapped_column(Integer, ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False)
    cantidad: Mapped[object] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    recepcion = relationship("RecepcionCompra", foreign_keys=[recepcion_id])
    detalle_orden = relationship("DetalleOrdenCompra", foreign_keys=[detalle_orden_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
    lote = relationship("Lote", foreign_keys=[lote_id])


class RecepcionCompra(Base):
    __tablename__ = "recepciones_compra"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    orden_id: Mapped[object] = mapped_column(Integer, ForeignKey("ordenes_compra.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    numero_documento: Mapped[object] = mapped_column(String(60), nullable=True)
    observaciones: Mapped[object] = mapped_column(String(255), nullable=True)
    orden = relationship("OrdenCompra", foreign_keys=[orden_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class RecetaVenta(Base):
    __tablename__ = "recetas_venta"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    venta_id: Mapped[object] = mapped_column(Integer, ForeignKey("ventas.id", ondelete="RESTRICT"), nullable=False)
    producto_id: Mapped[object] = mapped_column(Integer, ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    paciente: Mapped[object] = mapped_column(String(160), nullable=False)
    medico: Mapped[object] = mapped_column(String(160), nullable=False)
    numero_receta: Mapped[object] = mapped_column(String(60), nullable=False)
    venta = relationship("Venta", foreign_keys=[venta_id])
    producto = relationship("Producto", foreign_keys=[producto_id])


class TurnoCaja(Base):
    __tablename__ = "turnos_caja"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    apertura: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    monto_inicial: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    cierre: Mapped[object] = mapped_column(DateTime, nullable=True)
    efectivo_esperado: Mapped[object] = mapped_column(Numeric(12, 2), nullable=True)
    efectivo_contado: Mapped[object] = mapped_column(Numeric(12, 2), nullable=True)
    diferencia: Mapped[object] = mapped_column(Numeric(12, 2), nullable=True)
    estado: Mapped[object] = mapped_column(Enum('Abierto', 'Cerrado', native_enum=True), nullable=False, server_default=text("'Abierto'"))
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (UniqueConstraint('usuario', name="uq_usuarios_0"),)
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    nombre: Mapped[object] = mapped_column(String(120), nullable=False)
    usuario: Mapped[object] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[object] = mapped_column(String(255), nullable=False)
    rol: Mapped[object] = mapped_column(Enum('Administrador', 'Vendedor', native_enum=True), nullable=False)
    estado: Mapped[object] = mapped_column(Enum('Activo', 'Inactivo', native_enum=True), nullable=False, server_default=text("'Activo'"))
    fecha_creacion: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

class Venta(Base):
    __tablename__ = "ventas"
    id: Mapped[object] = mapped_column(Integer, autoincrement=True, primary_key=True, nullable=False)
    usuario_id: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    subtotal: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    descuento: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[object] = mapped_column(Enum('Completada', 'Anulada', native_enum=True), nullable=False, server_default=text("'Completada'"))
    cliente_id: Mapped[object] = mapped_column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    turno_id: Mapped[object] = mapped_column(Integer, ForeignKey("turnos_caja.id", ondelete="SET NULL"), nullable=True)
    metodo_pago: Mapped[object] = mapped_column(Enum('Efectivo', 'Tarjeta', 'Transferencia', 'Crédito', native_enum=True), nullable=False, server_default=text("'Efectivo'"))
    numero_factura: Mapped[object] = mapped_column(String(30), nullable=True)
    anulada_por: Mapped[object] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True)
    motivo_anulacion: Mapped[object] = mapped_column(String(255), nullable=True)
    monto_recibido: Mapped[object] = mapped_column(Numeric(12, 2), nullable=True)
    fecha_anulacion: Mapped[object] = mapped_column(Date, nullable=True)
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    cliente = relationship("Cliente", foreign_keys=[cliente_id])
    turno = relationship("TurnoCaja", foreign_keys=[turno_id])
    usuario_anulador = relationship("Usuario", foreign_keys=[anulada_por])
