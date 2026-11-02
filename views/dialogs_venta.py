"""Diálogos de apoyo a la venta: receta, forma de pago, sustitutos, FEFO y devoluciones."""
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout)

from utils.helpers import clean_text, format_currency
from utils.messages import warning
from utils.ui import button, fill_table, make_table


class RecetaDialog(QDialog):
    """Datos de receta para medicamentos de receta retenida y controlados."""

    def __init__(self, product_name: str, quantity: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datos de receta"); self.resize(420, 300)
        form = QFormLayout(self)
        form.addRow(QLabel(f"<b>{product_name}</b> · cantidad: {quantity}"))
        self.patient, self.document, self.doctor, self.doctor_code, self.number = (QLineEdit() for _ in range(5))
        for label, w in (("Paciente *", self.patient), ("Cédula del paciente", self.document), ("Médico *", self.doctor),
                         ("Código MINSA del médico", self.doctor_code), ("N.º de receta *", self.number)):
            form.addRow(label, w)
        row = QHBoxLayout(); row.addWidget(button("Aceptar", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject)); form.addRow(row)

    def validate(self) -> None:
        if not all(clean_text(w.text()) for w in (self.patient, self.doctor, self.number)):
            warning(self, "Validación", "Paciente, médico y número de receta son obligatorios."); return
        self.accept()

    def data(self) -> dict:
        return {"paciente": clean_text(self.patient.text()), "documento": clean_text(self.document.text()) or None, "medico": clean_text(self.doctor.text()),
                "codigo_medico": clean_text(self.doctor_code.text()) or None, "numero": clean_text(self.number.text())}


class PagoDialog(QDialog):
    """Forma de pago y cliente (obligatorio a crédito)."""

    def __init__(self, total: float, clients: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cobro"); form = QFormLayout(self)
        form.addRow(QLabel(f"<b>Total a cobrar: {format_currency(total)}</b>"))
        self.method = QComboBox(); self.method.addItems(["Efectivo", "Tarjeta", "Transferencia", "Crédito"])
        self.client = QComboBox(); self.client.addItem("Consumidor final", None)
        for c in clients:
            self.client.addItem(c["nombre"], c["id"])
        form.addRow("Método de pago", self.method); form.addRow("Cliente", self.client)
        row = QHBoxLayout(); row.addWidget(button("Cobrar", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject)); form.addRow(row)

    def validate(self) -> None:
        if self.method.currentText() == "Crédito" and self.client.currentData() is None:
            warning(self, "Validación", "Para vender a crédito selecciona un cliente."); return
        self.accept()

    def data(self) -> dict:
        return {"metodo": self.method.currentText(), "cliente_id": self.client.currentData()}


class SubstitutesDialog(QDialog):
    """Productos con el mismo principio activo y stock disponible."""

    def __init__(self, product_name: str, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sustitutos de {product_name}"); self.resize(780, 360)
        lay = QVBoxLayout(self)
        note = QLabel("Mismo principio activo con existencias válidas. «Verificar» = la concentración, forma o vía difiere o no está registrada: no es una equivalencia confirmada y la sustitución requiere validación del regente."); note.setWordWrap(True); lay.addWidget(note)
        table = make_table(["Código", "Producto", "Concentración / forma", "Equivalencia", "Precio", "Stock"]); lay.addWidget(table)
        fill_table(table, [[r["codigo"], r["nombre_comercial"], f"{r['concentracion'] or ''} {r['unidad_concentracion'] or ''} · {r['forma_farmaceutica'] or '—'}".strip(), r["equivalencia"], format_currency(r["precio_venta"]), r["stock"]] for r in rows])
        if not rows:
            lay.addWidget(QLabel("No hay sustitutos con stock disponible."))


class DevolucionDialog(QDialog):
    """Devolución parcial de una línea de venta (genera nota de crédito)."""

    def __init__(self, line: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Devolución / nota de crédito"); form = QFormLayout(self)
        available = int(line["cantidad"]) - int(line["devuelto"])
        form.addRow(QLabel(f"<b>{line['nombre_comercial']}</b> · lote {line['numero_lote']} · disponible para devolver: {available}"))
        self.qty = QSpinBox(); self.qty.setRange(1, max(1, available)); self.reason = QLineEdit()
        form.addRow("Cantidad", self.qty); form.addRow("Motivo *", self.reason)
        row = QHBoxLayout(); row.addWidget(button("Registrar", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject)); form.addRow(row)

    def validate(self) -> None:
        if not clean_text(self.reason.text()):
            warning(self, "Validación", "Indica el motivo de la devolución."); return
        self.accept()


class TableDialog(QDialog):
    """Diálogo de solo lectura que muestra una tabla (historial de precios, etc.)."""

    def __init__(self, title: str, headers: list[str], rows: list[list], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(560, 340)
        lay = QVBoxLayout(self)
        table = make_table(headers); lay.addWidget(table)
        fill_table(table, rows)
