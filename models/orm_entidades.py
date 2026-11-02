"""Modelos declarativos (SQLAlchemy) de las tablas `categorias` y `proveedores`."""
from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.orm import Base

ESTADOS = ("Activo", "Inactivo")


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(Enum(*ESTADOS, name="estado_categoria"), nullable=False, default="Activo")

    def as_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "descripcion": self.descripcion, "estado": self.estado}


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(25))
    correo: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(Enum(*ESTADOS, name="estado_proveedor"), nullable=False, default="Activo")

    def as_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "telefono": self.telefono, "correo": self.correo,
                "direccion": self.direccion, "estado": self.estado}
