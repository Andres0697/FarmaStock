"""Diálogos de apoyo de la pantalla de ventas."""
from html import escape

from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from utils.helpers import clean_text, format_currency
from utils.messages import error, warning


def _button_row(*buttons):
    row = QHBoxLayout()
    row.addStretch()
    for button in buttons:
        row.addWidget(button)
    return row


class DeviationDialog(QDialog):
    """Avisa que se vende un lote distinto al que vence primero (FEFO)."""

    def __init__(self, product_name, suggested_text, chosen_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lote distinto al sugerido")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        message = QLabel(
            f"<b>{escape(product_name)}</b><br><br>"
            f"Hay un lote que vence antes:<br>"
            f"&nbsp;&nbsp;• Sugerido (FEFO): <b>{escape(suggested_text)}</b><br>"
            f"&nbsp;&nbsp;• Seleccionado: <b>{escape(chosen_text)}</b><br><br>"
            "Puedes continuar; quedará registrado como desviación."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Motivo (opcional). Ej.: era el que estaba al frente")
        self.reason.setMaxLength(255)
        layout.addWidget(self.reason)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)

        accept = QPushButton("Continuar con este lote")
        accept.setObjectName("primaryButton")
        accept.clicked.connect(self.accept)
        accept.setDefault(True)

        layout.addLayout(_button_row(cancel, accept))

    def motivo(self):
        return clean_text(self.reason.text())


class PrescriptionDialog(QDialog):
    """Pide los datos de la receta para productos con receta o control especial."""

    def __init__(self, product_name, controlled=False, current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datos de la receta")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        kind = "de control especial" if controlled else "con receta"
        intro = QLabel(f"<b>{escape(product_name)}</b> es un medicamento {kind}.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        current = current or {}
        form = QFormLayout()
        self.patient = QLineEdit(current.get("paciente", ""))
        self.doctor = QLineEdit(current.get("medico", ""))
        self.number = QLineEdit(current.get("numero_receta", ""))
        for field in (self.patient, self.doctor, self.number):
            field.setMaxLength(160)
        form.addRow("Paciente *", self.patient)
        form.addRow("Médico *", self.doctor)
        form.addRow("N.º de receta *", self.number)
        layout.addLayout(form)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)

        save = QPushButton("Guardar receta")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._validate)
        save.setDefault(True)

        layout.addLayout(_button_row(cancel, save))

    def _validate(self):
        if not all(map(clean_text, (self.patient.text(), self.doctor.text(), self.number.text()))):
            warning(self, "Receta", "Paciente, médico y número de receta son obligatorios.")
            return
        self.accept()

    def data(self):
        return {
            "paciente": clean_text(self.patient.text()),
            "medico": clean_text(self.doctor.text()),
            "numero_receta": clean_text(self.number.text()),
        }


def build_receipt_html(header, rows):
    """Comprobante de venta en HTML (sirve para vista previa y PDF)."""
    lines = "".join(
        f"<tr><td>{escape(str(r['nombre_comercial']))}<br>"
        f"<small>Lote: {escape(str(r['numero_lote'] or '—'))}</small></td>"
        f"<td align='center'>{r['cantidad']}</td>"
        f"<td align='right'>{format_currency(r['precio_unitario'])}</td>"
        f"<td align='right'>{format_currency(r['subtotal'])}</td></tr>"
        for r in rows
    )

    payment = escape(str(header["metodo_pago"]))
    change = ""
    if header["metodo_pago"] == "Efectivo" and header["monto_recibido"] is not None:
        received = float(header["monto_recibido"])
        change = (
            f"<tr><td>Recibido</td><td align='right'>{format_currency(received)}</td></tr>"
            f"<tr><td>Cambio</td><td align='right'>"
            f"{format_currency(max(0, received - float(header['total'])))}</td></tr>"
        )

    status = (
        "<p align='center'><b style='color:#b42318'>VENTA ANULADA</b></p>"
        if header["estado"] == "Anulada"
        else ""
    )

    return f"""
    <h2 align="center" style="margin-bottom:0">FarmaStock</h2>
    <p align="center" style="margin-top:2px">Comprobante de venta</p>
    {status}
    <p>Venta N.º <b>{header['id']}</b><br>
       Fecha: {header['fecha']}<br>
       Atendió: {escape(str(header['usuario']))}</p>
    <table width="100%" cellspacing="0" cellpadding="4" border="0">
      <tr style="background:#eaf2fa">
        <th align="left">Producto</th><th>Cant.</th>
        <th align="right">Precio</th><th align="right">Subtotal</th></tr>
      {lines}
    </table>
    <hr>
    <table width="100%" cellspacing="0" cellpadding="3">
      <tr><td>Subtotal</td><td align="right">{format_currency(header['subtotal'])}</td></tr>
      <tr><td>Descuento</td><td align="right">{format_currency(header['descuento'])}</td></tr>
      <tr><td><b>TOTAL</b></td>
          <td align="right"><b>{format_currency(header['total'])}</b></td></tr>
      <tr><td>Pago</td><td align="right">{payment}</td></tr>
      {change}
    </table>
    <p align="center"><small>Documento interno. Este comprobante no sustituye la
    factura fiscal.</small></p>
    """


class ReceiptDialog(QDialog):
    """Vista previa del comprobante, con opción de guardarlo como PDF."""

    def __init__(self, header, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Comprobante · Venta #{header['id']}")
        self.resize(460, 600)
        self.header = header
        self.html = build_receipt_html(header, rows)

        layout = QVBoxLayout(self)
        view = QTextBrowser()
        view.setObjectName("receiptPreview")
        view.setHtml(self.html)
        layout.addWidget(view, 1)

        pdf = QPushButton("Guardar PDF")
        pdf.setObjectName("secondaryButton")
        pdf.clicked.connect(self.save_pdf)

        close = QPushButton("Cerrar")
        close.setObjectName("primaryButton")
        close.clicked.connect(self.accept)
        close.setDefault(True)

        layout.addLayout(_button_row(pdf, close))

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar comprobante", f"venta_{self.header['id']}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
            document = QTextDocument()
            document.setHtml(self.html)
            document.print_(writer)
        except Exception as exc:
            error(self, "Comprobante", f"No se pudo guardar el PDF.\n{exc}")
