"""Pruebas SIN base de datos: analizador de scripts y reglas del ejecutor de migraciones."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from database import migrations
from database.migrations import MigrationError, parse_script


class ParseScriptTests(unittest.TestCase):
    def test_divide_por_punto_y_coma_y_quita_comentarios(self):
        parts = parse_script("-- comentario\nCREATE TABLE a (id INT);\nINSERT INTO a VALUES (1); -- fin\n")
        self.assertEqual([s for _, s in parts], ["CREATE TABLE a (id INT)", "INSERT INTO a VALUES (1)"])

    def test_punto_y_coma_dentro_de_texto_no_corta(self):
        parts = parse_script("INSERT INTO t(x) VALUES ('a;b'), (\"c;d\"), ('it''s;ok');")
        self.assertEqual(len(parts), 1)
        self.assertIn("'a;b'", parts[0][1])
        self.assertIn("'it''s;ok'", parts[0][1])

    def test_comentario_dentro_de_texto_se_conserva(self):
        parts = parse_script("INSERT INTO t(x) VALUES ('-- no es comentario');")
        self.assertIn("-- no es comentario", parts[0][1])

    def test_directiva_skip_if_se_asocia_a_la_siguiente_sentencia(self):
        parts = parse_script("-- @skip_if: SELECT COUNT(*) FROM x WHERE a=1\nALTER TABLE t ADD COLUMN c INT;\nSELECT 2;")
        self.assertEqual(parts[0][0], "SELECT COUNT(*) FROM x WHERE a=1")
        self.assertIsNone(parts[1][0])

    def test_sentencia_final_sin_punto_y_coma(self):
        self.assertEqual(len(parse_script("SELECT 1;\nSELECT 2")), 2)


class MigrationFilesTests(unittest.TestCase):
    def test_versiones_unicas_y_ordenadas(self):
        files = migrations.up_files()
        versions = [p.stem.split("_")[0] for p in files]
        self.assertEqual(versions, sorted(versions))
        self.assertEqual(len(versions), len(set(versions)))

    def test_cada_migracion_tiene_su_down(self):
        for path in migrations.up_files():
            down = path.with_name(path.stem + "_down.sql")
            self.assertTrue(down.exists(), f"falta {down.name}")

    def test_todas_las_migraciones_se_analizan(self):
        for path in migrations.up_files():
            parts = parse_script(path.read_text(encoding="utf-8"))
            self.assertTrue(parts, f"{path.name} no tiene sentencias")
            for _, statement in parts:
                self.assertFalse(statement.startswith("--"), f"comentario suelto en {path.name}")

    def test_obsoletas_olvidadas_en_la_carpeta_se_ignoran(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("001_roles_auditoria_desviaciones", "001_ventas_pago_anulacion_desviaciones",
                         "002_entradas_mercaderia", "002_productos_regulatorio"):
                (Path(tmp) / f"{name}.sql").write_text("SELECT 1;")
            with mock.patch.object(migrations, "MIGRATIONS_DIR", Path(tmp)):
                names = [p.stem for p in migrations.up_files()]
        self.assertEqual(names, ["001_roles_auditoria_desviaciones", "002_productos_regulatorio"])

    def test_version_repetida_lanza_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "001_a.sql").write_text("SELECT 1;")
            (Path(tmp) / "001_b.sql").write_text("SELECT 1;")
            with mock.patch.object(migrations, "MIGRATIONS_DIR", Path(tmp)):
                with self.assertRaises(MigrationError):
                    migrations.up_files()


class FakeCursor:
    def __init__(self, log, skip_value=0):
        self.log, self.skip_value, self._last = log, skip_value, None

    def execute(self, sql, params=None):
        self.log.append(sql.strip())
        self._last = sql

    def fetchone(self):
        return {"n": self.skip_value}


class FakeDB:
    def __init__(self, applied=(), skip_value=0):
        self.log, self.applied, self.skip_value = [], set(applied), skip_value
        self.committed = 0

    def cursor(self, dictionary=True):
        db = self

        class Ctx:
            def __enter__(self_inner):
                cur = FakeCursor(db.log, db.skip_value)
                orig = cur.execute

                def execute(sql, params=None):
                    orig(sql, params)
                    if sql.strip().startswith("INSERT INTO schema_migraciones"):
                        db.applied.add(params[0])
                cur.execute = execute
                cur.fetchall = lambda: (
                    [{"version": v} for v in sorted(db.applied)]
                    if cur._last.strip().startswith("SELECT version")
                    else [{"n": db.skip_value}]
                )
                con = mock.Mock()
                con.commit = lambda: setattr(db, "committed", db.committed + 1)
                return con, cur

            def __exit__(self_inner, *a):
                return False
        return Ctx()


class ApplyPendingTests(unittest.TestCase):
    def test_solo_aplica_las_pendientes_y_registra_cada_version(self):
        db = FakeDB(applied={"001", "002", "003", "004", "005", "006"})
        applied = migrations.apply_pending(db)
        self.assertEqual(applied, ["007", "008", "009", "010"])
        self.assertTrue({"007", "008", "009"} <= db.applied)

    def test_al_dia_no_hace_nada(self):
        db = FakeDB(applied={f"{i:03d}" for i in range(1, 11)})
        self.assertEqual(migrations.apply_pending(db), [])

    def test_skip_if_omite_sentencias_ya_aplicadas(self):
        db = FakeDB(applied={f"{i:03d}" for i in range(1, 7)} | {"008", "009", "010"}, skip_value=1)
        migrations.apply_pending(db)
        self.assertFalse([q for q in db.log if q.startswith("ALTER TABLE ventas ADD COLUMN")])
        self.assertTrue([q for q in db.log if q.startswith("CREATE TABLE IF NOT EXISTS recetas_venta")])


if __name__ == "__main__":
    unittest.main()
