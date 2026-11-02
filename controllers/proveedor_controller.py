class ProveedorController:
    def __init__(self, model):
        self.model = model

    def list(self, search=""):
        return self.model.list_all(search)
