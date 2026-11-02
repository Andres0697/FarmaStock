"""Componentes visuales reutilizables. Usan la paleta existente de main.qss."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QTableWidgetItem, QVBoxLayout

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# (fondo, texto) por urgencia de vencimiento
EXPIRY_VENCIDO = ("#fde8e8", "#9b1c1c")
EXPIRY_30 = ("#fdecec", "#c62828")
EXPIRY_60 = ("#fff1e0", "#b45309")
EXPIRY_90 = ("#fff9db", "#8a6d00")
EXPIRY_OK = ("#e6f4ea", "#1e7d3a")


def expiry_level(days) -> tuple[str, tuple[str, str]]:
    """Devuelve (etiqueta, (fondo, texto)) según los días que faltan para vencer."""
    if days is None:
        return "—", ("#ffffff", "#243447")
    days = int(days)
    if days < 0:
        return "Vencido", EXPIRY_VENCIDO
    if days <= 30:
        return "≤ 30 días", EXPIRY_30
    if days <= 60:
        return "≤ 60 días", EXPIRY_60
    if days <= 90:
        return "≤ 90 días", EXPIRY_90
    return "Vigente", EXPIRY_OK


def colored_item(text, days) -> QTableWidgetItem:
    """Celda con color de urgencia según días a vencer."""
    _, (bg, fg) = expiry_level(days)
    item = QTableWidgetItem(str(text))
    item.setBackground(QColor(bg)); item.setForeground(QColor(fg))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


def stock_item(stock, minimum) -> QTableWidgetItem:
    """Rojo si no hay stock, ámbar si está en el mínimo o por debajo."""
    item = QTableWidgetItem(str(stock))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if int(stock) == 0:
        item.setBackground(QColor(EXPIRY_30[0])); item.setForeground(QColor(EXPIRY_30[1]))
    elif int(stock) <= int(minimum or 0):
        item.setBackground(QColor(EXPIRY_60[0])); item.setForeground(QColor(EXPIRY_60[1]))
    return item


class StatCard(QFrame):
    """Tarjeta de indicador: etiqueta, valor grande y nota; el color de acento va a la izquierda."""

    def __init__(self, title: str, accent: str = "#1976d2", note: str = ""):
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(f"#statCard {{ border-left: 5px solid {accent}; }}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18); shadow.setOffset(0, 3); shadow.setColor(QColor(16, 42, 67, 40))
        self.setGraphicsEffect(shadow)
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 12, 14, 12); lay.setSpacing(2)
        self.title = QLabel(title); self.title.setObjectName("cardLabel")
        self.value = QLabel("0"); self.value.setObjectName("cardValue")
        self.note = QLabel(note); self.note.setObjectName("cardNote")
        for w in (self.title, self.value, self.note):
            lay.addWidget(w)

    def set_value(self, value, note: str | None = None) -> None:
        self.value.setText(str(value))
        if note is not None:
            self.note.setText(note)


def logo_pixmap(size: int, small: bool = False) -> QPixmap:
    pix = QPixmap(str(ASSETS / ("logo_small.png" if small else "logo.png")))
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def make_table(headers: list[str]):
    """Tabla de solo lectura con el estilo estándar de la aplicación."""
    from PySide6.QtWidgets import QHeaderView, QTableWidget
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    return table


def fill_table(table, rows: list[list]) -> None:
    """Rellena la tabla con una lista de filas (valores ya formateados)."""
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, value if isinstance(value, QTableWidgetItem) else QTableWidgetItem("—" if value is None else str(value)))


def page_header(title: str, *buttons):
    """Encabezado estándar: título a la izquierda y botones de acción a la derecha."""
    from PySide6.QtWidgets import QHBoxLayout
    row = QHBoxLayout()
    label = QLabel(title); label.setObjectName("pageTitle")
    row.addWidget(label); row.addStretch()
    for b in buttons:
        row.addWidget(b)
    return row


def button(text: str, kind: str = "secondary", slot=None):
    """Botón con el estilo primario/secundario/peligro del tema."""
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(text); b.setObjectName(f"{kind}Button")
    if slot:
        b.clicked.connect(slot)
    return b
