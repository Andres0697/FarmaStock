class UsuarioController:
    def __init__(self, model):
        self.model = model

    def list(self):
        return self.model.list_all()
