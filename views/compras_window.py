from datetime import date

from PySide6.QtCore import QDate, QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QSpinBox,
                               QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from models.compra_model import CompraModel
from models.proveedor_model import ProveedorModel
from models.producto_model import ProductoModel
from utils.helpers import format_currency
from utils.messages import error, info, warning
from utils.ui import StatCard, button, fill_table, make_table, page_header, colored_item


class OrdenDialog(QDialog):
    """Nueva orden de compra: proveedor + líneas (producto, cantidad, costo)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva orden de compra"); self.resize(640, 460)
        self.lines: list[dict] = []
        lay = QVBoxLayout(self)
        top = QFormLayout()
        self.provider = QComboBox(); self.credit = QSpinBox(); self.credit.setRange(0, 365); self.credit.setSuffix(" días de crédito")
        top.addRow("Proveedor *", self.provider); top.addRow("Crédito", self.credit); lay.addLayout(top)
        add_row = QHBoxLayout()
        self.product, self.qty, self.cost = QComboBox(), QSpinBox(), QDoubleSpinBox()
        self.qty.setRange(1, 1_000_000); self.cost.setRange(0, 10_000_000); self.cost.setPrefix("C$ "); self.cost.setDecimals(2)
        for w in (self.product, self.qty, self.cost):
            add_row.addWidget(w)
        add_row.addWidget(button("Agregar", "secondary", self.add_line)); lay.addLayout(add_row)
        self.table = make_table(["Producto", "Cantidad", "Costo", "Subtotal"]); lay.addWidget(self.table, 1)
        self.total = QLabel("Total: C$ 0.00"); self.total.setObjectName("totalLabel"); lay.addWidget(self.total)
        row = QHBoxLayout(); row.addWidget(button("Crear orden", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject)); lay.addLayout(row)
        for p in ProveedorModel(db).active():
            self.provider.addItem(p["nombre"], p["id"])
        with db.cursor() as (_, c):
            c.execute("SELECT id,nombre_comercial FROM productos WHERE estado='Activo' ORDER BY nombre_comercial"); rows = c.fetchall()
        for p in rows:
            self.product.addItem(p["nombre_comercial"], p["id"])

    def add_line(self) -> None:
        if self.product.currentData() is None:
            return
        self.lines.append({"producto_id": self.product.currentData(), "nombre": self.product.currentText(), "cantidad": self.qty.value(), "costo_unitario": self.cost.value()})
        fill_table(self.table, [[l["nombre"], l["cantidad"], format_currency(l["costo_unitario"]), format_currency(l["cantidad"] * l["costo_unitario"])] for l in self.lines])
        self.total.setText(f"Total: {format_currency(sum(l['cantidad'] * l['costo_unitario'] for l in self.lines))}")

    def validate(self) -> None:
        if not self.lines or self.provider.currentData() is None:
            warning(self, "Validación", "Selecciona un proveedor y agrega al menos un producto."); return
        self.accept()


class RecepcionDialog(QDialog):
    """Recepción parcial o total: por línea se indica cantidad, lote y vencimiento.

    Una línea puede recibirse en varios lotes ("Agregar otro lote"). Las filas con
    cantidad 0 se ignoran. La validación definitiva la hace CompraModel.receive.
    """
    COL_PRODUCTO, COL_PENDIENTE, COL_CANTIDAD, COL_LOTE, COL_VENCE = range(5)

    def __init__(self, lines: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recepción de mercadería"); self.resize(860, 480)
        self.lines = {l["id"]: l for l in lines if l["pendiente"] > 0}
        self.rows: list[dict] = []
        lay = QVBoxLayout(self)
        head = QFormLayout()
        self.document = QLineEdit(); self.document.setMaxLength(60); self.document.setPlaceholderText("Factura o remisión del proveedor (opcional)")
        self.notes = QLineEdit(); self.notes.setMaxLength(255); self.notes.setPlaceholderText("Observaciones (opcional)")
        head.addRow("Documento", self.document); head.addRow("Observaciones", self.notes); lay.addLayout(head)
        self.table = make_table(["Producto", "Pendiente", "Cantidad a recibir", "Lote", "Vencimiento"])
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        lay.addWidget(self.table, 1)
        hint = QLabel("Deja la cantidad en 0 en lo que no llegó. Para repartir un producto en varios lotes usa «Agregar otro lote».")
        hint.setWordWrap(True); lay.addWidget(hint)
        row = QHBoxLayout()
        row.addWidget(button("Agregar otro lote", "secondary", self.add_lot_row)); row.addStretch()
        row.addWidget(button("Registrar recepción", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject))
        lay.addLayout(row)
        for line in self.lines.values():
            self._add_row(line)

    def _add_row(self, line: dict, at: int | None = None, default_qty: int | None = None) -> None:
        index = self.table.rowCount() if at is None else at
        self.table.insertRow(index)
        qty = QSpinBox(); qty.setRange(0, line["pendiente"]); qty.setValue(line["pendiente"] if default_qty is None else default_qty)
        lot = QLineEdit(); lot.setMaxLength(80); lot.setPlaceholderText("N.º de lote")
        lot.setValidator(QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9 ._/\-]*"), lot))
        exp = QDateEdit(QDate.currentDate().addMonths(12)); exp.setCalendarPopup(True); exp.setMinimumDate(QDate.currentDate().addDays(1))
        self.table.setItem(index, self.COL_PRODUCTO, QTableWidgetItem(line["nombre_comercial"]))
        self.table.setItem(index, self.COL_PENDIENTE, QTableWidgetItem(str(line["pendiente"])))
        self.table.setCellWidget(index, self.COL_CANTIDAD, qty)
        self.table.setCellWidget(index, self.COL_LOTE, lot)
        self.table.setCellWidget(index, self.COL_VENCE, exp)
        self.rows.insert(index, {"line": line, "qty": qty, "lot": lot, "exp": exp})

    def add_lot_row(self) -> None:
        index = self.table.currentRow()
        if index < 0:
            warning(self, "Recepción", "Selecciona la fila del producto al que quieres agregar otro lote."); return
        self._add_row(self.rows[index]["line"], index + 1, default_qty=0)

    def validate(self) -> None:
        picked = [r for r in self.rows if r["qty"].value() > 0]
        if not picked:
            warning(self, "Validación", "Indica al menos una cantidad recibida."); return
        if any(not r["lot"].text().strip() for r in picked):
            warning(self, "Validación", "Cada cantidad recibida necesita número de lote."); return
        totals: dict[int, int] = {}
        for r in picked:
            totals[r["line"]["id"]] = totals.get(r["line"]["id"], 0) + r["qty"].value()
        for line_id, total in totals.items():
            if total > self.lines[line_id]["pendiente"]:
                warning(self, "Validación", f"{self.lines[line_id]['nombre_comercial']}: recibes {total} u. y solo faltan {self.lines[line_id]['pendiente']}."); return
        self.accept()

    def items(self) -> list[dict]:
        return [{"detalle_id": r["line"]["id"], "numero_lote": r["lot"].text().strip(), "fecha_vencimiento": r["exp"].date().toPython(),
                 "cantidad": r["qty"].value()} for r in self.rows if r["qty"].value() > 0]


class ComprasPage(QWidget):
    """Órdenes de compra, cuentas por pagar y reabastecimiento sugerido."""
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.db, self.user, self.model = db, user, CompraModel(db)
        self.order_rows, self.payable_rows = [], []
        lay = QVBoxLayout(self)
        lay.addLayout(page_header("Compras y proveedores", button("＋ Nueva orden", "primary", self.new_order), button("Recibir mercadería", "secondary", self.receive),
                                  button("Cerrar con faltante", "secondary", self.close_partial), button("Anular orden", "danger", self.cancel_order),
                                  button("Registrar pago", "secondary", self.pay)))
        self.due = StatCard("Cuentas por pagar", "#c62828"); lay.addWidget(self.due)
        tabs = QTabWidget(); lay.addWidget(tabs, 1)
        self.orders = make_table(["Orden", "Fecha", "Proveedor", "Total", "Pedido (u.)", "Recibido (u.)", "Estado"])
        self.payables = make_table(["Cuenta", "Orden", "Recepción", "Proveedor", "Monto", "Saldo", "Emisión", "Vence", "Días", "Estado"])
        self.receptions = make_table(["Recepción", "Orden", "Fecha", "Usuario", "Documento", "Producto", "Lote", "Vence", "Cantidad", "Costo"])
        self.restock = make_table(["Código", "Producto", "Stock", "Mínimo", "Vendido 30 d", "Rotación/día", "Sugerido pedir"])
        for table, name in ((self.orders, "Órdenes de compra"), (self.receptions, "Recepciones"), (self.payables, "Cuentas por pagar"), (self.restock, "Reabastecimiento sugerido")):
            tabs.addTab(table, name)

    def refresh(self) -> None:
        try:
            self.order_rows, self.payable_rows = self.model.orders(), self.model.payables()
            fill_table(self.orders, [[r["id"], r["fecha"], r["proveedor"], format_currency(r["total"]), r["pedido"], r["recibido"], r["estado"]] for r in self.order_rows])
            fill_table(self.payables, [[r["id"], r["orden_id"], r["recepcion_id"] or "—", r["proveedor"], format_currency(r["monto"]), format_currency(r["saldo"]), r["fecha_emision"], r["fecha_vencimiento"],
                                        colored_item(r["dias"], r["dias"]) if r["estado"] == "Pendiente" else "—", r["estado"]] for r in self.payable_rows])
            fill_table(self.receptions, [[r["recepcion_id"], r["orden_id"], r["fecha"], r["usuario"], r["numero_documento"], r["nombre_comercial"], r["numero_lote"],
                                          r["fecha_vencimiento"], r["cantidad"], format_currency(r["costo_unitario"])] for r in self.model.receptions()])
            pending = sum(float(r["saldo"]) for r in self.payable_rows if r["estado"] == "Pendiente")
            self.due.set_value(format_currency(pending), "Saldo pendiente con proveedores")
            fill_table(self.restock, [[r["codigo"], r["nombre_comercial"], r["stock"], r["stock_minimo"], r["vendido"], r["rotacion_diaria"], r["sugerido"]] for r in self.model.restock_suggestions()])
        except Exception as exc:
            error(self, "Compras", f"No se pudieron cargar las compras.\n{exc}")

    def new_order(self) -> None:
        dialog = OrdenDialog(self.db, self)
        if dialog.exec():
            try:
                order_id = self.model.create_order(self.user, dialog.provider.currentData(), dialog.lines, dialog.credit.value())
                info(self, "Compras", f"Orden #{order_id} creada."); self.refresh()
            except Exception as exc:
                error(self, "Compras", str(exc))

    def _selected_order(self, allowed: tuple[str, ...], hint: str):
        r = self.orders.currentRow()
        if r < 0 or self.order_rows[r]["estado"] not in allowed:
            warning(self, "Compras", hint); return None
        return self.order_rows[r]

    def receive(self) -> None:
        order = self._selected_order(("Pendiente", "Parcial"), "Selecciona una orden pendiente o parcial.")
        if not order:
            return
        dialog = RecepcionDialog(self.model.order_lines(order["id"]), self)
        if dialog.exec():
            try:
                self.model.receive(self.user, order["id"], dialog.items(), dialog.document.text(), dialog.notes.text())
                info(self, "Compras", "Recepción registrada: lotes actualizados y cuenta por pagar generada."); self.refresh(); self.data_changed.emit()
            except Exception as exc:
                error(self, "Compras", str(exc))

    def _ask_reason(self, title: str, label: str) -> str | None:
        text, ok = QInputDialog.getText(self, title, label)
        return text.strip() if ok else None

    def cancel_order(self) -> None:
        order = self._selected_order(("Pendiente",), "Selecciona una orden pendiente sin recepciones.")
        reason = self._ask_reason("Anular orden", f"Motivo para anular la orden #{order['id']}:") if order else None
        if reason is not None:
            try:
                self.model.cancel_order(self.user, order["id"], reason); self.refresh()
            except Exception as exc:
                warning(self, "Compras", str(exc))

    def close_partial(self) -> None:
        order = self._selected_order(("Parcial",), "Selecciona una orden parcialmente recibida.")
        reason = self._ask_reason("Cerrar con faltante", f"Motivo del faltante en la orden #{order['id']}:") if order else None
        if reason is not None:
            try:
                self.model.close_order(self.user, order["id"], reason); self.refresh()
            except Exception as exc:
                warning(self, "Compras", str(exc))

    def pay(self) -> None:
        r = self.payables.currentRow()
        if r < 0 or self.payable_rows[r]["estado"] != "Pendiente":
            warning(self, "Compras", "Selecciona una cuenta pendiente en la pestaña de cuentas por pagar."); return
        row = self.payable_rows[r]
        amount, ok = QInputDialog.getDouble(self, "Pago a proveedor", f"Saldo: {format_currency(row['saldo'])}\nMonto a pagar:", float(row["saldo"]), 0, 100_000_000, 2)
        if ok:
            try:
                self.model.pay(self.user, row["id"], amount); self.refresh()
            except Exception as exc:
                warning(self, "Compras", str(exc))
