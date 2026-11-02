from PySide6.QtCore import Signal
from utils.qvalidators import apply, name_validator, username_validator
from PySide6.QtWidgets import *
from models.usuario_model import UsuarioModel
from utils.helpers import clean_text
from utils.messages import info,warning,error
class UserDialog(QDialog):
    def __init__(self,row=None,parent=None):
        super().__init__(parent); self.row=row; self.setWindowTitle('Editar usuario' if row else 'Nuevo usuario'); f=QFormLayout(self); self.name=QLineEdit(); self.username=QLineEdit(); self.password=QLineEdit(); apply(self.name,name_validator(self.name),120); apply(self.username,username_validator(self.username),40,'Sin espacios'); self.password.setMaxLength(72); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.role=QComboBox(); self.role.addItems(['Administrador','Regente','Vendedor']); self.status=QComboBox(); self.status.addItems(['Activo','Inactivo']); f.addRow('Nombre *',self.name); f.addRow('Usuario *',self.username); f.addRow('Contraseña' + ('' if row else ' *'),self.password); f.addRow('Rol',self.role); f.addRow('Estado',self.status); b=QHBoxLayout(); s=QPushButton('Guardar'); s.setObjectName('primaryButton'); c=QPushButton('Cancelar'); c.setObjectName('secondaryButton'); b.addWidget(s); b.addWidget(c); f.addRow(b); s.clicked.connect(self.validate); c.clicked.connect(self.reject)
        if row: self.name.setText(row['nombre']); self.username.setText(row['usuario']); self.role.setCurrentText(row['rol']); self.status.setCurrentText(row['estado'])
    def validate(self):
        if not clean_text(self.name.text()) or not clean_text(self.username.text()): warning(self,'Validación','Nombre y usuario son obligatorios.'); return
        if not self.row and not self.password.text().strip(): warning(self,'Validación','La contraseña es obligatoria.'); return
        if ' ' in self.username.text().strip(): warning(self,'Validación','El usuario no debe contener espacios.'); return
        self.accept()
    def data(self): return clean_text(self.name.text()),clean_text(self.username.text()),self.password.text().strip(),self.role.currentText(),self.status.currentText()
class UsuariosPage(QWidget):
    data_changed=Signal()
    def __init__(self,db,user): super().__init__(); self.model=UsuarioModel(db); self.user=user; self.build(); self.refresh()
    def build(self):
        l=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('Usuarios'); t.setObjectName('pageTitle'); h.addWidget(t); h.addStretch(); add=QPushButton('＋ Nuevo usuario'); add.setObjectName('primaryButton'); add.clicked.connect(self.new); h.addWidget(add); l.addLayout(h); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['ID','Nombre','Usuario','Rol','Estado','Creado']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); l.addWidget(self.table); edit=QPushButton('Editar seleccionado'); edit.setObjectName('secondaryButton'); edit.clicked.connect(self.edit); l.addWidget(edit)
    def refresh(self):
        self.rows=self.model.list_all(); self.table.setRowCount(len(self.rows));
        for r,x in enumerate(self.rows):
            for c,k in enumerate(['id','nombre','usuario','rol','estado','fecha_creacion']): self.table.setItem(r,c,QTableWidgetItem(str(x[k])))
    def new(self):
        d=UserDialog(parent=self)
        if d.exec():
            try: self.model.create(*d.data()); info(self,'Usuarios','Usuario registrado.'); self.refresh()
            except Exception as e: error(self,'Usuarios',f'No se pudo guardar.\n{e}')
    def edit(self):
        r=self.table.currentRow()
        if r<0: warning(self,'Usuarios','Selecciona un usuario.'); return
        d=UserDialog(self.rows[r],self)
        if d.exec():
            try: self.model.update(self.rows[r]['id'],*d.data()); info(self,'Usuarios','Usuario actualizado.'); self.refresh()
            except Exception as e: error(self,'Usuarios',f'No se pudo actualizar.\n{e}')
