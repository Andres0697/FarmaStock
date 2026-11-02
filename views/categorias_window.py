import csv

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QLabel, QVBoxLayout, QWidget

from models.categoria_model import CategoriaModel
from utils.helpers import clean_text
from utils.importers import ArchivoInvalido, parse_categorias_csv
from utils.messages import confirm, error, info, warning
from utils.permisos import can
from utils.qvalidators import apply, name_validator
from utils.ui import button, fill_table, make_table, page_header
from utils.workers import run_task


class CategoryDialog(QDialog):
    def __init__(self, row=None, parent=None):
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Editar categoría" if row else "Nueva categoría")
        form = QFormLayout(self)
        self.name, self.desc = QLineEdit(), QLineEdit()
        apply(self.name, name_validator(self.name), 100, "Ej.: Analgésicos")
        self.desc.setMaxLength(255)
        self.status = QComboBox(); self.status.addItems(["Activo", "Inactivo"])
        form.addRow("Nombre *", self.name); form.addRow("Descripción", self.desc); form.addRow("Estado", self.status)
        buttons = QHBoxLayout()
        buttons.addWidget(button("Guardar", "primary", self.validate)); buttons.addWidget(button("Cancelar", "secondary", self.reject))
        form.addRow(buttons)
        if row:
            self.name.setText(row["nombre"]); self.desc.setText(row["descripcion"] or ""); self.status.setCurrentText(row["estado"])

    def validate(self):
        if not clean_text(self.name.text()):
            warning(self, "Validación", "El nombre es obligatorio.")
            return
        self.accept()

    def data(self):
        return clean_text(self.name.text()), clean_text(self.desc.text()), self.status.currentText()


class CategoriasPage(QWidget):
    """Categorías: CRUD con SQLAlchemy, importar/exportar CSV (QFileDialog) en segundo plano (QThread)."""
    data_changed = Signal()

    def __init__(self, db, user):
        super().__init__()
        self.model, self.user, self.rows = CategoriaModel(db), user, []
        self.build()
        self.refresh()

    def build(self):
        layout = QVBoxLayout(self)
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar categoría…"); self.search.textChanged.connect(self.refresh)
        layout.addLayout(page_header("Categorías", self.search, button("＋ Nueva categoría", "primary", self.new)))
        self.table = make_table(["ID", "Nombre", "Descripción", "Estado"])
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(button("Editar seleccionada", "secondary", self.edit))
        self.delete_button = button("Eliminar seleccionada", "danger", self.remove)
        self.delete_button.setVisible(can(self.user, "gestionar_productos"))
        row.addWidget(self.delete_button); row.addStretch()
        layout.addLayout(row)

    def refresh(self):
        try:
            self.rows = self.model.list_all(self.search.text())
            fill_table(self.table, [[r["id"], r["nombre"], r["descripcion"], r["estado"]] for r in self.rows])
        except Exception as exc:
            error(self, "Categorías", f"No se pudieron cargar las categorías.\n{exc}")

    def _selected(self):
        index = self.table.currentRow()
        if index < 0:
            warning(self, "Categorías", "Selecciona una categoría.")
            return None
        return self.rows[index]

    def new(self):
        dialog = CategoryDialog(parent=self)
        if dialog.exec():
            try:
                self.model.create(*dialog.data()); info(self, "Categorías", "Categoría registrada."); self.refresh(); self.data_changed.emit()
            except Exception as exc:
                error(self, "Categorías", f"No se pudo guardar.\n{exc}")

    def edit(self):
        row = self._selected()
        if not row:
            return
        dialog = CategoryDialog(row, self)
        if dialog.exec():
            try:
                self.model.update(row["id"], *dialog.data()); info(self, "Categorías", "Categoría actualizada."); self.refresh(); self.data_changed.emit()
            except Exception as exc:
                error(self, "Categorías", str(exc))

    def remove(self):
        row = self._selected()
        if row and confirm(self, "Eliminar categoría", f"¿Eliminar la categoría «{row['nombre']}»?"):
            try:
                self.model.remove(self.user, row["id"]); self.refresh(); self.data_changed.emit()
            except Exception as exc:
                warning(self, "Categorías", str(exc))

    # ---- archivos (QFileDialog) + hilos (QThread) ----
    def import_csv(self):
        if not can(self.user, "gestionar_productos"):
            warning(self, "Categorías", "Tu rol no tiene permiso para importar categorías.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Importar categorías", "", "Archivos CSV (*.csv);;Todos los archivos (*)")
        if not path:  # el usuario canceló
            return

        def task(worker):
            worker.report(10, "Leyendo y validando el archivo…")
            rows, problems = parse_categorias_csv(path)
            if not rows:
                return {"creadas": 0, "omitidas": [], "problemas": problems}
            worker.report(60, "Guardando categorías…")
            result = self.model.import_rows(self.user, rows)
            result["problemas"] = problems
            return result

        def done(result):
            lines = [f"Categorías creadas: {result['creadas']}"]
            if result["omitidas"]:
                lines.append(f"Ya existían ({len(result['omitidas'])}): " + ", ".join(result["omitidas"][:8]) + ("…" if len(result["omitidas"]) > 8 else ""))
            if result["problemas"]:
                lines.append("Filas con problemas:\n" + "\n".join(result["problemas"][:8]))
            info(self, "Importación", "\n".join(lines))
            self.refresh(); self.data_changed.emit()

        run_task(self, "Importando categorías…", task, done, lambda msg: warning(self, "Importación", msg))

    def export_csv(self):
        if not self.rows:
            warning(self, "Categorías", "No hay categorías para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar categorías", "categorias.csv", "Archivos CSV (*.csv)")
        if not path:  # el usuario canceló
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        rows = list(self.rows)

        def task(worker):
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["nombre", "descripcion", "estado"])
                for r in rows:
                    writer.writerow([r["nombre"], r["descripcion"] or "", r["estado"]])
            return path

        run_task(self, "Exportando categorías…", task, lambda p: info(self, "Exportación", f"Archivo creado:\n{p}"),
                 lambda msg: warning(self, "Exportación", f"No se pudo guardar el archivo.\n{msg}"), cancelable=False)
