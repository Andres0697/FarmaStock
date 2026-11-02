"""Entradas de mercadería: un documento del proveedor con varias líneas.

Al registrar una entrada se crean (o se suman a) los lotes, se deja el
movimiento de inventario y el documento, todo en UNA transacción.
"""
from datetime import date
from decimal import Decimal

from models.lotes_service import receive_lot, validate_lot_input
from models.permisos import require_role
from utils.helpers import clean_text

MAX_LARGO_FACTURA = 60
MAX_LARGO_OBSERVACIONES = 255


class EntradaModel:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def active_products(self):
        """Productos activos para elegir en las líneas de la entrada."""
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, codigo, nombre_comercial, concentracion, unidad_concentracion
                FROM productos
                WHERE estado = 'Activo'
                ORDER BY nombre_comercial
                """
            )
            return cursor.fetchall()

    def list_entries(self, provider_id=None, since=None):
        """Entradas recientes, filtrables por proveedor y por fecha de factura."""
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT e.id, e.fecha_registro, e.fecha_factura, e.numero_factura,
                       p.nombre AS proveedor, u.nombre AS usuario, e.total,
                       (SELECT COUNT(*) FROM entrada_detalle d
                         WHERE d.entrada_id = e.id) AS lineas
                FROM entradas_inventario e
                INNER JOIN proveedores p ON p.id = e.proveedor_id
                INNER JOIN usuarios u ON u.id = e.usuario_id
                WHERE (%s IS NULL OR e.proveedor_id = %s)
                  AND (%s IS NULL OR e.fecha_factura >= %s)
                ORDER BY e.id DESC
                LIMIT 200
                """,
                (provider_id, provider_id, since, since),
            )
            return cursor.fetchall()

    def get_entry(self, entry_id):
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT e.id, e.fecha_registro, e.fecha_factura, e.numero_factura,
                       e.observaciones, e.total,
                       p.nombre AS proveedor, u.nombre AS usuario
                FROM entradas_inventario e
                INNER JOIN proveedores p ON p.id = e.proveedor_id
                INNER JOIN usuarios u ON u.id = e.usuario_id
                WHERE e.id = %s
                """,
                (entry_id,),
            )
            return cursor.fetchone()

    def detail(self, entry_id):
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT d.id, pr.codigo, pr.nombre_comercial, pr.concentracion,
                       pr.unidad_concentracion, l.numero_lote, l.fecha_vencimiento,
                       d.cantidad, d.costo_unitario, d.subtotal
                FROM entrada_detalle d
                INNER JOIN productos pr ON pr.id = d.producto_id
                INNER JOIN lotes l ON l.id = d.lote_id
                WHERE d.entrada_id = %s
                ORDER BY d.id
                """,
                (entry_id,),
            )
            return cursor.fetchall()

    # ------------------------------------------------------------------
    # Registrar una entrada
    # ------------------------------------------------------------------
    def create_entry(
        self, user_id, provider_id, invoice_number, invoice_date, lines, notes=""
    ):
        """Registra el documento y recibe todas sus líneas (atómico).

        Cada línea es un diccionario con:
            producto_id, numero_lote, fecha_vencimiento (date),
            cantidad (int > 0), costo_unitario (>= 0)

        Si un lote ya existe con el mismo vencimiento, la cantidad se suma a
        ese lote. Si falla cualquier línea no se guarda nada.
        Devuelve (entrada_id, total).
        """
        invoice_number = clean_text(invoice_number)
        notes = clean_text(notes)
        self._validate_header(invoice_number, invoice_date, notes, lines)
        clean_lines = [self._clean_line(line) for line in lines]
        total = sum((l["cantidad"] * l["costo_unitario"] for l in clean_lines), Decimal("0.00"))

        with self.db.transaction() as cursor:
            require_role(cursor, user_id, "registrar entradas de mercadería")
            self._require_active_provider(cursor, provider_id)
            self._require_new_invoice(cursor, provider_id, invoice_number)

            entry_id = self._insert_entry(
                cursor, provider_id, invoice_number, invoice_date, user_id, total, notes
            )
            reference = f"Entrada #{entry_id} · Factura {invoice_number}"

            for line in clean_lines:
                lot_id = self._receive_lot(cursor, provider_id, line)
                self._insert_detail(cursor, entry_id, lot_id, line)
                self._insert_movement(cursor, user_id, lot_id, line, reference)

            return entry_id, total

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_header(invoice_number, invoice_date, notes, lines):
        if not invoice_number:
            raise ValueError("Indique el número de factura del proveedor.")
        if len(invoice_number) > MAX_LARGO_FACTURA:
            raise ValueError(f"El número de factura admite máximo {MAX_LARGO_FACTURA} caracteres.")
        if invoice_date > date.today():
            raise ValueError("La fecha de la factura no puede ser futura.")
        if len(notes) > MAX_LARGO_OBSERVACIONES:
            raise ValueError("Las observaciones son demasiado largas.")
        if not lines:
            raise ValueError("Agregue al menos un producto a la entrada.")

    @staticmethod
    def _clean_line(line):
        lot, quantity, cost = validate_lot_input(
            line.get("numero_lote"), line.get("fecha_vencimiento"),
            line.get("cantidad"), line.get("costo_unitario"),
        )
        return {
            "producto_id": line["producto_id"],
            "numero_lote": lot,
            "fecha_vencimiento": line["fecha_vencimiento"],
            "cantidad": quantity,
            "costo_unitario": cost,
        }

    @staticmethod
    def _require_active_provider(cursor, provider_id):
        cursor.execute(
            "SELECT estado FROM proveedores WHERE id = %s FOR UPDATE", (provider_id,)
        )
        provider = cursor.fetchone()
        if not provider:
            raise ValueError("El proveedor no existe.")
        if provider["estado"] != "Activo":
            raise ValueError("El proveedor está inactivo.")

    @staticmethod
    def _require_new_invoice(cursor, provider_id, invoice_number):
        cursor.execute(
            """
            SELECT id FROM entradas_inventario
            WHERE proveedor_id = %s AND numero_factura = %s
            """,
            (provider_id, invoice_number),
        )
        previous = cursor.fetchone()
        if previous:
            raise ValueError(
                f"La factura {invoice_number} de este proveedor ya fue registrada "
                f"(entrada #{previous['id']})."
            )

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    @staticmethod
    def _insert_entry(cursor, provider_id, invoice, invoice_date, user_id, total, notes):
        cursor.execute(
            """
            INSERT INTO entradas_inventario
                (proveedor_id, numero_factura, fecha_factura, usuario_id,
                 total, observaciones)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (provider_id, invoice, invoice_date, user_id, total, notes or None),
        )
        return cursor.lastrowid

    @staticmethod
    def _receive_lot(cursor, provider_id, line):
        """Crea el lote o suma al existente (lógica compartida con las compras)."""
        return receive_lot(
            cursor, line["producto_id"], line["numero_lote"], line["fecha_vencimiento"],
            line["cantidad"], line["costo_unitario"], provider_id,
        )

    @staticmethod
    def _insert_detail(cursor, entry_id, lot_id, line):
        cursor.execute(
            """
            INSERT INTO entrada_detalle
                (entrada_id, producto_id, lote_id, cantidad, costo_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                entry_id,
                line["producto_id"],
                lot_id,
                line["cantidad"],
                line["costo_unitario"],
                line["cantidad"] * line["costo_unitario"],
            ),
        )

    @staticmethod
    def _insert_movement(cursor, user_id, lot_id, line, reference):
        cursor.execute(
            """
            INSERT INTO movimientos_inventario
                (producto_id, lote_id, tipo_movimiento, cantidad,
                 motivo, referencia, usuario_id)
            VALUES (%s, %s, 'Entrada', %s, 'Entrada de mercadería', %s, %s)
            """,
            (line["producto_id"], lot_id, line["cantidad"], reference, user_id),
        )
