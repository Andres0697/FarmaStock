from models.auditoria_model import AuditoriaModel
from models.usuario_model import UsuarioModel
from utils.helpers import verify_password


class LoginController:
    def __init__(self, db):
        self.model = UsuarioModel(db)
        self.audit = AuditoriaModel(db)

    def login(self, usuario, password):
        user = self.model.authenticate(usuario, password, verify_password)
        if user:
            self._log("LOGIN", user["id"], f"Inicio de sesión de {usuario}")
        return user

    def _log(self, action, user_id, detail):
        try:
            self.audit.log_now(user_id, action, "usuarios", user_id, detail)
        except Exception:
            pass  # la bitácora no debe impedir el acceso si aún no se aplicó la migración 001
