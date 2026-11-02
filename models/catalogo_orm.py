"""Operaciones CRUD genéricas sobre catálogos con nombre único, usando SQLAlchemy."""
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from database.orm import OrmDatabase
from models.orm_entidades import ESTADOS
from utils.helpers import clean_text


class CatalogoOrm:
    """Base de CategoriaModel y ProveedorModel. Subclases definen `entity`, `label` y `usage_sql`."""

    entity = None
    label = "registro"
    usage_sql: tuple[str, ...] = ()  # consultas con :id que cuentan registros que usan el catálogo

    def __init__(self, db, orm=None):
        self.db = db
        self.orm = orm or OrmDatabase(db)

    # ---- lectura ----
    def list_all(self, search=""):
        search = clean_text(search)
        stmt = select(self.entity).order_by(self.entity.nombre)
        if search:
            stmt = stmt.where(self.entity.nombre.like(f"%{search}%"))
        with self.orm.session_scope() as session:
            return [row.as_dict() for row in session.scalars(stmt)]

    def active(self):
        stmt = select(self.entity.id, self.entity.nombre).where(self.entity.estado == "Activo").order_by(self.entity.nombre)
        with self.orm.session_scope() as session:
            return [{"id": i, "nombre": n} for i, n in session.execute(stmt)]

    def get(self, entity_id):
        with self.orm.session_scope() as session:
            row = session.get(self.entity, entity_id)
            return row.as_dict() if row else None

    # ---- escritura ----
    def _check_name(self, session, name, exclude_id=None):
        if not name:
            raise ValueError("El nombre es obligatorio.")
        stmt = select(self.entity.id).where(self.entity.nombre == name)
        if exclude_id is not None:
            stmt = stmt.where(self.entity.id != exclude_id)
        if session.scalar(stmt) is not None:
            raise ValueError(f"Ya existe {self.label} con el nombre «{name}».")

    @staticmethod
    def _check_estado(values):
        if values.get("estado") not in ESTADOS:
            raise ValueError("El estado debe ser Activo o Inactivo.")

    def _save(self, session):
        try:
            session.flush()
        except IntegrityError as exc:
            raise ValueError(f"No se pudo guardar {self.label}: datos duplicados o inválidos.") from exc

    def _create(self, values: dict) -> int:
        values = {k: (clean_text(v) or None) if isinstance(v, str) or v is None else v for k, v in values.items()}
        values["nombre"] = clean_text(values.get("nombre"))
        self._check_estado(values)
        with self.orm.session_scope() as session:
            self._check_name(session, values["nombre"])
            row = self.entity(**values)
            session.add(row)
            self._save(session)
            return row.id

    def _update(self, entity_id: int, values: dict) -> None:
        values = {k: (clean_text(v) or None) if isinstance(v, str) or v is None else v for k, v in values.items()}
        values["nombre"] = clean_text(values.get("nombre"))
        self._check_estado(values)
        with self.orm.session_scope() as session:
            row = session.get(self.entity, entity_id)
            if row is None:
                raise ValueError(f"{self.label.capitalize()} no existe.")
            self._check_name(session, values["nombre"], exclude_id=entity_id)
            for key, value in values.items():
                setattr(row, key, value)
            self._save(session)

    def delete(self, entity_id: int) -> None:
        """Elimina si nadie lo usa; si está en uso se pide marcarlo como Inactivo."""
        with self.orm.session_scope() as session:
            row = session.get(self.entity, entity_id)
            if row is None:
                raise ValueError(f"{self.label.capitalize()} no existe.")
            for sql in self.usage_sql:
                if session.scalar(text(sql), {"id": entity_id}):
                    raise ValueError(f"No se puede eliminar: {self.label} ya está en uso. Márquelo como Inactivo.")
            session.delete(row)
            self._save(session)
