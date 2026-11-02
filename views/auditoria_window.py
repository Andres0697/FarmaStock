from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QTabWidget, QVBoxLayout, QWidget

from models.auditoria_model import AuditoriaModel
from models.ajuste_model import AjusteModel
from utils.messages import error
from utils.ui import button, fill_table, make_table, page_header


class AuditoriaPage(QWidget):
    """Bitácora de auditoría, desviaciones FEFO e historial de ajustes."""
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.model, self.adjustments = AuditoriaModel(db), AjusteModel(db)
        lay = QVBoxLayout(self)
        self.filter = QComboBox(); self.filter.addItem("Todas las acciones", "")
        self.filter.currentIndexChanged.connect(self.refresh_events)
        lay.addLayout(page_header("Auditoría", self.filter, button("Actualizar", "secondary", self.refresh)))
        tabs = QTabWidget(); lay.addWidget(tabs, 1)
        self.events = make_table(["Fecha", "Usuario", "Acción", "Entidad", "ID", "Detalle"])
        self.fefo = make_table(["Fecha", "Venta", "Usuario", "Producto", "Lote sugerido", "Vence", "Lote vendido", "Vence", "Motivo"])
        self.adj = make_table(["Fecha", "Tipo", "Producto", "Lote", "Antes", "Después", "Motivo", "Usuario"])
        for table, name in ((self.events, "Bitácora"), (self.fefo, "Desviaciones FEFO"), (self.adj, "Ajustes de inventario")):
            tabs.addTab(table, name)

    def refresh(self) -> None:
        try:
            current = self.filter.currentData()
            self.filter.blockSignals(True)
            self.filter.clear(); self.filter.addItem("Todas las acciones", "")
            for action in self.model.actions():
                self.filter.addItem(action, action)
            self.filter.setCurrentIndex(max(0, self.filter.findData(current)))
            self.filter.blockSignals(False)
            self.refresh_events()
            fill_table(self.fefo, [[r["fecha"], r["venta_id"], r["usuario"], r["nombre_comercial"], r["lote_sugerido"], r["vence_sugerido"],
                                    r["lote_vendido"], r["vence_vendido"], r["motivo"]] for r in self.model.fefo_deviations()])
            fill_table(self.adj, [[r["fecha"], r["tipo"], r["nombre_comercial"], r["numero_lote"], r["cantidad_antes"], r["cantidad_despues"],
                                   r["motivo"], r["usuario"]] for r in self.adjustments.history()])
        except Exception as exc:
            error(self, "Auditoría", f"No se pudo cargar la auditoría.\n{exc}")

    def refresh_events(self) -> None:
        rows = self.model.list_events(self.filter.currentData() or "")
        fill_table(self.events, [[r["fecha"], r["usuario"], r["accion"], r["entidad"], r["entidad_id"], r["detalle"]] for r in rows])
