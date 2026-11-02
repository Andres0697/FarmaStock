from PySide6.QtCore import Signal,QDate
from PySide6.QtWidgets import *
from models.inventario_model import InventarioModel
from models.producto_model import ProductoModel
from models.proveedor_model import ProveedorModel
from utils.messages import info,warning,error
from models.ajuste_model import AjusteModel
from utils.permisos import can
from utils.ui import colored_item,stock_item
from views.ajustes_dialog import AjusteTipoDialog

class LotDialog(QDialog):
    def __init__(self,product_model,provider_model,parent=None):
        super().__init__(parent); self.pm=product_model; self.pr=provider_model; self.setWindowTitle('Registrar entrada / lote'); self.resize(520,420); f=QFormLayout(self)
        self.product=QComboBox(); self.lot=QLineEdit(); self.mfg=QDateEdit(QDate.currentDate()); self.mfg.setCalendarPopup(True); self.exp=QDateEdit(QDate.currentDate().addMonths(12)); self.exp.setCalendarPopup(True); self.qty=QSpinBox(); self.qty.setRange(1,1000000); self.qty.setValue(10); self.cost=QDoubleSpinBox(); self.cost.setRange(0,10000000); self.cost.setDecimals(2); self.cost.setPrefix('C$ '); self.provider=QComboBox(); self.received=QDateEdit(QDate.currentDate()); self.received.setCalendarPopup(True); self.location=QLineEdit(); self.location.setPlaceholderText('Ej. Estante A-03')
        f.addRow('Producto *',self.product); f.addRow('Número de lote *',self.lot); f.addRow('Fecha de fabricación',self.mfg); f.addRow('Fecha de vencimiento *',self.exp); f.addRow('Cantidad *',self.qty); f.addRow('Precio de compra',self.cost); f.addRow('Proveedor',self.provider); f.addRow('Fecha de recepción',self.received); f.addRow('Ubicación',self.location); b=QHBoxLayout(); save=QPushButton('Registrar entrada'); save.setObjectName('primaryButton'); cancel=QPushButton('Cancelar'); cancel.setObjectName('secondaryButton'); b.addWidget(save); b.addWidget(cancel); f.addRow(b); save.clicked.connect(self.validate); cancel.clicked.connect(self.reject)
        rows=[]
        with self.pm.db.cursor() as (_,c): c.execute("SELECT id,nombre_comercial,concentracion,unidad_concentracion FROM productos WHERE estado='Activo' ORDER BY nombre_comercial"); rows=c.fetchall()
        for x in rows: self.product.addItem(f"{x['nombre_comercial']} · {x['concentracion'] or ''} {x['unidad_concentracion'] or ''}",x['id'])
        self.provider.addItem('Sin proveedor',None); [self.provider.addItem(x['nombre'],x['id']) for x in self.pr.active()]
    def validate(self):
        if not self.lot.text().strip(): warning(self,'Validación','El número de lote es obligatorio.'); return
        if self.exp.date()<QDate.currentDate(): warning(self,'Validación','La fecha de vencimiento no puede estar en el pasado.'); return
        if self.mfg.date()>self.exp.date(): warning(self,'Validación','La fabricación no puede ser posterior al vencimiento.'); return
        self.accept()
    def data(self): return (self.product.currentData(),self.lot.text().strip(),self.mfg.date().toPython(),self.exp.date().toPython(),self.qty.value(),self.cost.value(),self.provider.currentData(),self.received.date().toPython(),self.location.text().strip() or None)

class InventoryPage(QWidget):
    data_changed=Signal()
    def __init__(self,db,user): super().__init__(); self.db=db; self.user=user; self.model=InventarioModel(db); self.adjustments=AjusteModel(db); self.pm=ProductoModel(db); self.pr=ProveedorModel(db); self.build(); self.refresh()
    def build(self):
        lay=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('Inventario y lotes'); t.setObjectName('pageTitle'); h.addWidget(t); h.addStretch(); add=QPushButton('＋ Registrar entrada'); add.setObjectName('primaryButton'); add.clicked.connect(self.add_lot); self.expiry_filter=QComboBox(); self.expiry_filter.addItem('Vencen en 30 días',30); self.expiry_filter.addItem('Vencen en 60 días',60); self.expiry_filter.addItem('Vencen en 90 días',90); self.expiry_filter.setCurrentIndex(2); self.expiry_filter.currentIndexChanged.connect(self.refresh); h.addWidget(self.expiry_filter); h.addWidget(add); lay.addLayout(h)
        typed=QPushButton('Ajustar: merma / conteo / devolución'); typed.setObjectName('secondaryButton'); typed.clicked.connect(self.typed_adjust); h.addWidget(typed)
        if not can(self.user,'ajustar_inventario'):
            for b in (add,typed): b.setVisible(False)  # el vendedor no modifica inventario
        note=QLabel('El stock se controla por lote. Las ventas usan FEFO: primero sale el lote con vencimiento más cercano.'); note.setObjectName('mutedLabel'); lay.addWidget(note)
        tabs=QTabWidget(); self.low=QTableWidget(0,4); self.low.setHorizontalHeaderLabels(['Código','Producto','Stock disponible','Mínimo']); self.exp=QTableWidget(0,6); self.exp.setHorizontalHeaderLabels(['Código','Producto','Lote','Vencimiento','Cantidad','Días']); self.mov=QTableWidget(0,9); self.mov.setHorizontalHeaderLabels(['Fecha','Código','Producto','Lote','Movimiento','Cantidad','Saldo del lote','Motivo','Usuario'])
        for table in (self.low,self.exp,self.mov): table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setAlternatingRowColors(True); tabs.addTab(table,'')
        tabs.setTabText(0,'Stock bajo'); tabs.setTabText(1,'Vencimientos'); tabs.setTabText(2,'Movimientos'); lay.addWidget(tabs,1)
    def refresh(self):
        try:
            self.model.sync_expired()
            rows=self.model.low_stock(); self.low.setRowCount(len(rows));
            for r,x in enumerate(rows):
                for c,k in enumerate(['codigo','nombre_comercial','stock','stock_minimo']): self.low.setItem(r,c,stock_item(x[k],x['stock_minimo']) if k=='stock' else QTableWidgetItem(str(x[k])))
            rows=self.model.expiring(self.expiry_filter.currentData()); self.exp.setRowCount(len(rows));
            for r,x in enumerate(rows):
                for c,k in enumerate(['codigo','nombre_comercial','numero_lote','fecha_vencimiento','cantidad_actual','dias']): self.exp.setItem(r,c,colored_item(x[k],x['dias']) if k in ('fecha_vencimiento','dias') else QTableWidgetItem(str(x[k])))
            rows=self.model.movements(); self.mov.setRowCount(len(rows));
            for r,x in enumerate(rows):
                for c,k in enumerate(['fecha','codigo','nombre_comercial','numero_lote','tipo_movimiento','cantidad','saldo_lote','motivo','usuario']): self.mov.setItem(r,c,QTableWidgetItem('—' if x[k] is None or x[k]=='' else str(x[k])))
        except Exception as e: error(self,'Inventario',f'No se pudo cargar el inventario.\n{e}')
    def typed_adjust(self):
        d=AjusteTipoDialog(self.adjustments.lots(),self)
        if d.exec():
            try:
                self.adjustments.apply(self.user,*d.data()); info(self,'Inventario','Ajuste registrado correctamente.'); self.refresh(); self.data_changed.emit()
            except Exception as e: error(self,'Inventario',f'No se pudo aplicar el ajuste.\n{e}')
    def add_lot(self):
        d=LotDialog(self.pm,self.pr,self)
        if d.exec():
            try: self.model.create_lot(d.data(),self.user); info(self,'Inventario','Entrada registrada correctamente.'); self.refresh(); self.data_changed.emit()
            except Exception as e: error(self,'Inventario',f'No se pudo registrar el lote.\n{e}')
