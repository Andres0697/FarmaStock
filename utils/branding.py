"""Logo e iconos de la aplicación.

Los archivos viven en la carpeta `assets/`. Si falta alguno, las funciones
devuelven None y la pantalla muestra solo texto, sin fallar.
"""
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_FULL = "logo.png"        # emblema + nombre (para fondos claros)
LOGO_ICON = "logo_icon.png"   # solo el emblema
PIXEL_RATIO = 2.0             # se dibuja al doble para que se vea nítido


def logo_pixmap(filename, width, height=None):
    """Logo escalado con calidad dentro de width x height (mantiene proporción)."""
    path = ASSETS_DIR / filename
    if not path.exists():
        return None

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None

    box = QSize(round(width * PIXEL_RATIO), round((height or width * 2) * PIXEL_RATIO))
    scaled = pixmap.scaled(
        box,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(PIXEL_RATIO)
    return scaled


def app_icon():
    """Icono de la ventana (vacío si no existe el archivo)."""
    path = ASSETS_DIR / LOGO_ICON
    return QIcon(str(path)) if path.exists() else QIcon()
