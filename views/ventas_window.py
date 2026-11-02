"""Pantalla de Ventas: catálogo con lotes, carrito, cobro e historial."""
from datetime import date

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.carrito import Cart
from models.venta_model import METODOS_PAGO, VentaModel
from utils.helpers import format_currency
from utils.messages import confirm, error, warning
from views.ventas_dialogs import DeviationDialog, PrescriptionDialog, ReceiptDialog
from views.ventas_historial import HistoryPanel

DAYS_URGENT = 30   # vence en 30 días o menos: rojo
DAYS_WARNING = 90  # vence en 90 días o menos: ámbar
COLOR_URGENT = QColor("#c62828")
COLOR_WARNING = QColor("#b7791f")
COLOR_MUTED = QColor("#94a3b8")
HISTORY_WIDTH = 470


def product_label(product):
    """Nombre para mostrar: '[Rx] Amoxicilina 500 mg'.

    El marcador va al inicio para que no se pierda cuando el nombre es largo.
    """
    name = product["nombre_comercial"]
    if product["concentracion"]:
        name += f" {float(product['concentracion']):g} {product['unidad_concentracion'] or ''}".rstrip()
    if product["control_especial"]:
        return f"[Control] {name}"
    if product["requiere_receta"]:
        return f"[Rx] {name}"
    return name


def days_until(expiry):
    return (expiry - date.today()).days if expiry else None


def lot_text(lot_number, expiry, units=None):
    text = f"{lot_number} · vence {expiry}"
    return f"{text} · {units} u." if units is not None else text


def expiry_color(days):
    if days is None:
        return None
    if days <= DAYS_URGENT:
        return COLOR_URGENT
    if days <= DAYS_WARNING:
        return COLOR_WARNING
    return None


class SaleDetailDialog(QDialog):
    def __init__(self, model, sale_id, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Venta #{sale_id}")
        self.resize(760, 400)

        layout = QVBoxLayout(self)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            [
                "Código",
                "Producto",
                "Lote",
                "Cantidad",
                "Precio",
                "Subtotal",
            ]
        )
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        rows = model.detail(sale_id)
        table.setRowCount(len(rows))

        for row_index, data in enumerate(rows):
            values = [
                data["codigo"],
                data["nombre_comercial"],
                data["numero_lote"] or "—",
                data["cantidad"],
                format_currency(data["precio_unitario"]),
                format_currency(data["subtotal"]),
            ]

            for column, value in enumerate(values):
                table.setItem(
                    row_index,
                    column,
                    QTableWidgetItem(str(value)),
                )

        layout.addWidget(table)

class SalesPage(QWidget):
    """Punto de venta: busca, elige lote, arma el carrito y cobra."""

    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()

        self.db = db
        self.user = user
        self.model = VentaModel(db)
        self.cart = Cart()

        self._products = []
        self._selected = None   # producto seleccionado en el catálogo
        self._lots = []         # lotes vendibles del producto seleccionado (FEFO)
        self._received_edited = False

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self.refresh_products)

        self.build()
        self._setup_shortcuts()
        self.refresh_products()

    # ==================================================================
    # Construcción de la interfaz
    # ==================================================================
    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addLayout(self._build_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_catalog())
        splitter.addWidget(self._build_cart())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([520, 420])
        root.addWidget(splitter, 1)

        self._build_history_panel()

    def _build_header(self):
        row = QHBoxLayout()

        title = QLabel("Ventas")
        title.setObjectName("pageTitle")
        row.addWidget(title)
        row.addStretch()

        hint = QLabel("F2 Buscar  ·  F9 Cobrar  ·  F8 Historial")
        hint.setObjectName("mutedLabel")
        row.addWidget(hint)

        self.history_button = QPushButton("Historial")
        self.history_button.setObjectName("secondaryButton")
        self.history_button.setCheckable(True)
        self.history_button.setToolTip("Ventas recientes (F8)")
        self.history_button.clicked.connect(self.toggle_history)
        row.addWidget(self.history_button)
        return row

    # ---------------------------- catálogo ----------------------------
    def _build_catalog(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar o escanear: código, código de barras, nombre, principio activo…"
        )
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        self.search.returnPressed.connect(self.on_search_enter)
        layout.addWidget(self.search)

        self.products = QTableWidget(0, 5)
        self.products.setHorizontalHeaderLabels(
            ["Código", "Producto", "Stock", "Precio", "Lote sugerido / vence"]
        )
        header = self.products.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (0, 2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.products.verticalHeader().setVisible(False)
        self.products.verticalHeader().setDefaultSectionSize(46)
        self.products.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.products.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.products.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.products.setAlternatingRowColors(True)
        self.products.setWordWrap(False)
        self.products.itemSelectionChanged.connect(self.on_product_selected)
        self.products.doubleClicked.connect(self.add_selected)
        self.products.installEventFilter(self)
        layout.addWidget(self.products, 1)

        self.product_info = QLabel("Selecciona un producto.")
        self.product_info.setObjectName("mutedLabel")
        self.product_info.setWordWrap(True)
        layout.addWidget(self.product_info)

        layout.addLayout(self._build_add_bar())
        return panel

    def _build_add_bar(self):
        row = QHBoxLayout()

        self.lot_combo = QComboBox()
        self.lot_combo.setToolTip("Lote que realmente tomaste del estante")
        self.lot_combo.setMinimumWidth(200)
        self.lot_combo.currentIndexChanged.connect(self._update_quantity_limit)
        row.addWidget(self.lot_combo, 1)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1)
        self.quantity.setMinimumWidth(80)
        self.quantity.lineEdit().returnPressed.connect(self.add_selected)
        row.addWidget(self.quantity)

        self.add_button = QPushButton("Agregar")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumHeight(36)
        self.add_button.clicked.connect(self.add_selected)
        row.addWidget(self.add_button)

        self._set_add_bar_enabled(False)
        return row

    # ----------------------------- carrito ----------------------------
    def _build_cart(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Carrito")
        title.setObjectName("sectionTitle")
        head.addWidget(title)
        self.cart_count = QLabel("0 productos")
        self.cart_count.setObjectName("mutedLabel")
        head.addWidget(self.cart_count)
        head.addStretch()
        clear = QPushButton("Vaciar")
        clear.setObjectName("secondaryButton")
        clear.clicked.connect(self.clear_cart)
        head.addWidget(clear)
        layout.addLayout(head)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(
            ["Producto", "Lote", "Cant.", "Subtotal", ""]
        )
        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.cart_table.setColumnWidth(2, 78)
        self.cart_table.setColumnWidth(4, 40)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(46)
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setWordWrap(False)
        layout.addWidget(self.cart_table, 1)

        layout.addWidget(self._build_payment_box())
        return panel

    def _build_payment_box(self):
        box = QFrame()
        box.setObjectName("paymentBox")
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self.subtotal_label = QLabel("C$ 0.00")
        self.discount = QDoubleSpinBox()
        self.discount.setDecimals(2)
        self.discount.setPrefix("C$ ")
        self.discount.setRange(0, 0)
        self.discount.valueChanged.connect(self.update_totals)

        self.payment_method = QComboBox()
        self.payment_method.addItems(METODOS_PAGO)
        self.payment_method.currentIndexChanged.connect(self.update_totals)

        self.received = QDoubleSpinBox()
        self.received.setDecimals(2)
        self.received.setRange(0, 10_000_000)
        self.received.setPrefix("C$ ")
        self.received.valueChanged.connect(self._on_received_edited)

        exact = QPushButton("Exacto")
        exact.setObjectName("secondaryButton")
        exact.setToolTip("Recibido = total")
        exact.clicked.connect(self._set_exact_received)
        self.exact_button = exact

        self.change_label = QLabel("")
        self.total = QLabel("Total: C$ 0.00")
        self.total.setObjectName("totalLabel")

        grid.addWidget(QLabel("Subtotal"), 0, 0)
        grid.addWidget(self.subtotal_label, 0, 1, 1, 2, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(QLabel("Descuento"), 1, 0)
        grid.addWidget(self.discount, 1, 1, 1, 2)
        grid.addWidget(QLabel("Pago"), 2, 0)
        grid.addWidget(self.payment_method, 2, 1, 1, 2)
        self.received_caption = QLabel("Recibido")
        grid.addWidget(self.received_caption, 3, 0)
        grid.addWidget(self.received, 3, 1)
        grid.addWidget(exact, 3, 2)
        grid.addWidget(self.change_label, 4, 0, 1, 3, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.total, 5, 0, 1, 3, Qt.AlignmentFlag.AlignRight)

        self.finish_button = QPushButton("Cobrar  (F9)")
        self.finish_button.setObjectName("primaryButton")
        self.finish_button.setMinimumHeight(46)
        self.finish_button.clicked.connect(self.finish)
        grid.addWidget(self.finish_button, 6, 0, 1, 3)
        return box

    # ---------------------- historial (esquina) -----------------------
    def _build_history_panel(self):
        self.history = HistoryPanel(self.model, self.user, self)
        self.history.close_requested.connect(lambda: self.toggle_history(False))
        self.history.sale_cancelled.connect(self._after_sale_cancelled)

        shadow = QGraphicsDropShadowEffect(self.history)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(16, 42, 67, 70))
        self.history.setGraphicsEffect(shadow)

        self.history.hide()
        self._history_animation = QPropertyAnimation(self.history, b"geometry", self)
        self._history_animation.setDuration(180)
        self._history_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._history_animation.finished.connect(self._on_history_animation_end)

    def _setup_shortcuts(self):
        for key, action in (
            ("F2", self.focus_search),
            ("F8", lambda: self.toggle_history(not self.history.isVisible())),
            ("F9", self.finish),
            ("Del", self.remove_selected_cart_row),
            ("Esc", lambda: self.toggle_history(False)),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(lambda act=action: self.isVisible() and act())

    # ==================================================================
    # Historial en la esquina
    # ==================================================================
    def _history_rect(self, visible):
        top = self.history_button.geometry().bottom() + 10
        width = min(HISTORY_WIDTH, self.width() - 20)
        height = max(260, self.height() - top - 4)
        x = self.width() - width if visible else self.width() + 20
        return QRect(x, top, width, height)

    def toggle_history(self, show):
        self.history_button.setChecked(show)
        if show == self.history.isVisible() and not self._history_animation.state():
            return

        self._history_animation.stop()
        if show:
            self.history.refresh()
            self.history.setGeometry(self._history_rect(False))
            self.history.show()
            self.history.raise_()
        self._history_animation.setStartValue(self.history.geometry())
        self._history_animation.setEndValue(self._history_rect(show))
        self._history_animation.start()

    def _on_history_animation_end(self):
        if not self.history_button.isChecked():
            self.history.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.history.isVisible() and self.history_button.isChecked():
            self.history.setGeometry(self._history_rect(True))

    def _after_sale_cancelled(self):
        self.refresh_products()
        self.data_changed.emit()

    # ==================================================================
    # Catálogo y selección de producto
    # ==================================================================
    def refresh(self):
        """La llama el dashboard al entrar a esta pantalla."""
        self.refresh_products()
        if self.history.isVisible():
            self.history.refresh()
        self.focus_search()

    def showEvent(self, event):
        super().showEvent(event)
        self.focus_search()

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def refresh_products(self):
        selected_id = self._selected["id"] if self._selected else None
        try:
            self._products = self.model.search_products(self.search.text())
        except Exception as exc:
            error(self, "Ventas", f"No se pudieron cargar los productos.\n{exc}")
            return

        self.products.blockSignals(True)
        self.products.setRowCount(len(self._products))
        for row, product in enumerate(self._products):
            self._fill_product_row(row, product)
        self.products.blockSignals(False)

        self._select_product_by_id(selected_id)
        self.on_product_selected()

    def _fill_product_row(self, row, product):
        days = days_until(product["vence"])
        values = [
            product["codigo"],
            f"{product_label(product)}\n{self._product_subtitle(product)}",
            product["stock"],
            format_currency(product["precio_venta"]),
            f"{product['lote_sugerido']}\n{product['vence']}" if product["lote_sugerido"] else "—",
        ]

        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(self._product_subtitle(product, full=True))
            if column in (2, 3):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if int(product["stock"]) <= 0:
                item.setForeground(QBrush(COLOR_MUTED))
            elif column == 4 and expiry_color(days):
                item.setForeground(QBrush(expiry_color(days)))
            self.products.setItem(row, column, item)

    @staticmethod
    def _product_subtitle(product, full=False):
        """Segunda línea del producto: marca/laboratorio y presentación."""
        parts = [product["laboratorio"] or product["marca"], product["presentacion"]]
        if full:
            parts = [product["marca"], product["laboratorio"], product["presentacion"],
                     product["principio_activo"]]
        return " · ".join(part for part in parts if part) or "—"

    def _select_product_by_id(self, product_id):
        if product_id is None:
            self.products.clearSelection()
            return
        for row, product in enumerate(self._products):
            if product["id"] == product_id:
                self.products.selectRow(row)
                return
        self.products.clearSelection()

    def on_product_selected(self):
        row = self.products.currentRow()
        if row < 0 or row >= len(self._products) or not self.products.selectedItems():
            self._selected = None
            self._lots = []
            self.lot_combo.clear()
            self._set_add_bar_enabled(False)
            self.product_info.setText("Selecciona un producto.")
            return

        self._selected = self._products[row]
        self._lots = self.model.valid_lots(self._selected["id"])
        self._fill_lot_combo()
        self._show_product_info()

    def _show_product_info(self):
        details = self._product_subtitle(self._selected, full=True)
        if not self._lots:
            details += "\nSin stock vendible (agotado o vencido)."
        self.product_info.setText(details)

    def _fill_lot_combo(self):
        self.lot_combo.blockSignals(True)
        self.lot_combo.clear()

        if self._lots:
            first = self._lots[0]
            self.lot_combo.addItem(
                f"Automático FEFO · {first['numero_lote']} (vence {first['fecha_vencimiento']})",
                None,
            )
            for lot in self._lots[1:]:
                days = days_until(lot["fecha_vencimiento"])
                warn = "  ⚠" if days is not None and days <= DAYS_URGENT else ""
                self.lot_combo.addItem(
                    lot_text(lot["numero_lote"], lot["fecha_vencimiento"], lot["cantidad_actual"]) + warn,
                    lot["id"],
                )

        self.lot_combo.blockSignals(False)
        self._set_add_bar_enabled(bool(self._lots))
        self._update_quantity_limit()

    def _set_add_bar_enabled(self, enabled):
        for widget in (self.lot_combo, self.quantity, self.add_button):
            widget.setEnabled(enabled)

    def _chosen_lot(self):
        """Lote explícito elegido en el combo, o None si es FEFO automático."""
        lot_id = self.lot_combo.currentData()
        return next((lot for lot in self._lots if lot["id"] == lot_id), None)

    def _update_quantity_limit(self):
        """Máximo que se puede agregar según el stock y lo que ya hay en el carrito."""
        if not self._selected or not self._lots:
            self.quantity.setRange(1, 1)
            return

        lot = self._chosen_lot()
        if lot:
            existing = self.cart.find(self._selected["id"], lot["id"])
            available = lot["cantidad_actual"] - (existing["cantidad"] if existing else 0)
        else:
            available = int(self._selected["stock"]) - self.cart.units_of_product(
                self._selected["id"]
            )

        self.quantity.setRange(1, max(1, available))
        self.quantity.setValue(1)
        self.add_button.setEnabled(available > 0)

    def on_search_enter(self):
        """Enter en el buscador: un código exacto (lector de barras) agrega solo."""
        self._search_timer.stop()
        self.refresh_products()

        product_id = self.model.find_exact_product(self.search.text())
        if product_id is not None:
            self._select_product_by_id(product_id)
            self.on_product_selected()
            self.add_selected()
        elif self._products:
            self.products.selectRow(0)
            self.quantity.setFocus()

    def eventFilter(self, watched, event):
        if (
            watched is self.products
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            if self.quantity.isEnabled():
                self.quantity.setFocus()
                self.quantity.selectAll()
            return True
        return super().eventFilter(watched, event)

    # ==================================================================
    # Agregar al carrito
    # ==================================================================
    def add_selected(self):
        product = self._selected
        if not product:
            warning(self, "Ventas", "Selecciona un producto.")
            return
        if not self._lots:
            warning(self, "Ventas", "El producto no tiene stock vendible.")
            return

        chosen = self._chosen_lot()
        lot_id = chosen["id"] if chosen else None
        existing = self.cart.find(product["id"], lot_id)

        prescription = self._prescription_for(product)
        if prescription is False:
            return  # el vendedor canceló la receta

        reason = ""
        if chosen and not existing:
            reason = self._confirm_deviation(product, chosen)
            if reason is None:
                return  # canceló al ver el aviso de lote distinto

        self.cart.add(self._build_cart_item(product, chosen, reason, prescription))
        self.refresh_cart()

        self.search.clear()
        self.focus_search()

    def _prescription_for(self, product):
        """Datos de receta: None si no se necesitan, False si se canceló."""
        if not (product["requiere_receta"] or product["control_especial"]):
            return None

        for item in self.cart.items:
            if item["producto_id"] == product["id"] and item.get("receta"):
                return item["receta"]

        dialog = PrescriptionDialog(
            product_label(product), bool(product["control_especial"]), parent=self
        )
        return dialog.data() if dialog.exec() == QDialog.DialogCode.Accepted else False

    def _confirm_deviation(self, product, chosen):
        """Avisa del lote que vence antes. Devuelve el motivo, o None si cancela."""
        suggested = self._lots[0]
        dialog = DeviationDialog(
            product_label(product),
            lot_text(suggested["numero_lote"], suggested["fecha_vencimiento"]),
            lot_text(chosen["numero_lote"], chosen["fecha_vencimiento"]),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.motivo()

    def _build_cart_item(self, product, chosen, reason, prescription):
        return {
            "producto_id": product["id"],
            "nombre": product_label(product),
            "lote_id": chosen["id"] if chosen else None,
            "lote_texto": chosen["numero_lote"] if chosen else "FEFO",
            "desviado": chosen is not None,
            "cantidad": self.quantity.value(),
            "precio": float(product["precio_venta"]),
            "stock_lote": chosen["cantidad_actual"] if chosen else 0,
            "stock_producto": int(product["stock"]),
            "motivo_desviacion": reason,
            "receta": prescription,
        }

    # ==================================================================
    # Carrito
    # ==================================================================
    def refresh_cart(self):
        # Se vacía primero para destruir los widgets de las filas anteriores.
        self.cart_table.setRowCount(0)
        self.cart_table.setRowCount(len(self.cart))

        for row, item in enumerate(self.cart.items):
            name = QTableWidgetItem(f"{item['nombre']}\n{format_currency(item['precio'])} c/u")
            name.setToolTip(item["nombre"])
            self.cart_table.setItem(row, 0, name)
            self.cart_table.setItem(row, 1, self._lot_cell(item))
            self.cart_table.setCellWidget(row, 2, self._quantity_editor(item))
            self.cart_table.setItem(row, 3, self._money_cell(item["cantidad"] * item["precio"]))
            self.cart_table.setCellWidget(row, 4, self._remove_button(item))

        self.update_totals()
        self._update_quantity_limit()

    @staticmethod
    def _money_cell(value):
        cell = QTableWidgetItem(format_currency(value))
        cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return cell

    @staticmethod
    def _lot_cell(item):
        text = f"⚠ {item['lote_texto']}" if item["desviado"] else item["lote_texto"]
        cell = QTableWidgetItem(text)
        if item["desviado"]:
            cell.setForeground(QBrush(COLOR_WARNING))
            cell.setToolTip("Lote distinto al sugerido por FEFO")
        return cell

    def _quantity_editor(self, item):
        editor = QSpinBox()
        editor.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # sin flechas: se escribe la cantidad
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.setRange(1, self.cart.maximum_for(item))
        editor.setValue(item["cantidad"])
        editor.valueChanged.connect(lambda value, line=item: self._on_cart_quantity(line, value))
        return editor

    def _remove_button(self, item):
        button = QPushButton("✕")
        button.setObjectName("removeButton")
        button.setFixedSize(28, 28)
        button.setToolTip("Quitar del carrito")
        button.clicked.connect(lambda _=False, line=item: self._remove_line(line))
        return button

    def _on_cart_quantity(self, item, value):
        item["cantidad"] = value
        row = self.cart.items.index(item)
        self.cart_table.setItem(row, 3, self._money_cell(value * item["precio"]))
        self._sync_quantity_limits()
        self.update_totals()
        self._update_quantity_limit()

    def _sync_quantity_limits(self):
        """Actualiza el máximo de cada línea: depende de las demás del mismo producto."""
        for row, item in enumerate(self.cart.items):
            editor = self.cart_table.cellWidget(row, 2)
            if editor:
                editor.blockSignals(True)
                editor.setMaximum(self.cart.maximum_for(item))
                editor.blockSignals(False)

    def _remove_line(self, item):
        self.cart.remove(self.cart.items.index(item))
        self.refresh_cart()

    def remove_selected_cart_row(self):
        row = self.cart_table.currentRow()
        if row >= 0:
            self.cart.remove(row)
            self.refresh_cart()

    def clear_cart(self):
        if len(self.cart) and not confirm(self, "Ventas", "¿Vaciar el carrito?"):
            return
        self.cart.clear()
        self.refresh_cart()

    # ==================================================================
    # Totales y cobro
    # ==================================================================
    def _is_cash(self):
        return self.payment_method.currentText() == "Efectivo"

    def _on_received_edited(self):
        self._received_edited = True
        self._update_change()

    def _set_exact_received(self):
        self._received_edited = False
        self.update_totals()

    def _current_total(self):
        subtotal = self.cart.subtotal()
        return round(subtotal - min(self.discount.value(), subtotal), 2)

    def update_totals(self):
        subtotal = self.cart.subtotal()
        self.discount.setMaximum(subtotal)
        discount = min(self.discount.value(), subtotal)
        total = round(subtotal - discount, 2)

        units, lines = self.cart.units(), len(self.cart)
        self.cart_count.setText(f"{units} unidad(es) · {lines} producto(s)")
        self.subtotal_label.setText(format_currency(subtotal))
        self.total.setText(f"Total: {format_currency(total)}")

        cash = self._is_cash()
        for widget in (self.received, self.received_caption, self.exact_button):
            widget.setVisible(cash)

        if cash and not self._received_edited:
            self.received.blockSignals(True)
            self.received.setValue(total)
            self.received.blockSignals(False)
        self._update_change()

    def _update_change(self):
        if not self._is_cash():
            self.change_label.setText("")
            return

        total = self._current_total()
        received = self.received.value()
        if received + 0.001 >= total:
            self.change_label.setText(
                f"Cambio: {format_currency(VentaModel.calculate_change(total, received))}"
            )
            self.change_label.setStyleSheet("color:#2e7d32; font-weight:700;")
        else:
            self.change_label.setText(f"Falta: {format_currency(total - received)}")
            self.change_label.setStyleSheet("color:#c62828; font-weight:700;")

    def finish(self):
        if not len(self.cart):
            warning(self, "Ventas", "Agrega al menos un producto.")
            return

        total = self._current_total()
        method = self.payment_method.currentText()
        received = self.received.value() if self._is_cash() else None

        if received is not None and received + 0.001 < total:
            warning(self, "Ventas", "El monto recibido es menor que el total a pagar.")
            self.received.setFocus()
            return

        if not confirm(self, "Confirmar venta", self._confirmation_text(total, method, received)):
            return

        try:
            sale_id, *_ = self.model.create_sale(
                self.user["id"],
                self.cart.to_sale_items(),
                self.discount.value(),
                metodo_pago=method,
                monto_recibido=received,
                exigir_receta=True,
            )
        except Exception as exc:
            error(self, "Ventas", str(exc))
            self.refresh_products()  # el stock pudo cambiar
            return

        self._after_sale(sale_id)

    @staticmethod
    def _confirmation_text(total, method, received):
        text = f"Total: {format_currency(total)}\nPago: {method}"
        if received is not None:
            text += f"\nCambio: {format_currency(VentaModel.calculate_change(total, received))}"
        return text + "\n\n¿Registrar la venta?"

    def _after_sale(self, sale_id):
        header = self.model.get_sale(sale_id)
        lines = self.model.detail(sale_id)

        self.cart.clear()
        self.discount.setValue(0)
        self._received_edited = False
        self.refresh_cart()
        self.refresh_products()
        if self.history.isVisible():
            self.history.refresh()
        self.data_changed.emit()

        ReceiptDialog(header, lines, self).exec()
        self.focus_search()
