"""Capa ORM (SQLAlchemy) para los catálogos. Convive con el SQL directo del resto del sistema.

Usa el mismo servidor y las mismas tablas que `Database` (sin tablas nuevas) y el mismo
controlador `mysql-connector-python`. La interfaz nunca ve la sesión: los modelos abren una
sesión por operación con `session_scope()` (commit al terminar, rollback ante cualquier error).
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos ORM."""


_engines: dict = {}


def build_url(config: dict) -> URL:
    return URL.create(
        "mysql+mysqlconnector",
        username=config["user"], password=config["password"],
        host=config["host"], port=config["port"], database=config["database"],
        query={"charset": "utf8mb4"},
    )


class OrmDatabase:
    """Fábrica de sesiones. `url` permite usar otra base (por ejemplo SQLite en pruebas)."""

    def __init__(self, db=None, url=None):
        if url is None:
            url = build_url(db.config)
        key = str(url) if not isinstance(url, str) else url
        if key not in _engines:
            _engines[key] = create_engine(url, pool_pre_ping=True, future=True)
        self.engine = _engines[key]
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session_scope(self):
        """Sesión transaccional: commit si todo sale bien, rollback y relanzar si no."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
