from sqlalchemy import select

from models.catalogo_orm import CatalogoOrm
from models.orm_entidades import Categoria
from utils.permisos import require


class CategoriaModel(CatalogoOrm):
    """Categorías con SQLAlchemy (CRUD completo + importación masiva)."""

    entity = Categoria
    label = "una categoría"
    usage_sql = ("SELECT COUNT(*) FROM productos WHERE categoria_id = :id",)

    def create(self, nombre, descripcion="", estado="Activo"):
        return self._create({"nombre": nombre, "descripcion": descripcion, "estado": estado})

    def update(self, categoria_id, nombre, descripcion, estado):
        self._update(categoria_id, {"nombre": nombre, "descripcion": descripcion, "estado": estado})

    def import_rows(self, user: dict, rows: list[dict]) -> dict:
        """Importa filas ya validadas {nombre, descripcion, estado}. Todo o nada; omite las que ya existen."""
        require(user, "gestionar_productos")
        created, skipped = 0, []
        with self.orm.session_scope() as session:
            existing = {n.lower() for n in session.scalars(select(Categoria.nombre))}
            for row in rows:
                key = row["nombre"].lower()
                if key in existing:
                    skipped.append(row["nombre"])
                    continue
                session.add(Categoria(nombre=row["nombre"], descripcion=row["descripcion"] or None, estado=row["estado"]))
                existing.add(key)
                created += 1
            self._save(session)
        return {"creadas": created, "omitidas": skipped}

    def remove(self, user: dict, entity_id: int) -> None:
        require(user, "gestionar_productos")
        self.delete(entity_id)
