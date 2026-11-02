"""Pruebas SIN base de datos: clasificación de equivalencias farmacéuticas."""
import unittest
from decimal import Decimal

from models.producto_extra_model import classify_equivalence

BASE = {"concentracion": Decimal("500.000"), "unidad_concentracion": "mg",
        "forma_farmaceutica": "Tableta", "via_administracion": "Oral"}


class EquivalenciaTests(unittest.TestCase):
    def test_mismos_datos_es_equivalente(self):
        other = {**BASE, "concentracion": Decimal("500"), "forma_farmaceutica": "tableta "}
        self.assertEqual(classify_equivalence(BASE, other), "Equivalente")

    def test_distinta_concentracion_se_verifica(self):
        self.assertEqual(classify_equivalence(BASE, {**BASE, "concentracion": Decimal("160")}), "Verificar")

    def test_suspension_frente_a_tableta_se_verifica(self):
        other = {**BASE, "concentracion": Decimal("160"), "unidad_concentracion": "mg/5 mL", "forma_farmaceutica": "Suspensión"}
        self.assertEqual(classify_equivalence(BASE, other), "Verificar")

    def test_dato_faltante_no_se_asume_equivalente(self):
        self.assertEqual(classify_equivalence(BASE, {**BASE, "via_administracion": None}), "Verificar")
        self.assertEqual(classify_equivalence({**BASE, "concentracion": None}, BASE), "Verificar")

    def test_otra_via_se_verifica(self):
        self.assertEqual(classify_equivalence(BASE, {**BASE, "via_administracion": "Tópica"}), "Verificar")


if __name__ == "__main__":
    unittest.main()
