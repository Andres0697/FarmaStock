"""Panel de historial de ventas (se muestra en la esquina de la ventana de Ventas)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.helpers import format_currency
from utils.permisos import can
from utils.messages import confirm, error, info, warning
from views.ventas_dialogs import ReceiptDialog

FILTERS = {"Hoy": True, "Últimas 100": False}
CANCELLED_COLOR = QColor("#94a3b8")


class HistoryPanel(QFrame):
    """Lista de ventas con su detalle, comprobante y anulación (admin)."""

    close_requested = Signal()
    sale_cancelled = Signal()

    def __init__(self, model, user, parent=None):
        super().__init__(parent)
        self.setObjectName("historyPanel")
        self.model = model
        self.user = user
        self.is_admin = can(user, "anular_ventas")
        self._sales = []
        self._build()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header())

        self.sales_table = self._make_table(["N.º", "Fecha", "Usuario", "Total", "Estado"], stretch=2)
        self.sales_table.itemSelectionChanged.connect(self._show_detail)
        layout.addWidget(self.sales_table, 3)

        self.summary = QLabel("Selecciona una venta para ver su detalle.")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.detail_table = self._make_table(["Producto", "Lote", "Cant.", "Subtotal"], stretch=0)
        layout.addWidget(self.detail_table, 2)

        layout.addLayout(self._build_actions())

    def _build_header(self):
        row = QHBoxLayout()

        title = QLabel("Historial de ventas")
        title.setObjectName("sectionTitle")
        row.addWidget(title)
        row.addStretch()

        self.filter = QComboBox()
        self.filter.addItems(FILTERS)
        self.filter.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.filter)

        close = QPushButton("✕")
        close.setObjectName("secondaryButton")
        close.setFixedWidth(36)
        close.setToolTip("Cerrar historial (Esc)")
        close.clicked.connect(self.close_requested.emit)
        row.addWidget(close)
        return row

    def _build_actions(self):
        row = QHBoxLayout()

        self.receipt_button = QPushButton("Ver comprobante")
        self.receipt_button.setObjectName("secondaryButton")
        self.receipt_button.clicked.connect(self.show_receipt)
        row.addWidget(self.receipt_button)

        row.addStretch()

        self.cancel_button = QPushButton("Anular venta")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self.cancel_selected)
        self.cancel_button.setVisible(self.is_admin)
        row.addWidget(self.cancel_button)

        self._update_buttons(None)
        return row

    @staticmethod
    def _make_table(headers, stretch):
        """Tabla compacta; la columna `stretch` absorbe el espacio sobrante."""
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        for column in range(len(headers)):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if column == stretch
                else QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(column, mode)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        return table

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refresh(self):
        """Recarga la lista conservando la venta seleccionada si sigue visible."""
        selected_id = self._selected_sale_id()
        try:
            self._sales = self.model.list_history(FILTERS[self.filter.currentText()])
        except Exception as exc:
            error(self, "Historial", f"No se pudo cargar el historial.\n{exc}")
            return

        only_today = FILTERS[self.filter.currentText()]
        date_format = "%H:%M" if only_today else "%d/%m %H:%M"

        self.sales_table.blockSignals(True)
        self.sales_table.setRowCount(len(self._sales))
        for row, sale in enumerate(self._sales):
            values = [
                sale["id"],
                sale["fecha"].strftime(date_format),
                sale["usuario"],
                format_currency(sale["total"]),
                sale["estado"],
            ]
            for column, value in enumerate(values):
                self.sales_table.setItem(row, column, self._cell(value, sale["estado"], column))
        self.sales_table.blockSignals(False)

        self._restore_selection(selected_id)
        self._show_detail()

    @staticmethod
    def _cell(value, status, column):
        item = QTableWidgetItem(str(value))
        if column == 3:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if status == "Anulada":
            item.setForeground(QBrush(CANCELLED_COLOR))
            font = QFont(item.font())
            font.setStrikeOut(column != 4)
            item.setFont(font)
        return item

    def _restore_selection(self, sale_id):
        for row, sale in enumerate(self._sales):
            if sale["id"] == sale_id:
                self.sales_table.selectRow(row)
                return
        self.sales_table.clearSelection()

    def _selected_sale_id(self):
        row = self.sales_table.currentRow()
        if row < 0 or row >= len(self._sales) or not self.sales_table.selectedItems():
            return None
        return self._sales[row]["id"]

    def _show_detail(self):
        sale_id = self._selected_sale_id()
        self._update_buttons(sale_id)

        if sale_id is None:
            self.detail_table.setRowCount(0)
            self.summary.setText("Selecciona una venta para ver su detalle.")
            return

        try:
            header = self.model.get_sale(sale_id)
            rows = self.model.detail(sale_id)
        except Exception as exc:
            error(self, "Historial", f"No se pudo cargar la venta.\n{exc}")
            return

        self.summary.setText(self._summary_text(header))
        self.detail_table.setRowCount(len(rows))
        for row, line in enumerate(rows):
            values = [
                line["nombre_comercial"],
                line["numero_lote"] or "—",
                line["cantidad"],
                format_currency(line["subtotal"]),
            ]
            for column, value in enumerate(values):
                self.detail_table.setItem(row, column, QTableWidgetItem(str(value)))

    @staticmethod
    def _summary_text(header):
        text = (
            f"Venta #{header['id']} · {header['metodo_pago']} · "
            f"Total {format_currency(header['total'])}"
        )
        if header["estado"] == "Anulada":
            text += (
                f"\nANULADA por {header['anulada_por']}: {header['motivo_anulacion']}"
            )
        return text

    def _update_buttons(self, sale_id):
        has_sale = sale_id is not None
        self.receipt_button.setEnabled(has_sale)

        can_cancel = False
        if has_sale:
            row = self.sales_table.currentRow()
            can_cancel = self._sales[row]["estado"] == "Completada"
        self.cancel_button.setEnabled(can_cancel)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def show_receipt(self):
        sale_id = self._selected_sale_id()
        if sale_id is None:
            return
        try:
            ReceiptDialog(
                self.model.get_sale(sale_id), self.model.detail(sale_id), self
            ).exec()
        except Exception as exc:
            error(self, "Comprobante", str(exc))

    def cancel_selected(self):
        sale_id = self._selected_sale_id()
        if sale_id is None:
            warning(self, "Historial", "Selecciona una venta.")
            return

        reason, accepted = QInputDialog.getText(
            self, "Anular venta", f"Motivo de la anulación de la venta #{sale_id}:"
        )
        if not accepted:
            return

        if not confirm(
            self,
            "Anular venta",
            f"¿Anular la venta #{sale_id}? El stock volverá a sus lotes originales.",
        ):
            return

        try:
            self.model.cancel_sale(sale_id, self.user["id"], reason)
        except Exception as exc:
            error(self, "Anular venta", str(exc))
            return

        info(self, "Anular venta", f"Venta #{sale_id} anulada. El stock fue devuelto.")
        self.refresh()
        self.sale_cancelled.emit()
