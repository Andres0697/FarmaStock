import tempfile
import unittest
from pathlib import Path

from utils.importers import ArchivoInvalido, parse_categorias_csv


def write(text, suffix=".csv", encoding="utf-8-sig"):
    handle = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding=encoding, newline="")
    handle.write(text)
    handle.close()
    return handle.name


class ImportCsvTests(unittest.TestCase):
    def test_valid_rows_and_semicolon_delimiter(self):
        path = write("Nombre;Descripcion;Estado\nAnalgésicos;Dolor;activo\nVitaminas;;Inactivo\n")
        rows, errors = parse_categorias_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual([r["nombre"] for r in rows], ["Analgésicos", "Vitaminas"])
        self.assertEqual(rows[1]["estado"], "Inactivo")

    def test_reports_bad_lines_without_aborting(self):
        path = write("nombre,estado\nA,Activo\n,Activo\nB,Raro\nA,Activo\n" + "X" * 101 + ",Activo\n")
        rows, errors = parse_categorias_csv(path)
        self.assertEqual([r["nombre"] for r in rows], ["A"])
        self.assertEqual(len(errors), 4)

    def test_rejects_wrong_extension_missing_file_and_missing_column(self):
        with self.assertRaises(ArchivoInvalido):
            parse_categorias_csv(write("nombre\nA\n", suffix=".txt"))
        with self.assertRaises(ArchivoInvalido):
            parse_categorias_csv(Path(tempfile.gettempdir()) / "no_existe_123.csv")
        with self.assertRaises(ArchivoInvalido):
            parse_categorias_csv(write("categoria\nA\n"))

    def test_rejects_non_utf8(self):
        path = Path(tempfile.gettempdir()) / "latin_farmastock.csv"
        path.write_bytes("nombre\nAnalgésicos\n".encode("latin-1"))
        with self.assertRaises(ArchivoInvalido):
            parse_categorias_csv(path)


if __name__ == "__main__":
    unittest.main()
