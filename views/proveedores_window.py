"""Proveedores: datos de los proveedores y entradas de mercadería."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.proveedor_model import ProveedorModel
from utils.helpers import clean_text
from utils.permisos import can
from utils.messages import error, info, warning
from utils.qvalidators import apply, email_validator, name_validator, phone_validator
from utils.validators import valid_email, valid_phone
from utils.messages import confirm
from views.entradas_widgets import EntriesTab

# (clave en la base de datos, título de la columna)
PROVIDER_COLUMNS = (
    ("id", "ID"),
    ("nombre", "Nombre"),
    ("telefono", "Teléfono"),
    ("correo", "Correo"),
    ("direccion", "Dirección"),
    ("estado", "Estado"),
)


class ProviderDialog(QDialog):
    """Formulario para crear o editar un proveedor."""

    def __init__(self, row=None, parent=None):
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Editar proveedor" if row else "Nuevo proveedor")

        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QLineEdit()
        apply(self.name, name_validator(self.name), 120, "Nombre del proveedor")
        apply(self.phone, phone_validator(self.phone), 25, "Ej.: 8888-8888")
        apply(self.email, email_validator(self.email), 120, "correo@dominio.com")
        self.address.setMaxLength(255)
        self.status = QComboBox()
        self.status.addItems(["Activo", "Inactivo"])

        form = QFormLayout(self)
        form.addRow("Nombre *", self.name)
        form.addRow("Teléfono", self.phone)
        form.addRow("Correo", self.email)
        form.addRow("Dirección", self.address)
        form.addRow("Estado", self.status)
        form.addRow(self._build_buttons())

        if row:
            self._fill(row)

    def _build_buttons(self):
        save = QPushButton("Guardar")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.validate)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(save)
        row.addWidget(cancel)
        return row

    def _fill(self, row):
        self.name.setText(row["nombre"])
        self.phone.setText(row["telefono"] or "")
        self.email.setText(row["correo"] or "")
        self.address.setText(row["direccion"] or "")
        self.status.setCurrentText(row["estado"])

    def validate(self):
        if not clean_text(self.name.text()):
            warning(self, "Validación", "El nombre es obligatorio.")
            return
        if self.phone.text().strip() and not valid_phone(self.phone.text()):
            warning(self, "Validación", "El teléfono no tiene un formato válido.")
            return
        if not valid_email(self.email.text()):
            warning(self, "Validación", "El correo no tiene un formato válido.")
            return
        self.accept()

    def data(self):
        return (
            clean_text(self.name.text()),
            clean_text(self.phone.text()),
            clean_text(self.email.text()),
            clean_text(self.address.text()),
            self.status.currentText(),
        )


class ProvidersTab(QWidget):
    """Lista de proveedores con alta y edición."""

    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.model = ProveedorModel(db)
        self.user = user
        self.rows = []
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar proveedor…")
        self.search.textChanged.connect(self.refresh)

        add = QPushButton("＋ Nuevo proveedor")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.new)

        toolbar.addStretch()
        toolbar.addWidget(self.search)
        toolbar.addWidget(add)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(PROVIDER_COLUMNS))
        self.table.setHorizontalHeaderLabels([title for _, title in PROVIDER_COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        edit = QPushButton("Editar seleccionado")
        edit.setObjectName("secondaryButton")
        edit.clicked.connect(self.edit)
        actions = QHBoxLayout()
        actions.addWidget(edit)
        if can(self.user, "compras"):
            remove = QPushButton("Eliminar seleccionado")
            remove.setObjectName("dangerButton")
            remove.clicked.connect(self.remove)
            actions.addWidget(remove)
        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self):
        self.rows = self.model.list_all(self.search.text().strip())
        self.table.setRowCount(len(self.rows))
        for row, provider in enumerate(self.rows):
            for column, (key, _) in enumerate(PROVIDER_COLUMNS):
                self.table.setItem(row, column, QTableWidgetItem(str(provider[key] or "—")))

    def remove(self):
        row = self.table.currentRow()
        if row < 0:
            warning(self, "Proveedores", "Selecciona un proveedor.")
            return
        provider = self.rows[row]
        if confirm(self, "Eliminar proveedor", f"¿Eliminar a «{provider['nombre']}»?"):
            try:
                self.model.remove(self.user, provider["id"])
            except Exception as exc:
                warning(self, "Proveedores", str(exc))
                return
            self.refresh()
            self.data_changed.emit()

    def new(self):
        dialog = ProviderDialog(parent=self)
        if not dialog.exec():
            return
        try:
            self.model.create(dialog.data())
        except Exception as exc:
            error(self, "Proveedores", f"No se pudo guardar.\n{exc}")
            return
        info(self, "Proveedores", "Proveedor registrado.")
        self.refresh()
        self.data_changed.emit()

    def edit(self):
        row = self.table.currentRow()
        if row < 0:
            warning(self, "Proveedores", "Selecciona un proveedor.")
            return

        dialog = ProviderDialog(self.rows[row], self)
        if not dialog.exec():
            return
        try:
            self.model.update(self.rows[row]["id"], dialog.data())
        except Exception as exc:
            error(self, "Proveedores", str(exc))
            return
        info(self, "Proveedores", "Proveedor actualizado.")
        self.refresh()
        self.data_changed.emit()


class ProveedoresPage(QWidget):
    """Pantalla de Proveedores: datos y, para administradores, entradas."""

    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.providers_tab = ProvidersTab(db, user)
        self.entries_tab = None

        layout = QVBoxLayout(self)
        title = QLabel("Proveedores")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.providers_tab, "Proveedores")
        self.providers_tab.data_changed.connect(self.data_changed)

        # Solo el administrador registra y consulta entradas de mercadería.
        if can(user, "compras"):
            self.entries_tab = EntriesTab(db, user)
            self.tabs.addTab(self.entries_tab, "Entradas de mercadería")
            self.entries_tab.data_changed.connect(self.data_changed)

        layout.addWidget(self.tabs)

    def refresh(self):
        """La llama el dashboard al entrar a esta pantalla."""
        self.providers_tab.refresh()
        if self.entries_tab:
            self.entries_tab.refresh()
