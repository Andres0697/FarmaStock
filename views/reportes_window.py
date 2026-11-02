from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from models.reporte_model import ReporteModel
from utils.exporters import export_by_extension
from utils.messages import error, info, warning
from utils.permisos import can
from utils.ui import button, fill_table, make_table, page_header
from utils.workers import run_task


class ReportesPage(QWidget):
    """Reportes con rango de fechas y exportación a PDF/Excel. Incluye respaldo manual (administrador)."""
    data_changed = Signal()
    exportable_changed = Signal(bool)  # hay un reporte generado que se puede exportar

    def __init__(self, db, user, backup_service=None):
        super().__init__()
        self.user, self.model, self.backup = user, ReporteModel(db), backup_service
        self.headers, self.rows = [], []
        lay = QVBoxLayout(self)
        actions = [button("Exportar", "secondary", self.export)]
        if backup_service and can(user, "respaldos"):
            actions.append(button("Respaldar ahora", "secondary", backup_service.start))
            backup_service.finished.connect(lambda path: info(self, "Respaldo", f"Respaldo creado:\n{path}"))
            backup_service.failed.connect(lambda msg: warning(self, "Respaldo", f"No se pudo respaldar.\n{msg}"))
        lay.addLayout(page_header("Reportes", *actions))
        bar = QHBoxLayout()
        self.kind = QComboBox(); self.kind.addItems(list(self.model.reports))
        self.since = QDateEdit(QDate.currentDate().addDays(-30)); self.until = QDateEdit(QDate.currentDate())
        for d in (self.since, self.until):
            d.setCalendarPopup(True)
        for w in (QLabel("Reporte"), self.kind, QLabel("Desde"), self.since, QLabel("Hasta"), self.until, button("Generar", "primary", self.refresh)):
            bar.addWidget(w)
        bar.addStretch(); lay.addLayout(bar)
        self.table = make_table(["—"]); lay.addWidget(self.table, 1)

    def refresh(self) -> None:
        """Genera el reporte en un QThread para no congelar la ventana."""
        name = self.kind.currentText()
        report = self.model.reports[name]
        since, until = self.since.date().toPython(), self.until.date().toPython()
        if since > until:
            warning(self, "Reportes", "La fecha inicial no puede ser posterior a la final."); return

        def task(worker):
            worker.report(20, f"Generando «{name}»…")
            return report(since, until)

        def done(result):
            self.headers, self.rows = result
            self.table.setColumnCount(len(self.headers)); self.table.setHorizontalHeaderLabels(self.headers)
            fill_table(self.table, self.rows)
            self.exportable_changed.emit(bool(self.rows))

        run_task(self, f"Generando «{name}»…", task, done, lambda msg: error(self, "Reportes", f"No se pudo generar el reporte.\n{msg}"))

    def export(self) -> None:
        if not self.rows:
            warning(self, "Reportes", "Genera un reporte con datos antes de exportar."); return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar reporte", f"{self.kind.currentText()}.xlsx", "Excel (*.xlsx);;PDF (*.pdf)")
        if not path:  # el usuario canceló
            return
        title, headers, rows = self.kind.currentText(), list(self.headers), list(self.rows)

        def task(worker):
            worker.report(30, "Escribiendo archivo…")
            export_by_extension(path, title, headers, rows)
            return path

        run_task(self, "Exportando reporte…", task, lambda p: info(self, "Reportes", "Archivo exportado correctamente."),
                 lambda msg: error(self, "Reportes", f"No se pudo exportar.\n{msg}"), cancelable=False)
