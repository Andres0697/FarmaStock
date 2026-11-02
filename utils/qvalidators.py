"""Validadores de Qt (QValidator) para impedir datos inválidos mientras el usuario escribe.

Cada función devuelve un validador listo para `line_edit.setValidator(...)`. La validación
definitiva sigue haciéndose en la capa de lógica; estos validadores son la primera barrera.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QDoubleValidator, QRegularExpressionValidator

# Letras (con tildes y ñ), números, espacios y signos comunes de nombres comerciales.
_NOMBRE = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,&()/%+\-]*"


def _regex(pattern: str, parent=None) -> QRegularExpressionValidator:
    return QRegularExpressionValidator(QRegularExpression(pattern), parent)


def name_validator(parent=None):
    return _regex(_NOMBRE, parent)


def phone_validator(parent=None):
    return _regex(r"[0-9 +()\-]{0,25}", parent)


def email_validator(parent=None):
    # Permite escribir de forma parcial; el formato completo se confirma al guardar.
    return _regex(r"[A-Za-z0-9._%+\-@]{0,120}", parent)


def code_validator(parent=None):
    return _regex(r"[A-Za-z0-9._\-/]{0,50}", parent)


def username_validator(parent=None):
    return _regex(r"[A-Za-z0-9._\-]{0,40}", parent)


def document_validator(parent=None):
    return _regex(r"[A-Za-z0-9\-]{0,30}", parent)


def money_validator(maximum: float = 10_000_000, parent=None) -> QDoubleValidator:
    validator = QDoubleValidator(0.0, maximum, 2, parent)
    validator.setNotation(QDoubleValidator.Notation.StandardNotation)
    return validator


def apply(widget, validator, max_length: int | None = None, placeholder: str | None = None) -> None:
    """Asigna validador (y opcionalmente largo máximo y texto de ayuda) a un QLineEdit."""
    widget.setValidator(validator)
    if max_length:
        widget.setMaxLength(max_length)
    if placeholder:
        widget.setPlaceholderText(placeholder)
