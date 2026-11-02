class ProductoController:
    def __init__(self, model):
        self.model = model

    def list(self, search="", filter_name="Todos"):
        return self.model.list_all(search, filter_name)
