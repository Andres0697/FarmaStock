"""Exportación de tablas a Excel (openpyxl) y PDF (reportlab) y recibo de venta."""
from datetime import datetime
from pathlib import Path

from utils.helpers import format_currency


def export_excel(path: str, title: str, headers: list[str], rows: list[list]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = title[:30]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="1976D2")
    for row in rows:
        ws.append([str(v) if not isinstance(v, (int, float)) else v for v in row])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(len(str(c.value or "")) for c in col) + 3)
    wb.save(path)


def export_pdf(path: str, title: str, headers: list[str], rows: list[list]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    data = [headers] + [[str(v) for v in r] for r in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fc")])]))
    doc.build([Paragraph(f"FarmaStock · {title}", styles["Title"]),
               Paragraph(datetime.now().strftime("Generado: %d/%m/%Y %H:%M"), styles["Normal"]), Spacer(1, 10), table])


def export_by_extension(path: str, title: str, headers: list[str], rows: list[list]) -> None:
    (export_excel if Path(path).suffix.lower() == ".xlsx" else export_pdf)(path, title, headers, rows)


def sale_receipt_pdf(path: str, header: dict, lines: list[dict]) -> None:
    """Recibo/factura. Los datos fiscales (RUC, autorización DGI) se completan en la sección marcada."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    st = getSampleStyleSheet()
    rows = [["Producto", "Lote", "Cant.", "Precio", "Subtotal"]] + [
        [l["nombre_comercial"], l["numero_lote"], l["cantidad"], format_currency(l["precio_unitario"]), format_currency(l["subtotal"])] for l in lines]
    table = Table(rows, colWidths=[150, 60, 35, 55, 60], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1"))]))
    totals = Table([["Subtotal", format_currency(header["subtotal"])], ["Descuento", format_currency(header["descuento"])], ["TOTAL", format_currency(header["total"])]],
                   colWidths=[300, 60], hAlign="RIGHT")
    totals.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
    doc = SimpleDocTemplate(path, pagesize=A5, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    doc.build([
        Paragraph("FarmaStock · Farmacia", st["Title"]),
        Paragraph("RUC: ____________ &nbsp; Autorización DGI: ____________ &nbsp; Dirección: ____________", st["Normal"]),
        Spacer(1, 6),
        Paragraph(f"<b>Factura/Recibo:</b> {header['numero_factura'] or header['id']} &nbsp; <b>Fecha:</b> {header['fecha']:%d/%m/%Y %H:%M}", st["Normal"]),
        Paragraph(f"<b>Cliente:</b> {header['cliente']} {('· RUC ' + header['cliente_ruc']) if header.get('cliente_ruc') else ''}", st["Normal"]),
        Paragraph(f"<b>Cajero:</b> {header['usuario']} &nbsp; <b>Pago:</b> {header['metodo_pago']}", st["Normal"]),
        Spacer(1, 8), table, Spacer(1, 8), totals, Spacer(1, 12),
        Paragraph("Conserve este documento para cualquier devolución. Medicamentos sujetos a verificación de lote.", st["Italic"])])
