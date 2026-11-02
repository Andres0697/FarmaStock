"""CRUD de categorías y proveedores con SQLAlchemy sobre SQLite temporal (no requiere MySQL)."""
import tempfile
import unittest
from pathlib import Path

try:
    from sqlalchemy import text
    from sqlalchemy.orm import configure_mappers
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
        self.orm = orm
        self.cat = CategoriaModel(None, orm=orm)
        self.prov = ProveedorModel(None, orm=orm)

    def tearDown(self):
        self.orm.engine.dispose()
        self.dir.cleanup()

    def test_todas_las_tablas_estan_mapeadas_por_orm(self):
        import models.orm_entidades
        configure_mappers()
        expected = {
            "usuarios", "categorias", "proveedores", "principios_activos", "marcas",
            "productos", "nombres_alternativos", "lotes", "ventas", "detalle_venta",
            "movimientos_inventario", "bitacora_auditoria", "desviaciones_fefo",
            "historial_precios", "libro_controlados", "ordenes_compra",
            "detalle_orden_compra", "cuentas_por_pagar", "pagos_proveedor",
            "clientes", "turnos_caja", "abonos_cliente", "notas_credito",
            "ajustes_inventario", "recetas_venta", "entradas_inventario",
            "entrada_detalle", "pagos_venta", "recepciones_compra", "recepcion_detalle",
        }
        self.assertEqual(set(Base.metadata.tables), expected)
        self.assertEqual(len(Base.metadata.tables), 30)
        self.assertGreater(sum(len(table.foreign_keys) for table in Base.metadata.tables.values()), 0)
        self.assertIn("registro_sanitario", Base.metadata.tables["productos"].columns)
        self.assertIn("categoria_dispensacion", Base.metadata.tables["productos"].columns)
        self.assertIn("fecha_anulacion", Base.metadata.tables["ventas"].columns)
        self.assertIn("usuario_anulador", dir(models.orm_entidades.Venta))

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
            con.execute(text("INSERT INTO principios_activos(nombre) VALUES ('Principio de prueba')"))
            principio_id = con.execute(text("SELECT id FROM principios_activos WHERE nombre='Principio de prueba'")).scalar_one()
            con.execute(text("""
                INSERT INTO productos(codigo, nombre_comercial, principio_activo_id, categoria_id, precio_venta)
                VALUES ('TEST-001', 'Producto de prueba', :principio_id, :categoria_id, 10.00)
            """), {"principio_id": principio_id, "categoria_id": cid})
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
            con.execute(text("INSERT INTO categorias(nombre) VALUES ('Categoría lote')"))
            con.execute(text("INSERT INTO principios_activos(nombre) VALUES ('Principio lote')"))
            principio_id = con.execute(text("SELECT id FROM principios_activos WHERE nombre='Principio lote'")).scalar_one()
            categoria_id = con.execute(text("SELECT id FROM categorias LIMIT 1")).scalar_one()
            con.execute(text("""
                INSERT INTO productos(codigo, nombre_comercial, principio_activo_id, categoria_id, precio_venta)
                VALUES ('TEST-002', 'Producto lote', :principio_id, :categoria_id, 10.00)
            """), {"principio_id": principio_id, "categoria_id": categoria_id})
            producto_id = con.execute(text("SELECT id FROM productos WHERE codigo='TEST-002'")).scalar_one()
            con.execute(text("""
                INSERT INTO lotes(producto_id, numero_lote, fecha_vencimiento, cantidad_inicial,
                                  cantidad_actual, proveedor_id, fecha_recepcion)
                VALUES (:producto_id, 'LOTE-TEST', '2027-12-31', 10, 10, :proveedor_id, '2026-01-01')
            """), {"producto_id": producto_id, "proveedor_id": pid})
        with self.assertRaisesRegex(ValueError, "en uso"):
            self.prov.remove(ADMIN, pid)


if __name__ == "__main__":
    unittest.main()
