from PySide6.QtWidgets import QMessageBox

def info(parent,title,message): QMessageBox.information(parent,title,message)
def warning(parent,title,message): QMessageBox.warning(parent,title,message)
def error(parent,title,message): QMessageBox.critical(parent,title,message)
def confirm(parent,title,message):
    box=QMessageBox(parent); box.setIcon(QMessageBox.Icon.Question); box.setWindowTitle(title); box.setText(message)
    yes=box.addButton('Sí',QMessageBox.ButtonRole.AcceptRole); box.addButton('No',QMessageBox.ButtonRole.RejectRole); box.exec(); return box.clickedButton() is yes
