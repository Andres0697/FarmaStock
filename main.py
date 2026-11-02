import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from database.connection import Database
from database.migrations import MigrationError, apply_pending
from models.inventario_model import InventarioModel
from utils.branding import app_icon
from utils.helpers import load_stylesheet
from views.dashboard_window import DashboardWindow
from views.login_window import LoginWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FarmaStock")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(load_stylesheet())

    try:
        db = Database()
        db.test_connection()
    except Exception:
        QMessageBox.critical(
            None,
            "FarmaStock",
            "No se pudo conectar con MySQL.\n"
            "Configure el archivo .env y ejecute sql/database.sql y sql/seed.sql.",
        )
        return 1

    try:
        apply_pending(db)  # deja el esquema al día (migraciones pendientes)
    except MigrationError as exc:
        QMessageBox.critical(
            None,
            "FarmaStock",
            f"No se pudo actualizar la base de datos.\n\n{exc}\n\n"
            "Restaure su respaldo o contacte al responsable técnico antes de continuar.",
        )
        return 1

    try:
        InventarioModel(db).sync_expired()  # marca como «Vencido» los lotes que ya vencieron
    except Exception:
        pass  # no debe impedir abrir la aplicación; las ventas filtran por fecha de todos modos

    login = LoginWindow(db)
    login.show()

    def open_dashboard(user):
        login.hide()
        app.dashboard = DashboardWindow(db, user)
        app.dashboard.showMaximized()
        app.dashboard.logout_requested.connect(back_to_login)

    def back_to_login():
        app.dashboard.close()
        login.clear_form()
        login.show()
        login.raise_()
        login.activateWindow()

    login.login_success.connect(open_dashboard)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
