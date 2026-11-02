"""Pruebas de integración contra MySQL REAL (base temporal `farmastock_test`).

Se omiten si no hay servidor. Para ejecutarlas:
    docker compose -f tests/docker-compose.yml up -d     # MySQL 8 en el puerto 3307
    set FARMASTOCK_TEST_DB=1  (PowerShell: $env:FARMASTOCK_TEST_DB="1")
    python -m unittest tests.test_integracion_mysql -v

Nunca tocan la base `farmastock` real: crean y borran `farmastock_test`.
"""
import os
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

try:
    import mysql.connector
    from database.connection import Database
except ImportError:  # sin el conector las pruebas se omiten
    mysql = None

from database import migrations, reconciliacion
from database.migrations import parse_script
from models.compra_model import CompraModel
from models.entrada_model import EntradaModel
from models.ajuste_model import AjusteModel
from models.inventario_model import InventarioModel
from models.producto_extra_model import ProductoExtraModel
from models.producto_model import ProductoModel
from models.venta_model import VentaModel

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = "farmastock_test"
ENABLED = os.getenv("FARMASTOCK_TEST_DB") == "1" and mysql is not None


def _server_config():
    return {
        "host": os.getenv("TEST_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("TEST_DB_PORT", "3307")),
        "user": os.getenv("TEST_DB_USER", "root"),
        "password": os.getenv("TEST_DB_PASSWORD", "test"),
    }


@unittest.skipUnless(ENABLED, "defina FARMASTOCK_TEST_DB=1 y levante MySQL de pruebas")
class IntegracionBase(unittest.TestCase):
    def setUp(self):
        script = (ROOT / "sql" / "instalacion_completa.sql").read_text(encoding="utf-8")
        script = re.sub(r"\bfarmastock\b", TEST_DB, script)
        con = mysql.connector.connect(**_server_config())
        cur = con.cursor()
        for _, statement in parse_script(script):
            cur.execute(statement)
        con.commit()
        cur.close()
        con.close()
        self.db = Database()
        self.db.config.update(_server_config(), database=TEST_DB)
        self.assertEqual(migrations.apply_pending(self.db), [f"{i:03d}" for i in range(1, 11)])

    def tearDown(self):
        con = mysql.connector.connect(**_server_config())
        con.cursor().execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        con.close()

    # utilidades
    def one(self, sql, params=()):
        with self.db.cursor() as (_, c):
            c.execute(sql, params)
            return c.fetchone()

    def product(self, code):
        return self.one("SELECT id FROM productos WHERE codigo=%s", (code,))["id"]

    def stock(self, code):
        return int(self.one("SELECT COALESCE(SUM(cantidad_actual),0) s FROM lotes l JOIN productos p ON p.id=l.producto_id WHERE p.codigo=%s", (code,))["s"])


class EsquemaTests(IntegracionBase):
    def test_migraciones_al_dia_y_repetibles(self):
        self.assertEqual(migrations.apply_pending(self.db), [])
        with self.db.cursor() as (con, c):  # simula una 007 a medias: debe poder repetirse
            c.execute("DELETE FROM schema_migraciones WHERE version IN ('007','008','009','010')")
            con.commit()
        self.assertEqual(migrations.apply_pending(self.db), ["007", "008", "009", "010"])

    def test_columnas_y_tablas_que_usa_el_codigo(self):
        for table, column in [("ventas", "monto_recibido"), ("ventas", "fecha_anulacion"),
                              ("desviaciones_fefo", "producto_id"), ("recetas_venta", "paciente"),
                              ("entradas_inventario", "numero_factura"), ("pagos_venta", "metodo")]:
            n = self.one("SELECT COUNT(*) n FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s",
                         (TEST_DB, table, column))["n"]
            self.assertEqual(n, 1, f"falta {table}.{column}")

    def test_conciliacion_inicial_sin_diferencias(self):
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_seed_repetido_no_duplica_movimientos(self):
        before = self.one("SELECT COUNT(*) n FROM movimientos_inventario")["n"]
        script = (ROOT / "sql" / "seed.sql").read_text(encoding="utf-8").replace("farmastock", TEST_DB)
        last = [s for _, s in parse_script(script) if "'SEED'" in s][-1]
        with self.db.cursor() as (con, c):
            c.execute(last)
            con.commit()
        self.assertEqual(self.one("SELECT COUNT(*) n FROM movimientos_inventario")["n"], before)


class VentasTests(IntegracionBase):
    def test_venta_efectivo_descuenta_lotes_y_registra_movimiento(self):
        pid, before = self.product("FAR-001"), self.stock("FAR-001")
        sale_id, subtotal, desc, total = VentaModel(self.db).create_sale(1, [{"producto_id": pid, "cantidad": 3}], 0, "Efectivo", 100)
        self.assertEqual(self.stock("FAR-001"), before - 3)
        self.assertEqual(total, round(3 * 4.50, 2))
        mov = self.one("SELECT SUM(cantidad) s FROM movimientos_inventario WHERE referencia=%s", (f"Venta #{sale_id}",))
        self.assertEqual(int(mov["s"]), -3)
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_venta_mayor_al_stock_no_deja_rastros(self):
        pid, before = self.product("FAR-001"), self.stock("FAR-001")
        with self.assertRaises(ValueError):
            VentaModel(self.db).create_sale(1, [{"producto_id": pid, "cantidad": before + 1}], 0, "Efectivo", 9999)
        self.assertEqual(self.stock("FAR-001"), before)
        self.assertEqual(self.one("SELECT COUNT(*) n FROM ventas")["n"], 0)

    def test_fefo_consume_primero_el_lote_que_vence_antes(self):
        pid = self.product("FAR-001")
        first = self.one("SELECT id,cantidad_actual FROM lotes WHERE producto_id=%s ORDER BY fecha_vencimiento LIMIT 1", (pid,))
        VentaModel(self.db).create_sale(1, [{"producto_id": pid, "cantidad": 2}], 0, "Efectivo", 100)
        after = self.one("SELECT cantidad_actual FROM lotes WHERE id=%s", (first["id"],))["cantidad_actual"]
        self.assertEqual(after, first["cantidad_actual"] - 2)

    def test_lote_elegido_distinto_registra_desviacion_con_producto(self):
        pid = self.product("FAR-001")
        lots = VentaModel(self.db).valid_lots(pid)
        self.assertGreaterEqual(len(lots), 2)
        VentaModel(self.db).create_sale(1, [{"producto_id": pid, "cantidad": 1, "lote_id": lots[1]["id"], "motivo_desviacion": "Pedido del cliente"}], 0, "Efectivo", 100)
        row = self.one("SELECT producto_id, lote_sugerido_id, lote_vendido_id FROM desviaciones_fefo")
        self.assertEqual((row["producto_id"], row["lote_sugerido_id"], row["lote_vendido_id"]), (pid, lots[0]["id"], lots[1]["id"]))

    def test_producto_con_receta_guarda_receta(self):
        pid = self.product("FAR-003")
        item = {"producto_id": pid, "cantidad": 1, "receta": {"paciente": "Ana", "medico": "Dr. Pérez", "numero_receta": "R-1"}}
        sale_id, *_ = VentaModel(self.db).create_sale(1, [item], 0, "Efectivo", 100, exigir_receta=True)
        self.assertEqual(self.one("SELECT paciente FROM recetas_venta WHERE venta_id=%s", (sale_id,))["paciente"], "Ana")

    def test_anulacion_devuelve_stock_y_conserva_la_venta(self):
        pid, before = self.product("FAR-001"), self.stock("FAR-001")
        model = VentaModel(self.db)
        sale_id, *_ = model.create_sale(1, [{"producto_id": pid, "cantidad": 4}], 0, "Efectivo", 100)
        model.cancel_sale(sale_id, 1, "Error de digitación")
        self.assertEqual(self.stock("FAR-001"), before)
        sale = model.get_sale(sale_id)
        self.assertEqual(sale["estado"], "Anulada")
        self.assertIsNotNone(sale["fecha_anulacion"])
        with self.assertRaises(ValueError):
            model.cancel_sale(sale_id, 1, "Segunda anulación")
        self.assertEqual(self.stock("FAR-001"), before)

    def test_vendedor_no_puede_anular(self):
        pid = self.product("FAR-001")
        model = VentaModel(self.db)
        sale_id, *_ = model.create_sale(1, [{"producto_id": pid, "cantidad": 1}], 0, "Efectivo", 100)
        with self.assertRaises(PermissionError):
            model.cancel_sale(sale_id, 2, "Intento de vendedor")


ADMIN = {"id": 1, "rol": "Administrador"}
VENDEDOR = {"id": 2, "rol": "Vendedor"}
REGENTE = {"id": 3, "rol": "Regente"}


class PermisosYLotesTests(IntegracionBase):
    def lot_data(self, code="FAR-001", lote="NUEVO-77", days=300, qty=5):
        return (self.product(code), lote, None, date.today() + timedelta(days=days), qty, 1.5, None, date.today(), "Estante X")

    def test_regente_puede_anular_y_vendedor_no(self):
        pid = self.product("FAR-001")
        model = VentaModel(self.db)
        a, *_ = model.create_sale(1, [{"producto_id": pid, "cantidad": 1}], 0, "Efectivo", 100)
        b, *_ = model.create_sale(1, [{"producto_id": pid, "cantidad": 1}], 0, "Efectivo", 100)
        model.cancel_sale(a, REGENTE["id"], "Anulación del regente")
        with self.assertRaises(PermissionError):
            model.cancel_sale(b, VENDEDOR["id"], "Intento de vendedor")

    def test_crear_lote_exige_permiso_y_valida(self):
        model = InventarioModel(self.db)
        with self.assertRaises(PermissionError):
            model.create_lot(self.lot_data(), VENDEDOR)
        with self.assertRaises(ValueError):
            model.create_lot(self.lot_data(days=-1), ADMIN)      # vencido
        with self.assertRaises(ValueError):
            model.create_lot(self.lot_data(qty=0), ADMIN)
        lot_id = model.create_lot(self.lot_data(), ADMIN)
        self.assertEqual(self.one("SELECT cantidad_actual c FROM lotes WHERE id=%s", (lot_id,))["c"], 5)
        with self.assertRaises(ValueError):                      # mismo lote: no se suma por esta vía
            model.create_lot(self.lot_data(), ADMIN)
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_lote_en_cuarentena_no_se_vende_y_el_ajuste_no_lo_libera(self):
        pid = self.product("FAR-001")
        lots = VentaModel(self.db).valid_lots(pid)
        inv, adj = InventarioModel(self.db), AjusteModel(self.db)
        inv.set_blocked(ADMIN, lots[0]["id"], True, "Revisión de calidad")
        self.assertNotIn(lots[0]["id"], [l["id"] for l in VentaModel(self.db).valid_lots(pid)])
        adj.apply(ADMIN, "Conteo físico", lots[0]["id"], 3, "Conteo durante la cuarentena")
        self.assertEqual(self.one("SELECT estado FROM lotes WHERE id=%s", (lots[0]["id"],))["estado"], "Cuarentena")
        with self.assertRaises(PermissionError):
            inv.set_blocked(VENDEDOR, lots[0]["id"], False, "Sin permiso")
        self.assertEqual(inv.set_blocked(ADMIN, lots[0]["id"], False, "Revisión aprobada"), "Disponible")
        self.assertIn(lots[0]["id"], [l["id"] for l in VentaModel(self.db).valid_lots(pid)])

    def test_ajuste_exige_permiso_y_motivo(self):
        lot = self.one("SELECT id FROM lotes ORDER BY id LIMIT 1")["id"]
        with self.assertRaises(PermissionError):
            AjusteModel(self.db).apply(VENDEDOR, "Merma", lot, 1, "Producto dañado")
        with self.assertRaises(ValueError):
            AjusteModel(self.db).apply(ADMIN, "Merma", lot, 1, "ok")
        AjusteModel(self.db).apply(ADMIN, "Merma", lot, 1, "Producto dañado")
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_kardex_trae_saldo_acumulado_por_lote(self):
        pid = self.product("FAR-001")
        VentaModel(self.db).create_sale(1, [{"producto_id": pid, "cantidad": 2}], 0, "Efectivo", 100)
        rows = InventarioModel(self.db).movements(limit=500)
        sale = next(r for r in rows if r["tipo_movimiento"] == "Venta")
        stock = self.one("SELECT cantidad_actual c FROM lotes WHERE numero_lote=%s", (sale["numero_lote"],))["c"]
        self.assertEqual(int(sale["saldo_lote"]), stock)

    def test_no_permite_producto_duplicado(self):
        full = ProductoModel(self.db).get(self.product("FAR-001"))
        data = ("FAR-DUP", None, full["nombre_comercial"], full["principio_activo_id"], full["marca_id"], full["concentracion"],
                full["unidad_concentracion"], full["forma_farmaceutica"], full["via_administracion"], full["presentacion"],
                full["cantidad_presentacion"], full["unidad_presentacion"], None, full["categoria_id"], full["precio_venta"],
                full["stock_minimo"], False, False, "Activo")
        with self.assertRaises(ValueError):
            ProductoModel(self.db).create(data)
        other = list(data); other[5] = 650  # otra concentración = producto distinto
        self.assertTrue(ProductoModel(self.db).create(tuple(other)))

    def test_sustitutos_marcan_equivalencia(self):
        rows = ProductoExtraModel(self.db).substitutes(self.product("FAR-001"))
        pediatrico = next(r for r in rows if r["codigo"] == "FAR-017")  # suspensión de 160 mg/5 mL
        self.assertEqual(pediatrico["equivalencia"], "Verificar")


class EntradasYConciliacionTests(IntegracionBase):
    def test_entrada_crea_lote_documento_y_movimiento(self):
        pid = self.product("FAR-001")
        provider = self.one("SELECT id FROM proveedores ORDER BY id LIMIT 1")["id"]
        line = {"producto_id": pid, "numero_lote": "NUEVO-01", "fecha_vencimiento": date.today() + timedelta(days=400), "cantidad": 10, "costo_unitario": 2.0}
        before = self.stock("FAR-001")
        entry_id, total = EntradaModel(self.db).create_entry(1, provider, "F-100", date.today(), [line])
        self.assertEqual(total, 20.0)
        self.assertEqual(self.stock("FAR-001"), before + 10)
        with self.assertRaises(ValueError):  # la misma factura no se registra dos veces
            EntradaModel(self.db).create_entry(1, provider, "F-100", date.today(), [line])
        self.assertEqual(self.stock("FAR-001"), before + 10)
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_conciliacion_detecta_y_corrige_sin_tocar_lotes(self):
        lote = self.one("SELECT id, producto_id, cantidad_actual FROM lotes ORDER BY id LIMIT 1")
        with self.db.cursor() as (con, c):  # simula la carga inicial duplicada
            c.execute("INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id) VALUES(%s,%s,'Entrada',%s,'dup','SEED',1)",
                      (lote["producto_id"], lote["id"], lote["cantidad_actual"]))
            con.commit()
        diffs = reconciliacion.discrepancias(self.db)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(int(diffs[0]["diferencia"]), -lote["cantidad_actual"])
        self.assertEqual(reconciliacion.aplicar(self.db, 1, "Conciliación de prueba"), 1)
        self.assertEqual(reconciliacion.discrepancias(self.db), [])
        self.assertEqual(self.one("SELECT cantidad_actual c FROM lotes WHERE id=%s", (lote["id"],))["c"], lote["cantidad_actual"])


class ComprasTests(IntegracionBase):
    ADMIN = {"id": 1, "rol": "Administrador"}

    def _order(self, qty=100, cost="5.00", credit=10):
        provider = self.one("SELECT id FROM proveedores WHERE estado='Activo' ORDER BY id LIMIT 1")["id"]
        pid = self.product("FAR-001")
        order_id = CompraModel(self.db).create_order(self.ADMIN, provider, [{"producto_id": pid, "cantidad": qty, "costo_unitario": cost}], credit)
        return order_id, pid, CompraModel(self.db).order_lines(order_id)[0]["id"]

    def _item(self, detail, lot, qty, days=400):
        return {"detalle_id": detail, "numero_lote": lot, "fecha_vencimiento": date.today() + timedelta(days=days), "cantidad": qty}

    def test_recepcion_parcial_dos_lotes_y_completar(self):
        model = CompraModel(self.db)
        order_id, pid, detail = self._order()
        before = self.stock("FAR-001")
        rec1 = model.receive(self.ADMIN, order_id, [self._item(detail, "C-A", 30), self._item(detail, "C-B", 20)], "REM-1")
        self.assertEqual(self.stock("FAR-001"), before + 50)
        self.assertEqual(self.one("SELECT estado FROM ordenes_compra WHERE id=%s", (order_id,))["estado"], "Parcial")
        self.assertEqual(model.order_lines(order_id)[0]["pendiente"], 50)
        cxp = self.one("SELECT monto, saldo, recepcion_id FROM cuentas_por_pagar WHERE recepcion_id=%s", (rec1,))
        self.assertEqual(float(cxp["monto"]), 250.0)
        model.receive(self.ADMIN, order_id, [self._item(detail, "C-A", 50)], "REM-2")  # suma al lote existente
        self.assertEqual(self.one("SELECT estado FROM ordenes_compra WHERE id=%s", (order_id,))["estado"], "Recibida")
        self.assertEqual(self.one("SELECT cantidad_actual c FROM lotes WHERE producto_id=%s AND numero_lote='C-A'", (pid,))["c"], 80)
        self.assertEqual(self.one("SELECT COUNT(*) n FROM cuentas_por_pagar WHERE orden_id=%s", (order_id,))["n"], 2)
        self.assertEqual(reconciliacion.discrepancias(self.db), [])

    def test_no_se_puede_recibir_de_mas_ni_documento_repetido_ni_orden_cerrada(self):
        model = CompraModel(self.db)
        order_id, _, detail = self._order(qty=10)
        before = self.stock("FAR-001")
        with self.assertRaises(ValueError):
            model.receive(self.ADMIN, order_id, [self._item(detail, "X1", 11)])
        model.receive(self.ADMIN, order_id, [self._item(detail, "X1", 4)], "DOC-1")
        with self.assertRaises(ValueError):
            model.receive(self.ADMIN, order_id, [self._item(detail, "X2", 1)], "DOC-1")
        with self.assertRaises(ValueError):
            model.receive(self.ADMIN, order_id, [self._item(detail, "X2", 7)], "DOC-2")  # solo faltan 6
        self.assertEqual(self.stock("FAR-001"), before + 4)  # lo fallido no dejó nada a medias
        model.close_order(self.ADMIN, order_id, "Proveedor no tenía más")
        with self.assertRaises(ValueError):
            model.receive(self.ADMIN, order_id, [self._item(detail, "X3", 1)])

    def test_anular_solo_pendiente_y_cerrar_solo_parcial(self):
        model = CompraModel(self.db)
        order_id, _, detail = self._order()
        with self.assertRaises(ValueError):
            model.cancel_order(self.ADMIN, order_id, "ok")  # motivo muy corto
        with self.assertRaises(ValueError):
            model.close_order(self.ADMIN, order_id, "Sin parciales aún")
        model.receive(self.ADMIN, order_id, [self._item(detail, "Y1", 5)])
        with self.assertRaises(ValueError):
            model.cancel_order(self.ADMIN, order_id, "Ya recibió parte")
        other, _, _ = self._order()
        model.cancel_order(self.ADMIN, other, "Pedido duplicado")
        self.assertEqual(self.one("SELECT estado FROM ordenes_compra WHERE id=%s", (other,))["estado"], "Anulada")

    def test_costo_promedio_ponderado_y_pago_con_decimal(self):
        model = CompraModel(self.db)
        first, pid, d1 = self._order(qty=10, cost="4.00")
        second, _, d2 = self._order(qty=10, cost="6.00")
        model.receive(self.ADMIN, first, [self._item(d1, "P-1", 10)])
        model.receive(self.ADMIN, second, [self._item(d2, "P-1", 10)])
        self.assertEqual(float(self.one("SELECT precio_compra p FROM lotes WHERE producto_id=%s AND numero_lote='P-1'", (pid,))["p"]), 5.0)
        account = self.one("SELECT id, saldo FROM cuentas_por_pagar ORDER BY id DESC LIMIT 1")
        with self.assertRaises(ValueError):
            model.pay(self.ADMIN, account["id"], "999999")
        model.pay(self.ADMIN, account["id"], account["saldo"])
        self.assertEqual(self.one("SELECT estado FROM cuentas_por_pagar WHERE id=%s", (account["id"],))["estado"], "Pagada")


if __name__ == "__main__":
    unittest.main()
