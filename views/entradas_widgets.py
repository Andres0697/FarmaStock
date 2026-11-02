"""Entradas de mercadería: diálogo para registrarlas y pestaña con el historial."""
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.entrada_model import EntradaModel
from models.proveedor_model import ProveedorModel
from utils.helpers import clean_text, format_currency
from utils.messages import confirm, error, info, warning

# Opciones del filtro de período del historial: texto -> días hacia atrás
PERIODS = {"Últimos 30 días": 30, "Últimos 90 días": 90, "Este año": None, "Todo": 0}
DEFAULT_SHELF_LIFE_MONTHS = 12
DATE_FORMAT = "dd/MM/yyyy"
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def product_text(product):
    """'FAR-001 · Paracetamol 500 mg'."""
    name = product["nombre_comercial"]
    if product["concentracion"]:
        name += f" {float(product['concentracion']):g} {product['unidad_concentracion'] or ''}".rstrip()
    return f"{product['codigo']} · {name}"


def read_only_table(headers, stretch_column=0):
    """Tabla de solo lectura con el estilo común de la pantalla."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    return table


def set_row(table, row, values, right_columns=()):
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        if column in right_columns:
            item.setTextAlignment(RIGHT)
        table.setItem(row, column, item)


# ======================================================================
# Diálogo: registrar una entrada
# ======================================================================
class EntryDialog(QDialog):
    """Documento del proveedor (factura) con varias líneas de producto y lote."""

    def __init__(self, model, provider_model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar entrada de mercadería")
        self.resize(860, 640)

        self.model = model
        self.lines = []  # una por producto/lote agregado

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(self._build_header(provider_model))
        layout.addWidget(self._build_line_form())
        layout.addWidget(self._build_lines_table(), 1)
        layout.addLayout(self._build_footer())

        self._load_products()
        self._refresh_lines()

    # ---------------------------- interfaz ----------------------------
    def _build_header(self, provider_model):
        form = QFormLayout()

        self.provider = QComboBox()
        for provider in provider_model.active():
            self.provider.addItem(provider["nombre"], provider["id"])

        self.invoice = QLineEdit()
        self.invoice.setMaxLength(60)
        self.invoice.setPlaceholderText("Ej. F-00123")

        self.invoice_date = QDateEdit(QDate.currentDate())
        self.invoice_date.setCalendarPopup(True)
        self.invoice_date.setMaximumDate(QDate.currentDate())
        self.invoice_date.setDisplayFormat(DATE_FORMAT)

        self.notes = QLineEdit()
        self.notes.setMaxLength(255)
        self.notes.setPlaceholderText("Opcional")

        form.addRow("Proveedor *", self.provider)
        form.addRow("N.º de factura *", self.invoice)
        form.addRow("Fecha de la factura *", self.invoice_date)
        form.addRow("Observaciones", self.notes)
        return form

    def _build_line_form(self):
        box = QFrame()
        box.setObjectName("paymentBox")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)

        title = QLabel("Agregar producto recibido")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.product = QComboBox()
        self.product.setEditable(True)
        self.product.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.product.lineEdit().setPlaceholderText("Buscar por código o nombre…")
        layout.addWidget(self.product)

        row = QHBoxLayout()
        self.lot = QLineEdit()
        self.lot.setMaxLength(80)
        self.lot.setPlaceholderText("N.º de lote")

        self.expiry = QDateEdit(QDate.currentDate().addMonths(DEFAULT_SHELF_LIFE_MONTHS))
        self.expiry.setCalendarPopup(True)
        self.expiry.setMinimumDate(QDate.currentDate().addDays(1))
        self.expiry.setDisplayFormat(DATE_FORMAT)
        self.expiry.setToolTip("Fecha de vencimiento")

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1_000_000)
        self.quantity.setToolTip("Cantidad recibida (unidades)")

        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 10_000_000)
        self.cost.setDecimals(2)
        self.cost.setPrefix("C$ ")
        self.cost.setToolTip("Costo por unidad")

        add = QPushButton("Agregar")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.add_line)
        self.lot.returnPressed.connect(self.add_line)

        row.addWidget(self.lot, 2)
        row.addWidget(QLabel("Vence"))
        row.addWidget(self.expiry, 2)
        row.addWidget(QLabel("Cant."))
        row.addWidget(self.quantity, 1)
        row.addWidget(QLabel("Costo"))
        row.addWidget(self.cost, 1)
        row.addWidget(add)
        layout.addLayout(row)
        return box

    def _build_lines_table(self):
        self.table = read_only_table(
            ["Producto", "Lote", "Vence", "Cant.", "Costo", "Subtotal", ""]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 40)
        self.table.verticalHeader().setDefaultSectionSize(40)
        return self.table

    def _build_footer(self):
        row = QHBoxLayout()
        self.total_label = QLabel("Total: C$ 0.00")
        self.total_label.setObjectName("totalLabel")
        self.total_label.setMinimumWidth(260)
        row.addWidget(self.total_label)
        row.addStretch()

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)

        self.save_button = QPushButton("Registrar entrada")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save)

        row.addWidget(cancel)
        row.addWidget(self.save_button)
        return row

    # ---------------------------- productos ---------------------------
    def _load_products(self):
        for product in self.model.active_products():
            self.product.addItem(product_text(product), product["id"])

        completer = QCompleter(self.product.model(), self)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.product.setCompleter(completer)
        self.product.setCurrentIndex(-1)

    def _selected_product(self):
        """(id, texto) del producto escrito/elegido, o None si no está en la lista."""
        index = self.product.findText(self.product.currentText(), Qt.MatchFlag.MatchFixedString)
        if index < 0:
            return None
        return self.product.itemData(index), self.product.itemText(index)

    # ----------------------------- líneas -----------------------------
    def add_line(self):
        product = self._selected_product()
        lot = clean_text(self.lot.text())

        if product is None:
            warning(self, "Entrada", "Elige un producto de la lista.")
            self.product.setFocus()
            return
        if not lot:
            warning(self, "Entrada", "Escribe el número de lote.")
            self.lot.setFocus()
            return
        if self._line_index(product[0], lot) is not None:
            warning(self, "Entrada", f"El lote {lot} de ese producto ya está en la lista.")
            return

        self.lines.append(
            {
                "producto_id": product[0],
                "producto": product[1],
                "numero_lote": lot,
                "fecha_vencimiento": self.expiry.date().toPython(),
                "cantidad": self.quantity.value(),
                "costo_unitario": self.cost.value(),
            }
        )
        self._refresh_lines()
        self._reset_line_form()

    def _line_index(self, product_id, lot):
        for index, line in enumerate(self.lines):
            if line["producto_id"] == product_id and line["numero_lote"].lower() == lot.lower():
                return index
        return None

    def _reset_line_form(self):
        self.product.setCurrentIndex(-1)
        self.product.clearEditText()
        self.lot.clear()
        self.quantity.setValue(1)
        self.cost.setValue(0)
        self.product.setFocus()

    def _remove_line(self, line):
        self.lines.remove(line)
        self._refresh_lines()

    def _refresh_lines(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.lines))

        for row, line in enumerate(self.lines):
            subtotal = line["cantidad"] * line["costo_unitario"]
            set_row(
                self.table,
                row,
                [
                    line["producto"],
                    line["numero_lote"],
                    line["fecha_vencimiento"],
                    line["cantidad"],
                    format_currency(line["costo_unitario"]),
                    format_currency(subtotal),
                ],
                right_columns=(3, 4, 5),
            )
            self.table.setCellWidget(row, 6, self._remove_button(line))

        total = sum(l["cantidad"] * l["costo_unitario"] for l in self.lines)
        self.total_label.setText(f"Total: {format_currency(total)}")

    def _remove_button(self, line):
        button = QPushButton("✕")
        button.setObjectName("removeButton")
        button.setFixedSize(28, 28)
        button.setToolTip("Quitar de la entrada")
        button.clicked.connect(lambda _=False, item=line: self._remove_line(item))
        return button

    # ----------------------------- guardar ----------------------------
    def save(self):
        """Valida lo básico y pide confirmación. El guardado real lo hace data()."""
        if self.provider.currentData() is None:
            warning(self, "Entrada", "No hay proveedores activos. Registra uno primero.")
            return
        if not clean_text(self.invoice.text()):
            warning(self, "Entrada", "Escribe el número de factura del proveedor.")
            self.invoice.setFocus()
            return
        if not self.lines:
            warning(self, "Entrada", "Agrega al menos un producto a la entrada.")
            return

        units = sum(line["cantidad"] for line in self.lines)
        message = (
            f"Proveedor: {self.provider.currentText()}\n"
            f"Factura: {clean_text(self.invoice.text())}\n"
            f"{len(self.lines)} producto(s) · {units} unidades\n"
            f"{self.total_label.text()}\n\n¿Registrar la entrada?"
        )
        if confirm(self, "Confirmar entrada", message):
            self.accept()

    def data(self):
        """Datos para EntradaModel.create_entry."""
        return {
            "provider_id": self.provider.currentData(),
            "invoice_number": self.invoice.text(),
            "invoice_date": self.invoice_date.date().toPython(),
            "notes": self.notes.text(),
            "lines": [
                {key: line[key] for key in (
                    "producto_id", "numero_lote", "fecha_vencimiento",
                    "cantidad", "costo_unitario",
                )}
                for line in self.lines
            ],
        }


# ======================================================================
# Pestaña: historial de entradas
# ======================================================================
class EntriesTab(QWidget):
    """Historial de entradas por proveedor y período, con su detalle."""

    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.user = user
        self.model = EntradaModel(db)
        self.provider_model = ProveedorModel(db)
        self._entries = []
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addLayout(self._build_toolbar())

        self.entries_table = read_only_table(
            ["N.º", "Factura", "Fecha factura", "Proveedor", "Líneas", "Total", "Registró"],
            stretch_column=3,
        )
        self.entries_table.itemSelectionChanged.connect(self._show_detail)
        layout.addWidget(self.entries_table, 3)

        self.summary = QLabel("Selecciona una entrada para ver su detalle.")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.detail_table = read_only_table(
            ["Producto", "Lote", "Vence", "Cant.", "Costo", "Subtotal"]
        )
        layout.addWidget(self.detail_table, 2)

    def _build_toolbar(self):
        row = QHBoxLayout()

        self.provider_filter = QComboBox()
        self.provider_filter.setMinimumWidth(190)
        self.period_filter = QComboBox()
        self.period_filter.addItems(PERIODS)
        for combo in (self.provider_filter, self.period_filter):
            combo.currentIndexChanged.connect(self.refresh)

        add = QPushButton("＋ Registrar entrada")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.new_entry)

        row.addWidget(QLabel("Proveedor"))
        row.addWidget(self.provider_filter)
        row.addWidget(QLabel("Período"))
        row.addWidget(self.period_filter)
        row.addStretch()
        row.addWidget(add)
        return row

    # ------------------------------ datos -----------------------------
    def _reload_provider_filter(self):
        current = self.provider_filter.currentData()
        self.provider_filter.blockSignals(True)
        self.provider_filter.clear()
        self.provider_filter.addItem("Todos los proveedores", None)
        with self.model.db.cursor() as (_, cursor):
            cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
            for provider in cursor.fetchall():
                self.provider_filter.addItem(provider["nombre"], provider["id"])
        index = self.provider_filter.findData(current)
        self.provider_filter.setCurrentIndex(max(0, index))
        self.provider_filter.blockSignals(False)

    def _since_date(self):
        period = PERIODS[self.period_filter.currentText()]
        if period is None:  # "Este año"
            return date(date.today().year, 1, 1)
        if period == 0:  # "Todo"
            return None
        return date.today() - timedelta(days=period)

    def refresh(self):
        self._reload_provider_filter()  # por si se agregó un proveedor nuevo

        try:
            self._entries = self.model.list_entries(
                self.provider_filter.currentData(), self._since_date()
            )
        except Exception as exc:
            error(self, "Entradas", f"No se pudo cargar el historial.\n{exc}")
            return

        self.entries_table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            set_row(
                self.entries_table,
                row,
                [
                    entry["id"],
                    entry["numero_factura"],
                    entry["fecha_factura"],
                    entry["proveedor"],
                    entry["lineas"],
                    format_currency(entry["total"]),
                    entry["usuario"],
                ],
                right_columns=(4, 5),
            )
        self.detail_table.setRowCount(0)
        self.summary.setText(f"{len(self._entries)} entrada(s). Selecciona una para ver su detalle.")

    def _show_detail(self):
        row = self.entries_table.currentRow()
        if row < 0 or row >= len(self._entries):
            return

        entry = self._entries[row]
        header = self.model.get_entry(entry["id"])
        notes = f" · {header['observaciones']}" if header["observaciones"] else ""
        self.summary.setText(
            f"Entrada #{header['id']} · {header['proveedor']} · "
            f"Factura {header['numero_factura']} · registrada "
            f"{header['fecha_registro']:%d/%m/%Y %H:%M} por {header['usuario']}{notes}"
        )

        rows = self.model.detail(entry["id"])
        self.detail_table.setRowCount(len(rows))
        for index, line in enumerate(rows):
            set_row(
                self.detail_table,
                index,
                [
                    product_text(line),
                    line["numero_lote"],
                    line["fecha_vencimiento"],
                    line["cantidad"],
                    format_currency(line["costo_unitario"]),
                    format_currency(line["subtotal"]),
                ],
                right_columns=(3, 4, 5),
            )

    # ------------------------------ acciones --------------------------
    def new_entry(self):
        dialog = EntryDialog(self.model, self.provider_model, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.data()
        try:
            entry_id, total = self.model.create_entry(
                self.user["id"],
                data["provider_id"],
                data["invoice_number"],
                data["invoice_date"],
                data["lines"],
                data["notes"],
            )
        except Exception as exc:
            error(self, "Entradas", str(exc))
            return

        info(self, "Entradas", f"Entrada #{entry_id} registrada por {format_currency(total)}.")
        self.refresh()
        self.data_changed.emit()
