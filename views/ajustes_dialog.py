from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox

from models.ajuste_model import TIPOS
from utils.messages import warning
from utils.ui import button


class AjusteTipoDialog(QDialog):
    """Merma, vencido, devolución a proveedor o conteo físico por lote (siempre con motivo)."""

    def __init__(self, lots: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de inventario por lote"); self.resize(520, 240)
        form = QFormLayout(self)
        self.kind, self.lot = QComboBox(), QComboBox()
        self.kind.addItems(TIPOS); self.kind.currentTextChanged.connect(self._update_hint)
        for l in lots:
            self.lot.addItem(l["etiqueta"], l["id"])
        self.qty = QSpinBox(); self.qty.setRange(0, 1_000_000); self.hint = QLabel(); self.hint.setObjectName("mutedLabel")
        self.reason = QLineEdit(); self.reason.setPlaceholderText("Motivo obligatorio")
        for label, w in (("Tipo *", self.kind), ("Lote *", self.lot), ("Cantidad *", self.qty), ("", self.hint), ("Motivo *", self.reason)):
            form.addRow(label, w)
        row = QHBoxLayout(); row.addWidget(button("Aplicar", "primary", self.validate)); row.addWidget(button("Cancelar", "secondary", self.reject)); form.addRow(row)
        self._update_hint()

    def _update_hint(self) -> None:
        self.hint.setText("Cantidad real contada en el estante." if self.kind.currentText() == "Conteo físico" else "Unidades que salen del lote.")

    def validate(self) -> None:
        if self.lot.currentData() is None or not self.reason.text().strip():
            warning(self, "Validación", "Selecciona un lote e indica el motivo."); return
        self.accept()

    def data(self) -> tuple:
        return self.kind.currentText(), self.lot.currentData(), self.qty.value(), self.reason.text().strip()
