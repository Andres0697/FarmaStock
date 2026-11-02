from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QSplitter, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from models.cliente_model import ClienteModel
from utils.helpers import clean_text, format_currency
from utils.messages import error, info, warning
from utils.ui import button, fill_table, make_table, page_header
from utils.qvalidators import apply, document_validator, name_validator, phone_validator


class ClienteDialog(QDialog):
    def __init__(self, row: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar cliente" if row else "Nuevo cliente")
        form = QFormLayout(self)
        self.name, self.doc, self.ruc, self.phone, self.address = (QLineEdit() for _ in range(5))
        apply(self.name, name_validator(self.name), 120, "Nombre completo")
        apply(self.doc, document_validator(self.doc), 30); apply(self.ruc, document_validator(self.ruc), 30)
        apply(self.phone, phone_validator(self.phone), 25, "Ej.: 8888-8888"); self.address.setMaxLength(255)
        self.limit = QDoubleSpinBox(); self.limit.setRange(0, 100_000_000); self.limit.setPrefix("C$ "); self.limit.setToolTip("0 = sin límite")
        self.status = QComboBox(); self.status.addItems(["Activo", "Inactivo"])
        for label, widget in (("Nombre *", self.name), ("Cédula / documento", self.doc), ("RUC", self.ruc), ("Teléfono", self.phone),
                              ("Dirección", self.address), ("Límite de crédito", self.limit), ("Estado", self.status)):
            form.addRow(label, widget)
        row_box = QHBoxLayout(); row_box.addWidget(button("Guardar", "primary", self.validate)); row_box.addWidget(button("Cancelar", "secondary", self.reject)); form.addRow(row_box)
        if row:
            self.name.setText(row["nombre"]); self.doc.setText(row["documento"] or ""); self.ruc.setText(row["ruc"] or ""); self.phone.setText(row["telefono"] or "")
            self.address.setText(row["direccion"] or ""); self.limit.setValue(float(row["limite_credito"])); self.status.setCurrentText(row["estado"])

    def validate(self) -> None:
        if not clean_text(self.name.text()):
            warning(self, "Validación", "El nombre es obligatorio."); return
        self.accept()

    def data(self) -> dict:
        return {"nombre": clean_text(self.name.text()), "documento": clean_text(self.doc.text()), "ruc": clean_text(self.ruc.text()), "telefono": clean_text(self.phone.text()),
                "direccion": clean_text(self.address.text()), "limite_credito": self.limit.value(), "estado": self.status.currentText()}


class ClientesPage(QWidget):
    """Clientes, historial de compras y cobro de créditos."""
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.user, self.model, self.rows = user, ClienteModel(db), []
        lay = QVBoxLayout(self)
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre o documento…"); self.search.textChanged.connect(self.refresh)
        lay.addLayout(page_header("Clientes", self.search, button("＋ Nuevo cliente", "primary", self.new), button("Editar", "secondary", self.edit), button("Registrar abono", "secondary", self.add_payment)))
        split = QSplitter(Qt.Orientation.Vertical); lay.addWidget(split, 1)
        self.table = make_table(["Nombre", "Documento", "RUC", "Teléfono", "Límite crédito", "Saldo pendiente", "Estado"])
        self.table.itemSelectionChanged.connect(self.load_history)
        self.history = make_table(["Venta", "Fecha", "Pago", "Total", "Estado", "Factura"])
        box = QWidget(); bl = QVBoxLayout(box); t = QLabel("Historial de compras"); t.setObjectName("sectionTitle"); bl.addWidget(t); bl.addWidget(self.history)
        split.addWidget(self.table); split.addWidget(box)

    def refresh(self) -> None:
        try:
            self.rows = self.model.list_all(self.search.text().strip())
            fill_table(self.table, [[r["nombre"], r["documento"], r["ruc"], r["telefono"], format_currency(r["limite_credito"]), format_currency(r["saldo"]), r["estado"]] for r in self.rows])
        except Exception as exc:
            error(self, "Clientes", f"No se pudieron cargar los clientes.\n{exc}")

    def selected(self):
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def load_history(self) -> None:
        client = self.selected()
        rows = self.model.purchases(client["id"]) if client else []
        fill_table(self.history, [[r["id"], r["fecha"], r["metodo_pago"], format_currency(r["total"]), r["estado"], r["numero_factura"]] for r in rows])

    def new(self) -> None:
        self._save(ClienteDialog(parent=self), None)

    def edit(self) -> None:
        client = self.selected()
        if not client:
            warning(self, "Clientes", "Selecciona un cliente."); return
        self._save(ClienteDialog(client, self), client["id"])

    def _save(self, dialog: ClienteDialog, client_id) -> None:
        if dialog.exec():
            try:
                self.model.save(dialog.data(), client_id); self.refresh(); self.data_changed.emit()
            except Exception as exc:
                error(self, "Clientes", f"No se pudo guardar.\n{exc}")

    def add_payment(self) -> None:
        client = self.selected()
        if not client:
            warning(self, "Clientes", "Selecciona un cliente."); return
        amount, ok = QInputDialog.getDouble(self, "Abono", f"Saldo pendiente: {format_currency(client['saldo'])}\nMonto del abono:", 0, 0, 100_000_000, 2)
        if ok:
            try:
                self.model.add_payment(self.user["id"], client["id"], amount); info(self, "Clientes", "Abono registrado."); self.refresh()
            except Exception as exc:
                warning(self, "Clientes", str(exc))
