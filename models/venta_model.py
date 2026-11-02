from database.queries import (
    SALE_DETAIL,
    SALE_HEADER,
    SALE_HISTORY,
    SALE_LIST,
    SALE_PRODUCT_EXACT,
    SALE_PRODUCT_SEARCH_TEMPLATE,
    SALE_SEARCH_TOKEN,
    SALE_SEARCH_TOKEN_PARAMS,
    SALE_VALID_LOTS,
)
from models.permisos import require_role

METODOS_PAGO = ("Efectivo", "Tarjeta", "Transferencia")
MIN_LARGO_MOTIVO = 5


class VentaModel:
    """Ventas con FEFO, lote real elegido por el vendedor, pago y anulación."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def list_all(self):
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_LIST)
            return cursor.fetchall()

    def detail(self, sale_id):
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_DETAIL, (sale_id,))
            return cursor.fetchall()

    def search_products(self, text="", limit=200):
        """Productos activos para vender.

        Cada palabra escrita debe coincidir con el código, código de barras,
        nombre, concentración, principio activo, marca o nombre alternativo.
        Así "ibuprofeno 400" encuentra Ibuprofeno de 400 mg.
        """
        tokens = text.split()
        where = "".join(f"AND {SALE_SEARCH_TOKEN}\n  " for _ in tokens)
        params = []
        for token in tokens:
            params.extend([f"%{token}%"] * SALE_SEARCH_TOKEN_PARAMS)
        params.append(limit)

        sql = SALE_PRODUCT_SEARCH_TEMPLATE.format(where=where)
        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, params)
            return cursor.fetchall()

    def find_exact_product(self, code):
        """Id del producto cuyo código interno o de barras es exactamente
        `code` (lo que envía un lector de código de barras)."""
        code = code.strip()
        if not code:
            return None
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_PRODUCT_EXACT, (code, code))
            row = cursor.fetchone()
            return row["id"] if row else None

    def valid_lots(self, product_id):
        """Lotes vendibles del producto; el primero es el sugerido (FEFO)."""
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_VALID_LOTS, (product_id,))
            return cursor.fetchall()

    def get_sale(self, sale_id):
        """Encabezado de una venta con pago y datos de anulación."""
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_HEADER, (sale_id,))
            return cursor.fetchone()

    def list_history(self, only_today=True, limit=100):
        """Ventas recientes (completadas y anuladas) para el panel de historial."""
        with self.db.cursor() as (_, cursor):
            cursor.execute(SALE_HISTORY, (1 if only_today else 0, limit))
            return cursor.fetchall()

    @staticmethod
    def calculate_change(total, received):
        """Cambio a devolver; nunca negativo."""
        return max(0.0, round(float(received) - float(total), 2))

    # ------------------------------------------------------------------
    # Crear venta
    # ------------------------------------------------------------------
    def create_sale(
        self,
        user_id,
        items,
        descuento=0,
        metodo_pago="Efectivo",
        monto_recibido=None,
        exigir_receta=False,
    ):
        """Registra una venta completa (atómico: todo se guarda o nada).

        Cada elemento de `items` es un diccionario con:
            producto_id, cantidad
            lote_id            (opcional) lote real que tomó el vendedor.
                               Si falta, se aplica FEFO automático.
            motivo_desviacion  (opcional) por qué eligió otro lote.
            receta             (opcional) {paciente, medico, numero_receta}

        Devuelve (venta_id, subtotal, descuento, total).
        """
        if not items:
            raise ValueError("La venta está vacía.")

        with self.db.transaction() as cursor:
            lines, subtotal = self._prepare_lines(cursor, items, exigir_receta)

            descuento = max(0, float(descuento))
            if descuento > subtotal:
                raise ValueError("El descuento no puede superar el subtotal.")
            total = round(subtotal - descuento, 2)

            received = self._validate_payment(metodo_pago, monto_recibido, total)

            sale_id = self._insert_sale(
                cursor, user_id, subtotal, descuento, total, metodo_pago, received
            )

            for line in lines:
                self._save_line(cursor, sale_id, user_id, line)

            return sale_id, subtotal, descuento, total

    def _prepare_lines(self, cursor, items, exigir_receta):
        """Valida cada producto y decide de qué lote(s) sale la cantidad."""
        lines = []
        subtotal = 0
        reserved = {}  # lote_id -> unidades ya tomadas en ESTA venta

        for item in items:
            product = self._get_sellable_product(cursor, item["producto_id"])

            quantity = int(item["cantidad"])
            if quantity <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")

            receta = self._validate_prescription(product, item, exigir_receta)

            allocations, deviation = self._allocate(
                cursor, product, quantity, item.get("lote_id"), reserved
            )

            price = float(product["precio_venta"])
            subtotal += price * quantity
            lines.append(
                {
                    "producto_id": product["id"],
                    "precio": price,
                    "allocations": allocations,
                    "deviation": deviation,
                    "motivo_desviacion": (item.get("motivo_desviacion") or "").strip(),
                    "receta": receta,
                }
            )

        return lines, subtotal

    @staticmethod
    def _get_sellable_product(cursor, product_id):
        cursor.execute(
            """
            SELECT id, nombre_comercial, precio_venta, estado,
                   requiere_receta, control_especial
            FROM productos WHERE id = %s FOR UPDATE
            """,
            (product_id,),
        )
        product = cursor.fetchone()
        if not product or product["estado"] != "Activo":
            raise ValueError("El producto no está disponible para venta.")
        return product

    @staticmethod
    def _validate_prescription(product, item, exigir_receta):
        """Receta obligatoria para productos con receta o control especial."""
        needs_prescription = product["requiere_receta"] or product["control_especial"]
        if not (exigir_receta and needs_prescription):
            return None

        data = item.get("receta") or {}
        clean = {
            key: " ".join(str(data.get(key) or "").split())
            for key in ("paciente", "medico", "numero_receta")
        }
        if not all(clean.values()):
            raise ValueError(
                f"'{product['nombre_comercial']}' requiere receta: "
                "indique paciente, médico y número de receta."
            )
        return clean

    # ------------------------------------------------------------------
    # Asignación de lotes (FEFO o lote elegido)
    # ------------------------------------------------------------------
    def _allocate(self, cursor, product, quantity, chosen_lot_id, reserved):
        """Devuelve ([(lote, cantidad)], desviación | None)."""
        lots = self._valid_lots_fefo(cursor, product["id"], reserved)
        suggested = lots[0] if lots else None

        if chosen_lot_id is None:
            return self._allocate_fefo(product, quantity, lots, reserved), None

        chosen = next((lot for lot in lots if lot["id"] == chosen_lot_id), None)
        if chosen is None:
            raise ValueError(
                self._explain_unavailable_lot(cursor, product, chosen_lot_id)
            )

        if chosen["disponible"] < quantity:
            raise ValueError(
                f"El lote {chosen['numero_lote']} de '{product['nombre_comercial']}' "
                f"solo tiene {chosen['disponible']} unidad(es) disponibles."
            )

        reserved[chosen["id"]] = reserved.get(chosen["id"], 0) + quantity

        deviation = None
        if suggested and suggested["id"] != chosen["id"]:
            deviation = {
                "lote_sugerido_id": suggested["id"],
                "lote_vendido_id": chosen["id"],
            }
        return [(chosen, quantity)], deviation

    @staticmethod
    def _valid_lots_fefo(cursor, product_id, reserved):
        """Lotes vendibles, el que vence primero va primero."""
        cursor.execute(
            """
            SELECT id, numero_lote, cantidad_actual, fecha_vencimiento, estado
            FROM lotes
            WHERE producto_id = %s
              AND estado = 'Disponible'
              AND cantidad_actual > 0
              AND fecha_vencimiento >= CURDATE()
            ORDER BY fecha_vencimiento ASC, id ASC
            FOR UPDATE
            """,
            (product_id,),
        )
        lots = []
        for lot in cursor.fetchall():
            lot["disponible"] = lot["cantidad_actual"] - reserved.get(lot["id"], 0)
            if lot["disponible"] > 0:
                lots.append(lot)
        return lots

    @staticmethod
    def _allocate_fefo(product, quantity, lots, reserved):
        allocations = []
        remaining = quantity

        for lot in lots:
            if remaining <= 0:
                break
            taken = min(remaining, lot["disponible"])
            allocations.append((lot, taken))
            reserved[lot["id"]] = reserved.get(lot["id"], 0) + taken
            remaining -= taken

        if remaining > 0:
            raise ValueError(
                "No hay existencias válidas suficientes para "
                f"'{product['nombre_comercial']}'."
            )
        return allocations

    @staticmethod
    def _explain_unavailable_lot(cursor, product, lot_id):
        """Mensaje claro de por qué el lote elegido no se puede vender."""
        cursor.execute(
            """
            SELECT numero_lote, estado, cantidad_actual,
                   fecha_vencimiento < CURDATE() AS vencido
            FROM lotes WHERE id = %s AND producto_id = %s
            """,
            (lot_id, product["id"]),
        )
        lot = cursor.fetchone()
        name = product["nombre_comercial"]

        if not lot:
            return f"El lote indicado no existe para '{name}'."
        if lot["vencido"]:
            return f"El lote {lot['numero_lote']} está VENCIDO y no se puede vender."
        if lot["estado"] != "Disponible":
            return (
                f"El lote {lot['numero_lote']} no está disponible "
                f"(estado: {lot['estado']})."
            )
        return f"El lote {lot['numero_lote']} no tiene unidades disponibles."

    # ------------------------------------------------------------------
    # Pago
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_payment(metodo_pago, monto_recibido, total):
        if metodo_pago not in METODOS_PAGO:
            raise ValueError("Método de pago no válido.")

        if metodo_pago != "Efectivo":
            return total  # tarjeta o transferencia: se cobra el total exacto

        if monto_recibido is None:
            return None
        if float(monto_recibido) < total:
            raise ValueError("El monto recibido es menor que el total a pagar.")
        return round(float(monto_recibido), 2)

    # ------------------------------------------------------------------
    # Escritura de la venta
    # ------------------------------------------------------------------
    @staticmethod
    def _insert_sale(cursor, user_id, subtotal, descuento, total, metodo, received):
        cursor.execute(
            """
            INSERT INTO ventas
                (usuario_id, subtotal, descuento, total, estado,
                 metodo_pago, monto_recibido)
            VALUES (%s, %s, %s, %s, 'Completada', %s, %s)
            """,
            (user_id, subtotal, descuento, total, metodo, received),
        )
        return cursor.lastrowid

    def _save_line(self, cursor, sale_id, user_id, line):
        for lot, taken in line["allocations"]:
            self._register_lot_sale(cursor, sale_id, user_id, line, lot, taken)

        if line["deviation"]:
            self._register_deviation(cursor, sale_id, user_id, line)

        if line["receta"]:
            cursor.execute(
                """
                INSERT INTO recetas_venta
                    (venta_id, producto_id, paciente, medico, numero_receta)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    line["producto_id"],
                    line["receta"]["paciente"],
                    line["receta"]["medico"],
                    line["receta"]["numero_receta"],
                ),
            )

    @staticmethod
    def _register_lot_sale(cursor, sale_id, user_id, line, lot, taken):
        """Guarda el detalle, descuenta el lote y deja el movimiento."""
        cursor.execute(
            """
            INSERT INTO detalle_venta
                (venta_id, producto_id, lote_id, cantidad, precio_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                sale_id,
                line["producto_id"],
                lot["id"],
                taken,
                line["precio"],
                line["precio"] * taken,
            ),
        )
        cursor.execute(
            """
            UPDATE lotes
            SET cantidad_actual = cantidad_actual - %s,
                estado = IF(cantidad_actual = 0, 'Agotado', 'Disponible')
            WHERE id = %s
            """,
            (taken, lot["id"]),
        )
        cursor.execute(
            """
            INSERT INTO movimientos_inventario
                (producto_id, lote_id, tipo_movimiento, cantidad,
                 motivo, referencia, usuario_id)
            VALUES (%s, %s, 'Venta', %s, 'Salida por venta', %s, %s)
            """,
            (line["producto_id"], lot["id"], -taken, f"Venta #{sale_id}", user_id),
        )

    @staticmethod
    def _register_deviation(cursor, sale_id, user_id, line):
        """Deja constancia de que se vendió un lote distinto al sugerido."""
        cursor.execute(
            """
            INSERT INTO desviaciones_fefo
                (venta_id, usuario_id, producto_id,
                 lote_sugerido_id, lote_vendido_id, motivo)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                sale_id,
                user_id,
                line["producto_id"],
                line["deviation"]["lote_sugerido_id"],
                line["deviation"]["lote_vendido_id"],
                line["motivo_desviacion"] or None,
            ),
        )

    # ------------------------------------------------------------------
    # Anular venta
    # ------------------------------------------------------------------
    def cancel_sale(self, sale_id, admin_id, motivo):
        """Anula una venta y devuelve el stock a los lotes originales.

        Solo un administrador activo puede anular y el motivo es obligatorio.
        La venta nunca se borra: queda con estado 'Anulada' y quién la anuló.
        """
        motivo = " ".join((motivo or "").split())
        if len(motivo) < MIN_LARGO_MOTIVO:
            raise ValueError(
                f"Escriba el motivo de la anulación (mínimo {MIN_LARGO_MOTIVO} letras)."
            )

        with self.db.transaction() as cursor:
            require_role(cursor, admin_id, "anular ventas")
            self._lock_completed_sale(cursor, sale_id)

            cursor.execute(
                "SELECT producto_id, lote_id, cantidad FROM detalle_venta WHERE venta_id = %s",
                (sale_id,),
            )
            for row in cursor.fetchall():
                self._return_to_lot(cursor, sale_id, admin_id, row)

            cursor.execute(
                """
                UPDATE ventas
                SET estado = 'Anulada', anulada_por = %s,
                    fecha_anulacion = NOW(), motivo_anulacion = %s
                WHERE id = %s
                """,
                (admin_id, motivo, sale_id),
            )

    @staticmethod
    def _lock_completed_sale(cursor, sale_id):
        cursor.execute(
            "SELECT estado FROM ventas WHERE id = %s FOR UPDATE", (sale_id,)
        )
        sale = cursor.fetchone()
        if not sale:
            raise ValueError("La venta no existe.")
        if sale["estado"] == "Anulada":
            raise ValueError("Esta venta ya fue anulada.")

    @staticmethod
    def _return_to_lot(cursor, sale_id, admin_id, row):
        """Suma la cantidad al lote original y registra la devolución."""
        cursor.execute(
            """
            UPDATE lotes
            SET cantidad_actual = cantidad_actual + %s,
                estado = CASE
                    WHEN estado = 'Agotado' AND fecha_vencimiento < CURDATE() THEN 'Vencido'
                    WHEN estado = 'Agotado' THEN 'Disponible'
                    ELSE estado
                END
            WHERE id = %s
            """,
            (row["cantidad"], row["lote_id"]),
        )
        cursor.execute(
            """
            INSERT INTO movimientos_inventario
                (producto_id, lote_id, tipo_movimiento, cantidad,
                 motivo, referencia, usuario_id)
            VALUES (%s, %s, 'Devolución', %s, 'Anulación de venta', %s, %s)
            """,
            (
                row["producto_id"],
                row["lote_id"],
                row["cantidad"],
                f"Anulación venta #{sale_id}",
                admin_id,
            ),
        )
