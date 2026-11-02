from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from controllers.login_controller import LoginController
from utils.branding import LOGO_FULL, logo_pixmap
from utils.messages import error
from views.login_animations import AuthWorker, VerificationOverlay, make_shake_animation

MIN_VERIFY_MS = 800    # la animación de "verificando" dura al menos esto
SUCCESS_HOLD_MS = 950  # tiempo que se ve el check antes de abrir el sistema
LOGO_WIDTH = 230
from utils.qvalidators import apply, username_validator

class LoginWindow(QWidget):
    login_success = Signal(dict)

    def __init__(self, db):
        super().__init__()
        self.controller = LoginController(db)
        self._busy = False
        self._thread = None
        self._worker = None
        self._pending = None          # resultado de la verificación aún sin mostrar
        self._min_time_done = False
        self._shake = None            # animación de vibración (se crea al primer error)

        self.setWindowTitle("FarmaStock | Iniciar sesión")
        self.setFixedSize(460, 640)
        self.build()

    # ------------------------------ interfaz ---------------------------
    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(55, 30, 55, 40)
        root.setSpacing(12)

        root.addStretch()
        root.addWidget(self._build_logo())
        root.addWidget(self._build_subtitle())
        root.addSpacing(6)
        root.addWidget(self._build_card())
        root.addStretch()

        self.overlay = VerificationOverlay(self.card)

        self.password.returnPressed.connect(self.login)
        self.user.returnPressed.connect(self.login)

    def _build_logo(self):
        """Logo de assets/logo.png; si no existe, el nombre en texto."""
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = logo_pixmap(LOGO_FULL, LOGO_WIDTH, 150)
        if pixmap:
            label.setPixmap(pixmap)
        else:
            label.setText("FarmaStock")
            label.setObjectName("loginLogo")
        return label

    @staticmethod
    def _build_subtitle():
        subtitle = QLabel("Control de inventario y ventas")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return subtitle

    def _build_card(self):
        self.card = QFrame()
        self.card.setObjectName("loginCard")

        form = QVBoxLayout(self.card)
        form.setContentsMargins(28, 26, 28, 26)
        form.setSpacing(10)

        title = QLabel("Bienvenido")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.user = QLineEdit()
        apply(self.user, username_validator(self.user), 40)
        self.user.setPlaceholderText("Usuario")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Contraseña")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.show_password = QCheckBox("Mostrar contraseña")
        self.show_password.toggled.connect(self._toggle_password_visibility)

        self.msg = QLabel()
        self.msg.setObjectName("formMessage")
        self.msg.setWordWrap(True)

        self.login_button = QPushButton("Iniciar sesión")
        self.login_button.setObjectName("primaryButton")
        self.login_button.setMinimumHeight(44)
        self.login_button.clicked.connect(self.login)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.clicked.connect(self.clear_form)

        form.addWidget(title)
        form.addWidget(self.user)
        form.addWidget(self.password)
        form.addWidget(self.show_password)
        form.addWidget(self.msg)
        form.addSpacing(6)
        form.addWidget(self.login_button)
        form.addWidget(self.clear_button)
        return self.card

    def _toggle_password_visibility(self, visible):
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password.setEchoMode(mode)

    # --------------------------- iniciar sesión ------------------------
    def login(self):
        if self._busy:
            return

        username = self.user.text().strip()
        password = self.password.text()
        self.msg.clear()

        if not username or not password:
            self._show_error("Complete usuario y contraseña.")
            return

        self._start_verification(username, password)

    def _start_verification(self, username, password):
        """Muestra la animación y valida en un hilo aparte (no congela la ventana)."""
        self._busy = True
        self._pending = None
        self._min_time_done = False
        self._set_inputs_enabled(False)
        self.overlay.show_loading()

        self._thread = QThread(self)
        self._worker = AuthWorker(self.controller, username, password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_auth_result)
        self._thread.start()

        QTimer.singleShot(MIN_VERIFY_MS, self._on_min_time_done)

    def _on_auth_result(self, user, exception):
        self._stop_thread()
        self._pending = (user, exception)
        self._show_result_if_ready()

    def _on_min_time_done(self):
        self._min_time_done = True
        self._show_result_if_ready()

    def _show_result_if_ready(self):
        """Espera a tener el resultado Y a que pase el tiempo mínimo de animación."""
        if not self._busy or self._pending is None or not self._min_time_done:
            return

        user, exception = self._pending
        self._pending = None

        if exception is not None:
            self._end_verification()
            error(
                self,
                "Error de acceso",
                "No se pudo iniciar sesión. Verifique la conexión con MySQL.",
            )
        elif user is None:
            self._end_verification()
            self._show_error("Usuario o contraseña incorrectos, o usuario desactivado.")
        else:
            self.overlay.show_success(f"¡Bienvenido, {user['nombre']}!")
            QTimer.singleShot(SUCCESS_HOLD_MS, lambda: self._complete_login(user))

    def _complete_login(self, user):
        if not self._busy:  # la ventana se cerró o se reinició mientras tanto
            return
        self.login_success.emit(user)
        self._end_verification()

    # ------------------------------ estado -----------------------------
    def _show_error(self, text):
        self.msg.setText(text)
        self._shake_card()

    def _shake_card(self):
        if self._shake is None:
            self._shake = make_shake_animation(self.card, QPoint(self.card.pos()))
        if self._shake.state() != self._shake.State.Running:
            self._shake.start()

    def _set_inputs_enabled(self, enabled):
        for widget in (self.user, self.password, self.show_password,
                       self.login_button, self.clear_button):
            widget.setEnabled(enabled)

    def _end_verification(self):
        self._busy = False
        self.overlay.stop()
        self._set_inputs_enabled(True)

    def _stop_thread(self):
        if self._thread is None:
            return
        self._thread.quit()
        self._thread.wait()
        self._worker.deleteLater()
        self._thread.deleteLater()
        self._thread = self._worker = None

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:  # centrado en la pantalla cada vez que se muestra
            area = screen.availableGeometry()
            self.move(area.center() - self.rect().center())

    def clear_form(self):
        self._pending = None
        self._end_verification()
        self.user.clear()
        self.password.clear()
        self.msg.clear()
        self.user.setFocus()

    def closeEvent(self, event):
        self._stop_thread()
        self._busy = False
        super().closeEvent(event)
