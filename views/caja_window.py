from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from models.caja_model import CajaModel
from utils.helpers import format_currency
from utils.messages import confirm, error, info, warning
from utils.ui import StatCard, button, fill_table, make_table, page_header


class ArqueoDialog(QDialog):
    """Arqueo: el cajero cuenta el efectivo y el sistema muestra la diferencia."""

    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cierre de turno · Arqueo")
        form = QFormLayout(self)
        form.addRow("Fondo inicial", QLabel(format_currency(summary["inicial"])))
        for method in ("Efectivo", "Tarjeta", "Transferencia", "Crédito"):
            form.addRow(f"Ventas {method.lower()}", QLabel(format_currency(summary["por_metodo"].get(method, 0))))
        form.addRow("Devoluciones en efectivo", QLabel(format_currency(summary["devoluciones_efectivo"])))
        form.addRow("Efectivo esperado", QLabel(f"<b>{format_currency(summary['efectivo_esperado'])}</b>"))
        self.counted = QDoubleSpinBox(); self.counted.setRange(0, 100_000_000); self.counted.setPrefix("C$ "); self.counted.setDecimals(2)
        form.addRow("Efectivo contado *", self.counted)
        row = QHBoxLayout(); row.addWidget(button("Cerrar turno", "primary", self.accept)); row.addWidget(button("Cancelar", "secondary", self.reject))
        form.addRow(row)


class CajaPage(QWidget):
    """Apertura y cierre de turno con arqueo."""
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.user, self.model = user, CajaModel(db)
        lay = QVBoxLayout(self)
        self.open_btn = button("Abrir turno", "primary", self.open_shift)
        self.close_btn = button("Cerrar turno (arqueo)", "danger", self.close_shift)
        lay.addLayout(page_header("Caja", self.open_btn, self.close_btn))
        cards = QHBoxLayout()
        self.state, self.cash, self.total = StatCard("Estado del turno"), StatCard("Efectivo esperado", "#2e7d32"), StatCard("Ventas del turno", "#1976d2")
        for card in (self.state, self.cash, self.total):
            cards.addWidget(card)
        lay.addLayout(cards)
        title = QLabel("Historial de turnos"); title.setObjectName("sectionTitle"); lay.addWidget(title)
        self.table = make_table(["Turno", "Cajero", "Apertura", "Cierre", "Inicial", "Esperado", "Contado", "Diferencia", "Estado"])
        lay.addWidget(self.table, 1)

    def refresh(self) -> None:
        try:
            shift = self.model.current(self.user["id"])
            self.open_btn.setEnabled(shift is None); self.close_btn.setEnabled(shift is not None)
            if shift:
                s = self.model.summary(shift["id"])
                self.state.set_value("Abierto", f"Turno #{shift['id']} desde {shift['apertura']:%d/%m %H:%M}")
                self.cash.set_value(format_currency(s["efectivo_esperado"]), "Fondo + ventas en efectivo")
                self.total.set_value(format_currency(sum(s["por_metodo"].values())), "Todos los métodos de pago")
            else:
                self.state.set_value("Cerrado", "Abre un turno para vender"); self.cash.set_value("—", ""); self.total.set_value("—", "")
            fill_table(self.table, [[r["id"], r["usuario"], r["apertura"], r["cierre"], format_currency(r["monto_inicial"]),
                                     format_currency(r["efectivo_esperado"]) if r["efectivo_esperado"] is not None else "—",
                                     format_currency(r["efectivo_contado"]) if r["efectivo_contado"] is not None else "—",
                                     format_currency(r["diferencia"]) if r["diferencia"] is not None else "—", r["estado"]] for r in self.model.history()])
        except Exception as exc:
            error(self, "Caja", f"No se pudo cargar la caja.\n{exc}")

    def open_shift(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle("Apertura de turno")
        form = QFormLayout(dialog)
        amount = QDoubleSpinBox(); amount.setRange(0, 100_000_000); amount.setPrefix("C$ "); amount.setDecimals(2)
        form.addRow("Fondo inicial en efectivo", amount)
        row = QHBoxLayout(); row.addWidget(button("Abrir turno", "primary", dialog.accept)); row.addWidget(button("Cancelar", "secondary", dialog.reject)); form.addRow(row)
        if dialog.exec():
            try:
                self.model.open(self.user["id"], amount.value()); info(self, "Caja", "Turno abierto. Ya puedes registrar ventas.")
                self.refresh(); self.data_changed.emit()
            except Exception as exc:
                warning(self, "Caja", str(exc))

    def close_shift(self) -> None:
        shift = self.model.current(self.user["id"])
        if not shift:
            return
        dialog = ArqueoDialog(self.model.summary(shift["id"]), self)
        if dialog.exec():
            try:
                result = self.model.close(self.user["id"], shift["id"], dialog.counted.value())
                info(self, "Turno cerrado", f"Esperado: {format_currency(result['efectivo_esperado'])}\nContado: {format_currency(result['contado'])}\n"
                                             f"Diferencia: {format_currency(result['diferencia'])}")
                self.refresh(); self.data_changed.emit()
            except Exception as exc:
                error(self, "Caja", str(exc))
