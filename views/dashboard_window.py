from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QMenuBar,
    QMessageBox,
    QToolBar,
    QToolButton,
    QMenu,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from views.productos_window import ProductosPage
from views.categorias_window import CategoriasPage
from views.proveedores_window import ProveedoresPage
from views.ventas_window import SalesPage
from views.usuarios_window import UsuariosPage
from views.inventario_window import InventoryPage
from views.caja_window import CajaPage
from views.clientes_window import ClientesPage
from views.compras_window import ComprasPage
from views.reportes_window import ReportesPage
from views.auditoria_window import AuditoriaPage
from utils.backup import BackupService
from utils.permisos import can
from utils.branding import LOGO_ICON, logo_pixmap
from utils.helpers import format_currency
from utils.messages import confirm


class DashboardWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.setWindowTitle("FarmaStock | Gestión de farmacia")
        self.resize(1360, 820)
        self.setMinimumSize(1180, 720)
        self.build()
        self.load_dashboard()

    def build(self):
        central = QWidget()
        self.setCentralWidget(central)

        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setMinimumWidth(250)
        side.setMaximumWidth(290)

        sidebar_layout = QVBoxLayout(side)
        sidebar_layout.setContentsMargins(18, 22, 18, 18)
        sidebar_layout.setSpacing(4)

        sidebar_layout.addLayout(self.build_brand())

        user_label = QLabel(f"{self.user['nombre']}\n{self.user['rol']}")
        user_label.setObjectName("sidebarUser")
        user_label.setWordWrap(True)
        user_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        user_label.setMinimumHeight(58)
        user_label.setSizePolicy(
            user_label.sizePolicy().horizontalPolicy(),
            user_label.sizePolicy().verticalPolicy(),
        )
        sidebar_layout.addWidget(user_label)
        sidebar_layout.addSpacing(15)

        self.nav = []
        self.nav_entries = []  # (texto, índice) en el orden del menú lateral
        self.add_nav(sidebar_layout, "Inicio", 0)
        self.add_nav(sidebar_layout, "Productos", 1)
        self.add_nav(sidebar_layout, "Inventario", 2)
        self.add_nav(sidebar_layout, "Ventas", 3)
        self.add_nav(sidebar_layout, "Categorías", 4)
        self.add_nav(sidebar_layout, "Proveedores", 5)

        # Los módulos adicionales se muestran según los permisos del rol.
        self.extra_modules = self.available_modules()
        for index, (label, _factory) in self.extra_modules.items():
            self.add_nav(sidebar_layout, label, index)

        if self.user["rol"] == "Administrador":
            self.add_nav(sidebar_layout, "Usuarios", 6)

        sidebar_layout.addStretch()

        logout_button = QPushButton("Cerrar sesión")
        logout_button.setObjectName("dangerButton")
        logout_button.setMinimumHeight(40)
        logout_button.clicked.connect(self.logout)
        sidebar_layout.addWidget(logout_button)

        self.side_panel = side
        main.addWidget(side)

        content = QFrame()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 22, 26, 22)
        self.content_layout = content_layout

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        main.addWidget(content, 1)

        self.home = self.home_page()
        self.stack.addWidget(self.home)

        self.pages = {
            1: ProductosPage(self.db, self.user),
            2: InventoryPage(self.db, self.user),
            3: SalesPage(self.db, self.user),
            4: CategoriasPage(self.db, self.user),
            5: ProveedoresPage(self.db, self.user),
        }

        for index, (_label, factory) in self.extra_modules.items():
            self.pages[index] = factory()

        if self.user["rol"] == "Administrador":
            self.pages[6] = UsuariosPage(self.db, self.user)

        for page in self.pages.values():
            self.stack.addWidget(page)
            page.data_changed.connect(self.load_dashboard)

        self.build_actions()

    def available_modules(self):
        """{índice: (texto del menú, función que crea la página)} según permisos."""
        modules = {
            7: ("Caja", lambda: CajaPage(self.db, self.user)),  # todo usuario que cobra
            8: ("Clientes", lambda: ClientesPage(self.db, self.user)),
        }
        if can(self.user, "compras"):
            modules[9] = ("Compras", lambda: ComprasPage(self.db, self.user))
        if can(self.user, "reportes"):
            self.backup_service = BackupService(self.db) if can(self.user, "respaldos") else None
            modules[10] = ("Reportes", lambda: ReportesPage(self.db, self.user, self.backup_service))
        if can(self.user, "ver_auditoria"):
            modules[11] = ("Auditoría", lambda: AuditoriaPage(self.db, self.user))
        return modules

    def build_brand(self):
        """Emblema del logo en una insignia blanca + nombre (se lee sobre el azul)."""
        row = QHBoxLayout()
        row.setSpacing(10)

        badge = QLabel()
        badge.setObjectName("brandBadge")
        badge.setFixedSize(54, 54)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = logo_pixmap(LOGO_ICON, 40, 40)
        if pixmap:
            badge.setPixmap(pixmap)
            row.addWidget(badge)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        brand = QLabel("FarmaStock")
        brand.setObjectName("sidebarBrand")
        tagline = QLabel("Gestión de farmacia")
        tagline.setObjectName("sidebarTag")
        texts.addWidget(brand)
        texts.addWidget(tagline)
        row.addLayout(texts, 1)

        return row

    def add_nav(self, layout, text, index):
        button = QPushButton(text)
        button.setObjectName("navButton")
        button.setMinimumHeight(36)
        button.setSizePolicy(
            button.sizePolicy().horizontalPolicy(),
            button.sizePolicy().verticalPolicy(),
        )
        button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
        layout.addWidget(button)
        self.nav.append(button)
        self.nav_entries.append((text, index))

    def navigate(self, index):
        if index == 0:
            self.stack.setCurrentWidget(self.home)
            self.load_dashboard()
        else:
            page = self.pages.get(index)
            if not page:
                return
            self.stack.setCurrentWidget(page)
            getattr(page, "refresh", lambda: None)()
        self.current_index = index
        self.sync_actions()

    # ------------------------------------------------------------------
    # Menús, barra de herramientas y acciones reutilizables (QAction)
    # ------------------------------------------------------------------
    def _action(self, text, slot, shortcut=None, icon=None, tip=None, checkable=False):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
        action.setStatusTip(tip or text.replace("&", ""))
        action.setToolTip(f"{text.replace('&', '')}" + (f" ({QKeySequence(shortcut).toString()})" if shortcut else ""))
        action.setCheckable(checkable)
        action.triggered.connect(lambda checked=False, target=slot: target())
        return action

    def build_actions(self):
        """Una sola definición de cada acción, compartida por el menú, la barra y los atajos."""
        std = QStyle.StandardPixmap
        self.current_index = 0
        self.nav_actions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for position, (label, index) in enumerate(self.nav_entries, start=1):
            shortcut = f"Ctrl+{position}" if position <= 9 else f"Ctrl+Shift+{position - 9}"
            action = self._action(label, lambda checked=False, i=index: self.navigate(i), shortcut,
                                  tip=f"Ir a {label}", checkable=True)
            group.addAction(action)
            self.nav_actions[index] = action
        self.nav_actions[0].setChecked(True)

        self.act_import = self._action("&Importar categorías (CSV)…", self.import_categories, "Ctrl+O", std.SP_DialogOpenButton,
                                       "Importar categorías desde un archivo CSV")
        self.act_export_cat = self._action("Exportar categorías (CSV)…", self.export_categories, None, std.SP_DialogSaveButton,
                                           "Exportar las categorías a un archivo CSV")
        self.act_export = self._action("&Exportar reporte…", self.export_report, "Ctrl+E", std.SP_DialogSaveButton,
                                       "Exportar a Excel o PDF el reporte generado")
        self.act_backup = self._action("&Respaldar ahora", self.backup_now, "Ctrl+B", std.SP_DriveHDIcon,
                                       "Crear un respaldo de la base de datos")
        self.act_refresh = self._action("&Actualizar", self.refresh_current, "F5", std.SP_BrowserReload, "Actualizar la pantalla actual")
        self.act_logout = self._action("Cerrar &sesión", self.logout, "Ctrl+L", std.SP_DialogCloseButton, "Cerrar la sesión actual")
        self.act_exit = self._action("&Salir", self.close, "Ctrl+Q", std.SP_TitleBarCloseButton, "Cerrar la aplicación")
        self.act_about = self._action("&Acerca de FarmaStock", self.about, "F1", std.SP_MessageBoxInformation, "Información del sistema")
        self.nav_actions[0].setIcon(self.style().standardIcon(std.SP_DirHomeIcon))

        tools = QToolBar("Herramientas")
        tools.setObjectName("mainToolBar")
        tools.setMovable(False)
        self.content_layout.insertWidget(0, tools)
        tools.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for index in (0, 3, 1):  # inicio, ventas, productos
            if index in self.nav_actions:
                tools.addAction(self.nav_actions[index])
        tools.addSeparator()
        for action in (self.act_import, self.act_export, self.act_backup, self.act_refresh):
            tools.addAction(action)
        tools.addSeparator()
        tools.addAction(self.act_logout)
        tools.setVisible(False)  # oculta por defecto; se muestra desde Ver > Barra de herramientas

        bar = QMenuBar()
        bar.setNativeMenuBar(False)
        bar.setVisible(False)  # oculta por defecto para no alterar el diseño
        self.content_layout.insertWidget(0, bar)
        file_menu = bar.addMenu("&Archivo")
        for action in (self.act_import, self.act_export_cat, self.act_export, self.act_backup):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.act_logout)
        file_menu.addAction(self.act_exit)
        view_menu = bar.addMenu("&Ver")
        for action in self.nav_actions.values():
            view_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(tools.toggleViewAction())
        view_menu.addAction(self.act_refresh)
        help_menu = bar.addMenu("A&yuda")
        help_menu.addAction(self.act_about)

        # Sin elementos nuevos en pantalla: la barra se muestra con Alt o F10 y los menús salen con clic derecho en el menú lateral
        self.menu_bar = bar
        bar.triggered.connect(lambda _action: bar.setVisible(False))
        self.act_show_bar = self._action("Mostrar barra de menús", self.toggle_menu_bar, "F10",
                                         tip="Mostrar u ocultar la barra de menús (también con la tecla Alt)")
        self.popup_menu = QMenu(self)
        for menu in (file_menu, view_menu, help_menu):
            self.popup_menu.addMenu(menu)
        self.popup_menu.addSeparator()
        self.popup_menu.addAction(self.act_show_bar)
        self.side_panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.side_panel.customContextMenuRequested.connect(lambda pos: self.popup_menu.exec(self.side_panel.mapToGlobal(pos)))

        # Los atajos funcionan aunque los menús estén ocultos
        self.addActions(list(self.nav_actions.values()) + [self.act_import, self.act_export_cat, self.act_export, self.act_backup,
                                                          self.act_refresh, self.act_logout, self.act_exit, self.act_about, self.act_show_bar])

        reports = self.pages.get(10)
        if reports is not None:
            reports.exportable_changed.connect(lambda _has: self.sync_actions())
        self.sync_actions()

    def sync_actions(self):
        """Mantiene sincronizados menú, barra y menú lateral con la pantalla y los permisos."""
        for index, action in self.nav_actions.items():
            action.setChecked(index == self.current_index)
        self.act_import.setEnabled(can(self.user, "gestionar_productos") and 4 in self.pages)
        self.act_export_cat.setEnabled(4 in self.pages)
        reports = self.pages.get(10)
        self.act_export.setEnabled(reports is not None and bool(reports.rows))
        self.act_backup.setEnabled(getattr(self, "backup_service", None) is not None)

    def toggle_menu_bar(self):
        self.menu_bar.setVisible(not self.menu_bar.isVisible())

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():  # como en las aplicaciones de Windows
            self.toggle_menu_bar()
        super().keyReleaseEvent(event)

    def import_categories(self):
        self.navigate(4)
        self.pages[4].import_csv()

    def export_categories(self):
        self.navigate(4)
        self.pages[4].export_csv()

    def export_report(self):
        self.navigate(10)
        self.pages[10].export()

    def backup_now(self):
        if getattr(self, "backup_service", None) is not None:
            self.backup_service.start()

    def refresh_current(self):
        self.navigate(self.current_index)

    def about(self):
        QMessageBox.information(self, "FarmaStock", "FarmaStock\nSistema de gestión de farmacia.\nPython · PySide6 · MySQL · SQLAlchemy")

    def home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header = QHBoxLayout()
        title = QLabel("Resumen de farmacia")
        title.setObjectName("pageTitle")
        header.addWidget(title)

        header.addStretch()

        current_user = QLabel(f"Usuario: {self.user['nombre']}")
        current_user.setWordWrap(True)
        current_user.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        current_user.setMaximumWidth(320)
        header.addWidget(current_user)
        layout.addLayout(header)

        cards = QHBoxLayout()
        self.cards = {}

        for key, label in [
            ("products", "Productos activos"),
            ("units", "Unidades disponibles"),
            ("low", "Stock bajo"),
            ("exp", "Por vencer"),
            ("sales", "Ventas de hoy"),
        ]:
            frame = QFrame()
            frame.setObjectName("statCard")
            card_layout = QVBoxLayout(frame)

            card_label = QLabel(label)
            card_label.setObjectName("cardLabel")
            card_label.setWordWrap(True)

            value = QLabel("0")
            value.setObjectName("cardValue")

            card_layout.addWidget(card_label)
            card_layout.addWidget(value)
            self.cards[key] = value
            cards.addWidget(frame)

        layout.addLayout(cards)

        panels = QHBoxLayout()

        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_title = QLabel("Stock crítico")
        left_title.setObjectName("sectionTitle")
        left_layout.addWidget(left_title)
        self.low = self.table(["Código", "Producto", "Stock", "Mínimo"])
        left_layout.addWidget(self.low)
        panels.addWidget(left_frame)

        expiry_frame = QFrame()
        expiry_layout = QVBoxLayout(expiry_frame)
        expiry_title = QLabel("Próximos vencimientos")
        expiry_title.setObjectName("sectionTitle")
        expiry_layout.addWidget(expiry_title)
        self.exp = self.table(
            ["Código", "Producto", "Lote", "Vencimiento", "Días"]
        )
        expiry_layout.addWidget(self.exp)
        panels.addWidget(expiry_frame)

        layout.addLayout(panels, 1)
        return page

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        return table

    def load_dashboard(self):
        try:
            with self.db.cursor() as (_, cursor):
                cursor.execute(
                    """SELECT
                        (SELECT COUNT(*) FROM productos WHERE estado='Activo') products,
                        (SELECT COALESCE(SUM(cantidad_actual),0)
                         FROM lotes
                         WHERE estado='Disponible'
                           AND fecha_vencimiento>=CURDATE()) units,
                        (SELECT COUNT(*)
                         FROM productos p
                         WHERE p.estado='Activo'
                           AND p.stock_minimo>0
                           AND COALESCE(
                               (SELECT SUM(cantidad_actual)
                                FROM lotes l
                                WHERE l.producto_id=p.id
                                  AND l.estado='Disponible'
                                  AND l.fecha_vencimiento>=CURDATE()),0
                           )<=p.stock_minimo) low,
                        (SELECT COUNT(*)
                         FROM lotes
                         WHERE cantidad_actual>0
                           AND fecha_vencimiento BETWEEN CURDATE()
                               AND DATE_ADD(CURDATE(),INTERVAL 90 DAY)) exp,
                        (SELECT COALESCE(SUM(total),0)
                         FROM ventas
                         WHERE estado='Completada'
                           AND DATE(fecha)=CURDATE()) sales"""
                )
                stats = cursor.fetchone()

                cursor.execute(
                    """SELECT
                        p.codigo,
                        p.nombre_comercial,
                        COALESCE(SUM(
                            CASE
                                WHEN l.estado='Disponible'
                                 AND l.fecha_vencimiento>=CURDATE()
                                THEN l.cantidad_actual
                                ELSE 0
                            END
                        ),0) stock,
                        p.stock_minimo
                    FROM productos p
                    LEFT JOIN lotes l ON l.producto_id=p.id
                    WHERE p.estado='Activo'
                    GROUP BY p.id
                    HAVING stock<=p.stock_minimo
                    ORDER BY stock,p.nombre_comercial
                    LIMIT 8"""
                )
                low = cursor.fetchall()

                cursor.execute(
                    """SELECT
                        p.codigo,
                        p.nombre_comercial,
                        l.numero_lote,
                        l.fecha_vencimiento,
                        DATEDIFF(l.fecha_vencimiento,CURDATE()) dias
                    FROM lotes l
                    JOIN productos p ON p.id=l.producto_id
                    WHERE l.cantidad_actual>0
                      AND l.fecha_vencimiento BETWEEN CURDATE()
                          AND DATE_ADD(CURDATE(),INTERVAL 90 DAY)
                    ORDER BY l.fecha_vencimiento
                    LIMIT 8"""
                )
                expiry = cursor.fetchall()

            self.cards["products"].setText(str(stats["products"]))
            self.cards["units"].setText(str(stats["units"]))
            self.cards["low"].setText(str(stats["low"]))
            self.cards["exp"].setText(str(stats["exp"]))
            self.cards["sales"].setText(format_currency(stats["sales"]))

            self.fill(
                self.low,
                low,
                ["codigo", "nombre_comercial", "stock", "stock_minimo"],
            )
            self.fill(
                self.exp,
                expiry,
                ["codigo", "nombre_comercial", "numero_lote",
                 "fecha_vencimiento", "dias"],
            )
        except Exception:
            pass

    def fill(self, table, rows, keys):
        table.setRowCount(len(rows))
        for row, data in enumerate(rows):
            for column, key in enumerate(keys):
                table.setItem(row, column, QTableWidgetItem(str(data[key])))

    def logout(self):
        if confirm(
            self,
            "Cerrar sesión",
            "¿Está seguro de que desea cerrar sesión?",
        ):
            self.logout_requested.emit()
