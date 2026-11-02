"""CRUD de categorías y proveedores con SQLAlchemy sobre SQLite temporal (no requiere MySQL)."""
import tempfile
import unittest
from pathlib import Path

try:
    from sqlalchemy import text
    from database.orm import Base, OrmDatabase
    import models.orm_entidades  # noqa: F401  (registra los modelos)
    from models.categoria_model import CategoriaModel
    from models.proveedor_model import ProveedorModel
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

ADMIN = {"id": 1, "rol": "Administrador"}
VENDEDOR = {"id": 2, "rol": "Vendedor"}


@unittest.skipUnless(HAS_SQLALCHEMY, "SQLAlchemy no está instalado")
class OrmCatalogosTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        orm = OrmDatabase(url=f"sqlite:///{Path(self.dir.name) / 'test.db'}")
        Base.metadata.create_all(orm.engine)
        with orm.engine.begin() as con:
            con.execute(text("CREATE TABLE productos (id INTEGER PRIMARY KEY, categoria_id INTEGER)"))
            for table in ("lotes", "ordenes_compra", "entradas_inventario"):
                con.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, proveedor_id INTEGER)"))
        self.orm = orm
        self.cat = CategoriaModel(None, orm=orm)
        self.prov = ProveedorModel(None, orm=orm)

    def tearDown(self):
        self.orm.engine.dispose()
        self.dir.cleanup()

    def test_categoria_crud(self):
        cid = self.cat.create("  Analgésicos ", "Dolor", "Activo")
        self.assertEqual(self.cat.get(cid)["nombre"], "Analgésicos")
        self.cat.update(cid, "Analgesicos y antipiréticos", "", "Inactivo")
        row = self.cat.get(cid)
        self.assertEqual((row["estado"], row["descripcion"]), ("Inactivo", None))
        self.assertEqual(self.cat.active(), [])
        self.assertEqual(len(self.cat.list_all("antipir")), 1)
        self.cat.remove(ADMIN, cid)
        self.assertIsNone(self.cat.get(cid))

    def test_nombre_obligatorio_y_unico(self):
        self.cat.create("Vitaminas")
        with self.assertRaises(ValueError):
            self.cat.create("Vitaminas")
        with self.assertRaises(ValueError):
            self.cat.create("   ")
        other = self.cat.create("Jarabes")
        with self.assertRaises(ValueError):
            self.cat.update(other, "Vitaminas", "", "Activo")

    def test_no_elimina_si_esta_en_uso_y_exige_permiso(self):
        cid = self.cat.create("Antibióticos")
        with self.orm.engine.begin() as con:
            con.execute(text("INSERT INTO productos(categoria_id) VALUES (:c)"), {"c": cid})
        with self.assertRaisesRegex(ValueError, "en uso"):
            self.cat.remove(ADMIN, cid)
        with self.assertRaises(PermissionError):
            self.cat.remove(VENDEDOR, cid)

    def test_rollback_si_falla_a_mitad(self):
        with self.assertRaises(RuntimeError):
            with self.orm.session_scope() as session:
                session.add(models.orm_entidades.Categoria(nombre="Temporal", estado="Activo"))
                session.flush()
                raise RuntimeError("falla simulada")
        self.assertEqual(self.cat.list_all(), [])

    def test_importacion_masiva_omite_existentes_y_exige_permiso(self):
        self.cat.create("Vitaminas")
        rows = [{"nombre": "vitaminas", "descripcion": "", "estado": "Activo"},
                {"nombre": "Jarabes", "descripcion": "Tos", "estado": "Activo"}]
        with self.assertRaises(PermissionError):
            self.cat.import_rows(VENDEDOR, rows)
        result = self.cat.import_rows(ADMIN, rows)
        self.assertEqual(result["creadas"], 1)
        self.assertEqual(result["omitidas"], ["vitaminas"])

    def test_proveedor_crud_y_bloqueo_por_uso(self):
        pid = self.prov.create(("Droguería Norte", "8888-8888", "a@b.com", "Managua", "Activo"))
        self.prov.update(pid, ("Droguería Norte S.A.", "", "a@b.com", "León", "Activo"))
        self.assertEqual(self.prov.get(pid)["direccion"], "León")
        with self.orm.engine.begin() as con:
            con.execute(text("INSERT INTO lotes(proveedor_id) VALUES (:p)"), {"p": pid})
        with self.assertRaisesRegex(ValueError, "en uso"):
            self.prov.remove(ADMIN, pid)


if __name__ == "__main__":
    unittest.main()
