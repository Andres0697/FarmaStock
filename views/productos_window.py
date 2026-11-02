from PySide6.QtCore import Signal, Qt, QDate
from PySide6.QtWidgets import *
from models.producto_model import ProductoModel
from models.proveedor_model import ProveedorModel
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from utils.qvalidators import apply, code_validator, name_validator
from models.inventario_model import InventarioModel
from utils.messages import info, warning, error
from utils.helpers import clean_text, format_currency
from datetime import date
from models.producto_extra_model import ProductoExtraModel, CATEGORIAS_DISPENSACION
from utils.permisos import can
from utils.ui import colored_item, stock_item
from views.dialogs_venta import SubstitutesDialog, TableDialog

class ProductDialog(QDialog):

    def __init__(self, model, product=None, parent=None):
        super().__init__(parent)
        self.model = model
        self.product = product
        self.setWindowTitle('Editar producto' if product else 'Nuevo producto')
        self.resize(720, 560)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)
        basic = QWidget()
        f = QFormLayout(basic)
        self.code = QLineEdit()
        self.barcode = QLineEdit()
        apply(self.code, code_validator(self.code), 50, 'Código interno')
        self.barcode.setValidator(QRegularExpressionValidator(QRegularExpression(r'[0-9]{0,14}'), self.barcode)); self.barcode.setMaxLength(14)
        self.barcode.setPlaceholderText('Opcional · EAN/UPC, normalmente 8–14 dígitos')
        self.name = QLineEdit()
        apply(self.name, name_validator(self.name), 160, 'Nombre comercial')
        self.brand = QComboBox()
        self.brand.setEditable(True)
        self.brand.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.brand.setPlaceholderText('Escribe una marca/laboratorio o selecciona uno')
        self.cat = QComboBox()
        self.status = QComboBox()
        self.status.addItems(['Activo', 'Inactivo'])
        for w in (self.brand, self.cat):
            w.setMinimumWidth(260)
        f.addRow('Código interno *', self.code)
        f.addRow('Código de barras (EAN/UPC)', self.barcode)
        f.addRow('Nombre comercial *', self.name)
        f.addRow('Marca / laboratorio', self.brand)
        f.addRow('Categoría *', self.cat)
        f.addRow('Estado', self.status)
        tabs.addTab(basic, 'Información básica')
        pharm = QWidget()
        pf = QFormLayout(pharm)
        self.active = QComboBox()
        self.active.setEditable(True)
        self.active.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.active.setPlaceholderText('Escribe o selecciona el principio activo')
        self.conc = QDoubleSpinBox()
        self.conc.setRange(0, 100000)
        self.conc.setDecimals(3)
        self.conc.setSingleStep(0.5)
        self.unit = QComboBox()
        self.unit.addItems(['mg', 'g', 'mcg', 'mg/mL', 'g/100 mL', '%', 'mL', 'UI', 'Otra'])
        self.form = QComboBox()
        self.form.addItems(['Tableta', 'Cápsula', 'Jarabe', 'Solución', 'Suspensión', 'Crema', 'Gel', 'Pomada', 'Gotas', 'Spray', 'Polvo', 'Otro'])
        self.route = QLineEdit()
        self.presentation = QLineEdit()
        self.present_qty = QSpinBox()
        self.present_qty.setRange(1, 100000)
        self.present_unit = QComboBox()
        self.present_unit.addItems(['tabletas', 'cápsulas', 'mL', 'g', 'unidades', 'sobres', 'ampollas', 'Otro'])
        self.rx = QComboBox()
        self.rx.addItems(['No', 'Sí'])
        self.control = QComboBox()
        self.control.addItems(['No', 'Sí'])
        pf.addRow('Principio activo *', self.active)
        pf.addRow('Concentración', self.conc)
        pf.addRow('Unidad', self.unit)
        pf.addRow('Forma farmacéutica', self.form)
        pf.addRow('Vía de administración', self.route)
        pf.addRow('Presentación', self.presentation)
        pf.addRow('Cantidad por presentación', self.present_qty)
        pf.addRow('Unidad de presentación', self.present_unit)
        self.dispensing = QComboBox()
        self.dispensing.addItems(CATEGORIAS_DISPENSACION)
        self.dispensing.currentTextChanged.connect(self._sync_dispensing)
        self.sanitary = QLineEdit()
        self.sanitary.setPlaceholderText('Registro sanitario (MINSA)')
        pf.addRow('Categoría de dispensación', self.dispensing)
        pf.addRow('Registro sanitario', self.sanitary)
        pf.addRow('Requiere receta', self.rx)
        pf.addRow('Control especial', self.control)
        self.control.currentTextChanged.connect(lambda text: text == 'Sí' and self.rx.setCurrentText('Sí'))  # controlado implica receta
        tabs.addTab(pharm, 'Información farmacéutica')
        other = QWidget()
        of = QFormLayout(other)
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 10000000)
        self.price.setDecimals(2)
        self.price.setPrefix('C$ ')
        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100000)
        self.desc = QTextEdit()
        self.alt = QLineEdit()
        self.alt.setPlaceholderText('Separar nombres alternativos con coma')
        of.addRow('Precio de venta *', self.price)
        of.addRow('Stock mínimo', self.minimum)
        of.addRow('Nombres alternativos', self.alt)
        of.addRow('Descripción', self.desc)
        tabs.addTab(other, 'Inventario y otros')
        buttons = QHBoxLayout()
        save = QPushButton('Guardar')
        save.setObjectName('primaryButton')
        cancel = QPushButton('Cancelar')
        cancel.setObjectName('secondaryButton')
        buttons.addStretch()
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        root.addLayout(buttons)
        save.clicked.connect(self.validate)
        cancel.clicked.connect(self.reject)
        pa, ma, ca = model.catalog_options()
        self.active.addItem('Seleccionar...', None)
        [self.active.addItem(x['nombre'], x['id']) for x in pa]
        self.brand.addItem('Sin marca', None)
        [self.brand.addItem(x['nombre'], x['id']) for x in ma]
        self.cat.addItem('Seleccionar...', None)
        [self.cat.addItem(x['nombre'], x['id']) for x in ca]
        if product:
            self.load(product)

    def _sync_dispensing(self, category):
        """Sugiere receta/control según la categoría; luego se pueden ajustar a mano."""
        self.rx.setCurrentText('No' if category == 'Venta libre' else 'Sí')
        self.control.setCurrentText('Sí' if category == 'Controlado' else 'No')

    def regulatory(self):
        return clean_text(self.sanitary.text()) or None, self.dispensing.currentText()

    def select_data(self, combo, value):
        i = combo.findData(value)
        combo.setCurrentIndex(i if i >= 0 else 0)

    def load(self, p):
        self.code.setText(p['codigo'])
        self.barcode.setText(p['codigo_barras'] or '')
        self.name.setText(p['nombre_comercial'])
        self.select_data(self.active, p['principio_activo_id'])
        self.select_data(self.brand, p['marca_id'])
        self.select_data(self.cat, p['categoria_id'])
        self.conc.setValue(float(p['concentracion'] or 0))
        self.unit.setCurrentText(p['unidad_concentracion'] or 'mg')
        self.form.setCurrentText(p['forma_farmaceutica'] or 'Tableta')
        self.route.setText(p['via_administracion'] or '')
        self.presentation.setText(p['presentacion'] or '')
        self.present_qty.setValue(p['cantidad_presentacion'] or 1)
        self.present_unit.setCurrentText(p['unidad_presentacion'] or 'unidades')
        self.price.setValue(float(p['precio_venta']))
        self.minimum.setValue(p['stock_minimo'])
        self.desc.setPlainText(p['descripcion'] or '')
        self.alt.setText(', '.join(self.model.alternatives(p['id'])))
        self.status.setCurrentText(p['estado'])
        self.sanitary.setText(p.get('registro_sanitario') or '')
        self.dispensing.setCurrentText(p.get('categoria_dispensacion') or 'Venta libre')
        # Se cargan al final: así lo guardado manda sobre el valor sugerido por la categoría
        self.rx.setCurrentText('Sí' if p['requiere_receta'] else 'No')
        self.control.setCurrentText('Sí' if p['control_especial'] else 'No')

    def validate(self):
        barcode = clean_text(self.barcode.text())
        if barcode and (not barcode.isdigit() or not 8 <= len(barcode) <= 14):
            warning(self, 'Validación', 'El código de barras debe contener únicamente dígitos y tener entre 8 y 14 caracteres.')
            return
        if not clean_text(self.code.text()) or not clean_text(self.name.text()) or (not clean_text(self.active.currentText())) or (self.cat.currentData() is None):
            warning(self, 'Validación', 'Código, nombre, principio activo y categoría son obligatorios.')
            return
        if self.price.value() <= 0:
            warning(self, 'Validación', 'El precio de venta debe ser mayor que cero.')
            return
        self.accept()

    def data(self):
        active_text = clean_text(self.active.currentText())
        active_id = self.model.get_or_create_active(active_text)
        brand_text = clean_text(self.brand.currentText())
        brand_id = self.model.get_or_create_brand(brand_text)
        return (clean_text(self.code.text()), clean_text(self.barcode.text()) or None, clean_text(self.name.text()), active_id, brand_id, self.conc.value() or None, self.unit.currentText(), self.form.currentText(), clean_text(self.route.text()) or None, clean_text(self.presentation.text()) or None, self.present_qty.value(), self.present_unit.currentText(), clean_text(self.desc.toPlainText()) or None, self.cat.currentData(), self.price.value(), self.minimum.value(), self.rx.currentText() == 'Sí', self.control.currentText() == 'Sí', self.status.currentText())

    def alternatives(self):
        return [x.strip() for x in self.alt.text().split(',') if x.strip()]

class LotsDialog(QDialog):
    data_changed = Signal()

    def __init__(self, model, product, user, parent=None):
        super().__init__(parent)

        self.model = model
        self.product = product
        self.user = user
        self._rows = []

        self.setWindowTitle(
            f"Gestión de lotes · {product['nombre_comercial']}"
        )
        self.resize(980, 520)

        layout = QVBoxLayout(self)

        title = QLabel(
            f"{product['nombre_comercial']} · "
            f"{product['concentracion'] or ''} "
            f"{product['unidad_concentracion'] or ''}"
        )
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.summary = QLabel()
        self.summary.setObjectName("mutedLabel")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Lote",
                "Vencimiento",
                "Cantidad",
                "Compra",
                "Proveedor",
                "Recepción",
                "Estado",
                "Ubicación",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()

        add_button = QPushButton("Registrar entrada")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.add_lot)
        actions.addWidget(add_button)

        adjust_button = QPushButton("Ajustar lote seleccionado")
        adjust_button.setObjectName("secondaryButton")
        adjust_button.clicked.connect(self.adjust_lot)
        actions.addWidget(adjust_button)

        block_button = QPushButton("Bloquear / liberar lote")
        block_button.setObjectName("secondaryButton")
        block_button.clicked.connect(self.toggle_block)
        actions.addWidget(block_button)

        refresh_button = QPushButton("Actualizar")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.load)
        actions.addWidget(refresh_button)

        actions.addStretch()

        close_button = QPushButton("Cerrar")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)

        layout.addLayout(actions)

        self.load()

    def load(self):
        try:
            rows = self.model.lots(self.product["id"])
            self._rows = rows
            self.table.setRowCount(len(rows))

            available = sum(
                int(row["cantidad_actual"] or 0)
                for row in rows
                if row["estado"] == "Disponible"
                and row["fecha_vencimiento"]
            )
            total = sum(
                int(row["cantidad_actual"] or 0)
                for row in rows
            )

            self.summary.setText(
                f"Lotes registrados: {len(rows)} · "
                f"Stock disponible: {available} · "
                f"Total físico: {total}"
            )

            keys = [
                "numero_lote",
                "fecha_vencimiento",
                "cantidad_actual",
                "precio_compra",
                "proveedor",
                "fecha_recepcion",
                "estado",
                "ubicacion",
            ]

            for row_index, row_data in enumerate(rows):
                for column, key in enumerate(keys):
                    value = row_data.get(key)

                    if key == "precio_compra":
                        text = format_currency(value)
                    elif value is None or value == "":
                        text = "—"
                    else:
                        text = str(value)

                    cell = (colored_item(text, (value - date.today()).days) if key == 'fecha_vencimiento' and value else QTableWidgetItem(text))
                    self.table.setItem(row_index, column, cell)

            self.table.resizeRowsToContents()

        except Exception as exc:
            self._rows = []
            self.table.setRowCount(0)
            self.summary.setText("No se pudieron cargar los lotes.")
            error(
                self,
                "Lotes",
                f"No se pudieron cargar los lotes.\n{exc}",
            )

    def add_lot(self):
        from views.inventario_window import LotDialog

        provider_model = (
            self.model.provider_model
            if hasattr(self.model, "provider_model")
            else ProveedorModel(self.model.db)
        )

        dialog = LotDialog(
            self.model,
            provider_model,
            self,
        )

        index = dialog.product.findData(self.product["id"])

        if index >= 0:
            dialog.product.setCurrentIndex(index)

        dialog.product.setEnabled(False)

        if not dialog.exec():
            return

        try:
            InventarioModel(self.model.db).create_lot(
                dialog.data(),
                self.user,
            )
            info(
                self,
                "Lotes",
                "Entrada registrada correctamente.",
            )
            self.load()
            self.data_changed.emit()
        except Exception as exc:
            error(
                self,
                "Lotes",
                f"No se pudo registrar la entrada.\n{exc}",
            )

    def adjust_lot(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self._rows):
            warning(
                self,
                "Lotes",
                "Selecciona el lote que deseas ajustar.",
            )
            return

        from models.ajuste_model import AjusteModel
        from views.ajustes_dialog import AjusteTipoDialog

        adjustments = AjusteModel(self.model.db)
        dialog = AjusteTipoDialog(adjustments.lots(), self)
        index = dialog.lot.findData(self._rows[row]["id"])

        if index >= 0:
            dialog.lot.setCurrentIndex(index)

        if not dialog.exec():
            return

        try:
            adjustments.apply(self.user, *dialog.data())
            info(
                self,
                "Lotes",
                "Ajuste registrado correctamente.",
            )
            self.load()
            self.data_changed.emit()
        except Exception as exc:
            error(
                self,
                "Lotes",
                f"No se pudo ajustar el lote.\n{exc}",
            )

    def toggle_block(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self._rows):
            warning(self, "Lotes", "Selecciona el lote que deseas bloquear o liberar.")
            return

        lot = self._rows[row]
        blocking = lot["estado"] != "Cuarentena"
        action = "bloquear (cuarentena)" if blocking else "liberar"
        reason, accepted = QInputDialog.getText(
            self, "Lotes", f"Motivo para {action} el lote {lot['numero_lote']}:"
        )
        if not accepted:
            return

        try:
            new_state = InventarioModel(self.model.db).set_blocked(
                self.user, lot["id"], blocking, reason
            )
            info(self, "Lotes", f"Lote {lot['numero_lote']}: estado {new_state}.")
            self.load()
            self.data_changed.emit()
        except Exception as exc:
            error(self, "Lotes", f"No se pudo cambiar el estado del lote.\n{exc}")


class ProductosPage(QWidget):
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.model = ProductoModel(db)
        self.provider = ProveedorModel(db)
        self.extra = ProductoExtraModel(db)
        self.build()
        self.refresh()

    def build(self):
        lay = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel('Productos')
        title.setObjectName('pageTitle')
        self.search = QLineEdit()
        self.search.setPlaceholderText('Buscar por código, nombre, marca, principio activo o alias…')
        self.search.textChanged.connect(self.refresh)
        self.filter = QComboBox()
        self.filter.addItems(['Todos', 'Activos', 'Stock bajo', 'Sin stock', 'Próximos a vencer', 'Vencidos'])
        self.filter.currentTextChanged.connect(self.refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.search, 1)
        header.addWidget(self.filter)
        lay.addLayout(header)
        actions = QHBoxLayout()
        self.add = QPushButton('＋ Nuevo producto')
        self.add.setObjectName('primaryButton')
        self.add.clicked.connect(self.new)
        actions.addWidget(self.add)
        self.edit = QPushButton('Editar')
        self.edit.setObjectName('secondaryButton')
        self.edit.clicked.connect(self.edit_selected)
        actions.addWidget(self.edit)
        self.lots_btn = QPushButton('Ver lotes')
        self.lots_btn.setObjectName('secondaryButton')
        self.lots_btn.clicked.connect(self.view_lots)
        actions.addWidget(self.lots_btn)
        self.subs_btn = QPushButton('Sustitutos')
        self.subs_btn.setObjectName('secondaryButton')
        self.subs_btn.clicked.connect(self.view_substitutes)
        actions.addWidget(self.subs_btn)
        self.prices_btn = QPushButton('Historial de precios')
        self.prices_btn.setObjectName('secondaryButton')
        self.prices_btn.clicked.connect(self.view_price_history)
        actions.addWidget(self.prices_btn)
        if not can(self.user, 'gestionar_productos'):
            self.add.setVisible(False)  # el vendedor solo consulta el catálogo
            self.edit.setVisible(False)
        actions.addStretch()
        lay.addLayout(actions)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(['Código', 'Producto', 'Principio activo', 'Forma', 'Presentación', 'Categoría', 'Precio', 'Stock', 'Vence', 'Estado'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.edit_selected)
        lay.addWidget(self.table, 1)

    def refresh(self):
        try:
            rows = self.model.list_all(self.search.text().strip(), self.filter.currentText())
            self.table.setRowCount(len(rows))
            self._rows = rows
            for r, x in enumerate(rows):
                vals = [x['codigo'], f"{x['nombre_comercial']} {x['concentracion'] or ''} {x['unidad_concentracion'] or ''}", x['principio_activo'], x['forma_farmaceutica'], x['presentacion'] or '—', x['categoria'], format_currency(x['precio_venta']), x['stock'], x['proximo_vencimiento'] or '—', x['estado']]
                for c, v in enumerate(vals):
                    self.table.setItem(r, c, QTableWidgetItem(str(v)))
                self.table.setItem(r, 7, stock_item(x['stock'], x['stock_minimo']))
                if x['proximo_vencimiento']:
                    self.table.setItem(r, 8, colored_item(x['proximo_vencimiento'], (x['proximo_vencimiento'] - date.today()).days))
        except Exception as e:
            error(self, 'Productos', f'No se pudieron cargar los productos.\n{e}')

    def selected(self):
        r = self.table.currentRow()
        return self._rows[r] if r >= 0 and r < len(self._rows) else None

    def new(self):
        d = ProductDialog(self.model, parent=self)
        if d.exec():
            try:
                data = d.data()
                pid = self.model.create(data)
                self.model.save_alternatives(pid, d.alternatives())
                self.extra.save_regulatory(self.user, pid, *d.regulatory(), data[14], data[14], requiere_receta=d.rx.currentText() == 'Sí', control_especial=d.control.currentText() == 'Sí')
                info(self, 'Productos', 'Producto registrado. Ahora puedes registrar sus lotes desde Inventario.')
                self.refresh()
                self.data_changed.emit()
            except Exception as e:
                error(self, 'Productos', f'No se pudo guardar el producto.\n{e}')

    def edit_selected(self):
        p = self.selected()
        if not p:
            warning(self, 'Productos', 'Selecciona un producto.')
            return
        full = self.model.get(p['id'])
        d = ProductDialog(self.model, full, self)
        if d.exec():
            try:
                data = d.data()
                self.model.update(p['id'], data)
                self.model.save_alternatives(p['id'], d.alternatives())
                self.extra.save_regulatory(self.user, p['id'], *d.regulatory(), full['precio_venta'], data[14], requiere_receta=d.rx.currentText() == 'Sí', control_especial=d.control.currentText() == 'Sí')
                info(self, 'Productos', 'Producto actualizado.')
                self.refresh()
                self.data_changed.emit()
            except Exception as e:
                error(self, 'Productos', f'No se pudo actualizar.\n{e}')

    def view_substitutes(self):
        p = self.selected()
        if not p:
            warning(self, 'Productos', 'Selecciona un producto.')
            return
        SubstitutesDialog(p['nombre_comercial'], self.extra.substitutes(p['id']), self).exec()

    def view_price_history(self):
        p = self.selected()
        if not p:
            warning(self, 'Productos', 'Selecciona un producto.')
            return
        rows = [[h['fecha'], format_currency(h['precio_anterior']), format_currency(h['precio_nuevo']), h['usuario']] for h in self.extra.price_history(p['id'])]
        TableDialog(f"Precios · {p['nombre_comercial']}", ['Fecha', 'Anterior', 'Nuevo', 'Usuario'], rows, self).exec()

    def view_lots(self):
        product = self.selected()

        if not product:
            warning(
                self,
                "Lotes",
                "Selecciona un producto.",
            )
            return

        try:
            full_product = self.model.get(product["id"])

            if not full_product:
                warning(
                    self,
                    "Lotes",
                    "No se encontró la información del producto.",
                )
                return

            dialog = LotsDialog(
                self.model,
                full_product,
                self.user,
                self,
            )

            dialog.data_changed.connect(self.refresh)
            dialog.data_changed.connect(self.data_changed.emit)
            dialog.exec()
            self.refresh()

        except Exception as exc:
            error(
                self,
                "Lotes",
                f"No se pudo abrir la gestión de lotes.\n{exc}",
            )
