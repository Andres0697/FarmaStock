"""Animaciones y hilo de verificación del login."""
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

BLUE = QColor("#1976d2")
TRACK = QColor("#dbe7f3")
GREEN = QColor("#2e9d57")
TEXT = QColor("#243447")
CORNER_RADIUS = 16
CIRCLE_RADIUS = 34


class AuthWorker(QObject):
    """Ejecuta el inicio de sesión fuera del hilo de la interfaz."""

    done = Signal(object, object)  # (usuario o None, excepción o None)

    def __init__(self, controller, username, password):
        super().__init__()
        self.controller = controller
        self.username = username
        self.password = password

    @Slot()
    def run(self):
        try:
            self.done.emit(self.controller.login(self.username, self.password), None)
        except Exception as exc:  # se informa a la ventana; no se pierde
            self.done.emit(None, exc)


class VerificationOverlay(QWidget):
    """Capa sobre el formulario: círculo girando al verificar y check al aprobar."""

    def __init__(self, parent):
        super().__init__(parent)
        self._mode = None  # "loading" | "success"
        self._text = ""
        self._angle = 0
        self._progress = 0.0

        self._spin = QVariantAnimation(self, startValue=0, endValue=360, duration=900)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._on_spin)

        self._draw = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=550)
        self._draw.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._draw.valueChanged.connect(self._on_draw)

        parent.installEventFilter(self)  # seguir el tamaño del formulario
        self.hide()

    # ------------------------------ estados ---------------------------
    def show_loading(self, text="Verificando credenciales…"):
        self._mode, self._text = "loading", text
        self._draw.stop()
        self._spin.start()
        self._cover_parent()

    def show_success(self, text):
        self._mode, self._text = "success", text
        self._spin.stop()
        self._progress = 0.0
        self._draw.start()
        self._cover_parent()

    def stop(self):
        self._spin.stop()
        self._draw.stop()
        self._mode = None
        self.hide()

    # --------------------------- interno ------------------------------
    def _cover_parent(self):
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    def _on_spin(self, value):
        self._angle = value
        self.update()

    def _on_draw(self, value):
        self._progress = value
        self.update()

    # ----------------------------- dibujo -----------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 253))
        painter.drawRoundedRect(self.rect(), CORNER_RADIUS, CORNER_RADIUS)

        center = QPointF(self.width() / 2, self.height() / 2 - 16)
        if self._mode == "loading":
            self._paint_spinner(painter, center)
        elif self._mode == "success":
            self._paint_check(painter, center)

        self._paint_text(painter, center)

    @staticmethod
    def _circle_rect(center):
        r = CIRCLE_RADIUS
        return QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r)

    def _paint_spinner(self, painter, center):
        rect = self._circle_rect(center)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(TRACK, 6))
        painter.drawEllipse(rect)

        pen = QPen(BLUE, 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Qt mide los ángulos en 1/16 de grado y en sentido antihorario
        painter.drawArc(rect, -self._angle * 16, -110 * 16)

    def _paint_check(self, painter, center):
        """Primero se dibuja el círculo verde y luego la palomita."""
        circle_part = min(1.0, self._progress / 0.6)
        check_part = max(0.0, (self._progress - 0.6) / 0.4)

        pen = QPen(GREEN, 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawArc(self._circle_rect(center), 90 * 16, int(-360 * 16 * circle_part))

        a = center + QPointF(-14, 2)
        b = center + QPointF(-4, 12)
        c = center + QPointF(15, -9)
        first = min(1.0, check_part / 0.4)
        second = max(0.0, (check_part - 0.4) / 0.6)
        if first > 0:
            painter.drawLine(a, a + (b - a) * first)
        if second > 0:
            painter.drawLine(b, b + (c - b) * second)

    def _paint_text(self, painter, center):
        font = QFont(self.font())
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(GREEN if self._mode == "success" else TEXT)
        area = QRectF(10, center.y() + CIRCLE_RADIUS + 14, self.width() - 20, 40)
        painter.drawText(area, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._text)


def make_shake_animation(widget, home, amplitude=10, duration=380):
    """Animación de vibración horizontal (error de acceso), reutilizable.

    `home` es la posición normal del widget. Se crea una sola vez y se lanza
    con .start() cada vez que haga falta.
    """
    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setDuration(duration)
    keyframes = (0, 0), (0.15, -1), (0.35, 1), (0.55, -0.6), (0.75, 0.6), (1, 0)
    for step, factor in keyframes:
        animation.setKeyValueAt(step, home + QPoint(round(amplitude * factor), 0))
    return animation
