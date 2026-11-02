"""Carrito de venta sin dependencias de interfaz (fácil de probar)."""


class Cart:
    """Líneas de venta. Una línea es (producto, lote); lote None = FEFO automático."""

    def __init__(self):
        self.items = []

    # -- consulta ------------------------------------------------------
    def __len__(self):
        return len(self.items)

    def find(self, product_id, lot_id):
        return next(
            (
                item
                for item in self.items
                if item["producto_id"] == product_id and item["lote_id"] == lot_id
            ),
            None,
        )

    def units(self):
        return sum(item["cantidad"] for item in self.items)

    def subtotal(self):
        return sum(item["cantidad"] * item["precio"] for item in self.items)

    def units_of_product(self, product_id, exclude=None):
        """Unidades del producto en el carrito, sin contar la línea `exclude`."""
        return sum(
            item["cantidad"]
            for item in self.items
            if item["producto_id"] == product_id and item is not exclude
        )

    def maximum_for(self, item):
        """Máximo que puede tener esta línea según el stock conocido."""
        if item["lote_id"] is not None:
            return item["stock_lote"]
        return max(1, item["stock_producto"] - self.units_of_product(
            item["producto_id"], exclude=item))

    # -- cambios -------------------------------------------------------
    def add(self, item):
        """Agrega una línea o suma a la existente. Devuelve la línea."""
        existing = self.find(item["producto_id"], item["lote_id"])
        if existing:
            existing["cantidad"] += item["cantidad"]
            return existing
        self.items.append(item)
        return item

    def remove(self, index):
        if 0 <= index < len(self.items):
            self.items.pop(index)

    def clear(self):
        self.items.clear()

    def to_sale_items(self):
        """Datos para VentaModel.create_sale.

        Las líneas con lote elegido van primero para reservar su lote antes de
        que el FEFO automático reparta el resto.
        """
        ordered = sorted(self.items, key=lambda item: item["lote_id"] is None)
        return [
            {
                "producto_id": item["producto_id"],
                "cantidad": item["cantidad"],
                "lote_id": item["lote_id"],
                "motivo_desviacion": item.get("motivo_desviacion", ""),
                "receta": item.get("receta"),
            }
            for item in ordered
        ]
