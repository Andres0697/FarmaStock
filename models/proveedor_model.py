from models.catalogo_orm import CatalogoOrm
from models.orm_entidades import Proveedor
from utils.permisos import require


class ProveedorModel(CatalogoOrm):
    """Proveedores con SQLAlchemy (CRUD completo). `data` = (nombre, teléfono, correo, dirección, estado)."""

    entity = Proveedor
    label = "un proveedor"
    usage_sql = (
        "SELECT COUNT(*) FROM lotes WHERE proveedor_id = :id",
        "SELECT COUNT(*) FROM ordenes_compra WHERE proveedor_id = :id",
        "SELECT COUNT(*) FROM entradas_inventario WHERE proveedor_id = :id",
    )

    @staticmethod
    def _values(data):
        nombre, telefono, correo, direccion, estado = data
        return {"nombre": nombre, "telefono": telefono, "correo": correo, "direccion": direccion, "estado": estado}

    def create(self, data):
        return self._create(self._values(data))

    def update(self, provider_id, data):
        self._update(provider_id, self._values(data))

    def remove(self, user: dict, entity_id: int) -> None:
        require(user, "gestionar_productos")
        self.delete(entity_id)
