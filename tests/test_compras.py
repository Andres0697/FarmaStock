"""Pruebas offline (sin MySQL) de las reglas de recepción de compras y lotes."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from models.compra_model import clean_order_lines, plan_receipt
from models.lotes_service import money, validate_lot_input, weighted_cost

FUTURE = date.today() + timedelta(days=365)


def lines():
    return [
        {"id": 1, "producto_id": 10, "cantidad": 100, "recibido": 0, "costo_unitario": Decimal("5.00"), "nombre_comercial": "Para"},
        {"id": 2, "producto_id": 11, "cantidad": 50, "recibido": 20, "costo_unitario": Decimal("8.50"), "nombre_comercial": "Amox"},
    ]


def item(detalle, lote="L1", qty=10, venc=FUTURE):
    return {"detalle_id": detalle, "numero_lote": lote, "fecha_vencimiento": venc, "cantidad": qty}


class PlanReceiptTests(unittest.TestCase):
    def test_partial_with_two_lots_same_line(self):
        plan = plan_receipt(lines(), [item(1, "A", 60), item(1, "B", 40)])
        self.assertEqual([p["cantidad"] for p in plan], [60, 40])
        self.assertEqual(plan[0]["costo_unitario"], Decimal("5.00"))
        self.assertEqual(plan[0]["producto_id"], 10)

    def test_cannot_exceed_pending(self):
        with self.assertRaisesRegex(ValueError, "solo faltan 30"):
            plan_receipt(lines(), [item(2, "A", 31)])

    def test_pending_considers_all_items_of_line(self):
        with self.assertRaises(ValueError):
            plan_receipt(lines(), [item(1, "A", 60), item(1, "B", 41)])

    def test_rejects_empty_and_foreign_line(self):
        with self.assertRaises(ValueError):
            plan_receipt(lines(), [])
        with self.assertRaisesRegex(ValueError, "no pertenece"):
            plan_receipt(lines(), [item(99)])

    def test_rejects_zero_negative_expired_and_missing_lot(self):
        for bad in (item(1, qty=0), item(1, qty=-3), item(1, venc=date.today()), item(1, lote="  ")):
            with self.assertRaises(ValueError):
                plan_receipt(lines(), [bad])

    def test_duplicate_lot_in_same_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "repetido"):
            plan_receipt(lines(), [item(1, "A", 10), item(1, "a", 10)])

    def test_cost_comes_from_order_not_from_input(self):
        bad = item(1, "A", 5); bad["costo_unitario"] = 0
        self.assertEqual(plan_receipt(lines(), [bad])[0]["costo_unitario"], Decimal("5.00"))


class LotRulesTests(unittest.TestCase):
    def test_weighted_cost(self):
        self.assertEqual(weighted_cost(100, "5.00", 100, "7.00"), Decimal("6.00"))
        self.assertEqual(weighted_cost(0, "0", 10, "3.333"), Decimal("3.33"))

    def test_money_is_decimal_two_places(self):
        self.assertEqual(money(0.1) + money(0.2), Decimal("0.30"))
        with self.assertRaises(ValueError):
            money("abc")

    def test_validate_lot_input(self):
        self.assertEqual(validate_lot_input(" ab  1 ", FUTURE, "5", 2), ("ab 1", 5, Decimal("2.00")))
        with self.assertRaises(ValueError):
            validate_lot_input("x" * 81, FUTURE, 1, 1)
        with self.assertRaises(ValueError):
            validate_lot_input("x", FUTURE, 1, -1)
        with self.assertRaises(ValueError):
            validate_lot_input("x", FUTURE, "abc", 1)


class OrderLinesTests(unittest.TestCase):
    def test_total_math_and_validation(self):
        clean = clean_order_lines([{"producto_id": 1, "cantidad": 3, "costo_unitario": 1.1}])
        self.assertEqual(clean[0]["cantidad"] * clean[0]["costo_unitario"], Decimal("3.30"))
        for bad in ([], [{"producto_id": 1, "cantidad": 0, "costo_unitario": 1}],
                    [{"producto_id": 1, "cantidad": 1, "costo_unitario": -1}]):
            with self.assertRaises(ValueError):
                clean_order_lines(bad)


if __name__ == "__main__":
    unittest.main()
