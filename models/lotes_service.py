"""Ingreso de mercadería a lotes: lógica única para entradas y recepciones de compra.

Se ejecuta SIEMPRE dentro de una transacción abierta por quien la llama (recibe el cursor).
No escribe el movimiento de inventario: lo registra el llamador con su propia referencia.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from utils.helpers import clean_text

MAX_LARGO_LOTE = 80
ESTADOS_QUE_NO_REINGRESAN = ("Vencido", "Retirado", "Cuarentena")
_CENTAVO = Decimal("0.01")


def money(value) -> Decimal:
    """Convierte a Decimal con 2 decimales (evita errores de float)."""
    try:
        return Decimal(str(value)).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    except Exception as exc:  # decimal.InvalidOperation y similares
        raise ValueError(f"Monto inválido: {value!r}") from exc


def weighted_cost(old_qty: int, old_cost, new_qty: int, new_cost) -> Decimal:
    """Costo promedio ponderado entre lo ya recibido y lo nuevo."""
    old_qty, new_qty = int(old_qty), int(new_qty)
    total_qty = old_qty + new_qty
    if total_qty <= 0:
        return money(new_cost)
    total = Decimal(str(old_cost)) * old_qty + Decimal(str(new_cost)) * new_qty
    return (total / total_qty).quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def validate_lot_input(numero_lote, vencimiento, cantidad, costo) -> tuple[str, int, Decimal]:
    """Valida y normaliza los datos de un lote. Devuelve (lote, cantidad, costo)."""
    lot = clean_text(numero_lote)
    if not lot:
        raise ValueError("Cada línea necesita número de lote.")
    if len(lot) > MAX_LARGO_LOTE:
        raise ValueError(f"El lote '{lot[:20]}…' es demasiado largo (máximo {MAX_LARGO_LOTE}).")
    try:
        quantity = int(cantidad)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"La cantidad del lote {lot} no es válida.") from exc
    if quantity <= 0:
        raise ValueError(f"La cantidad del lote {lot} debe ser mayor que cero.")
    cost = money(costo)
    if cost < 0:
        raise ValueError(f"El costo del lote {lot} no puede ser negativo.")
    if not isinstance(vencimiento, date) or vencimiento <= date.today():
        raise ValueError(f"El lote {lot} está vencido o vence hoy: no se puede recibir.")
    return lot, quantity, cost


def receive_lot(cursor, producto_id, numero_lote, vencimiento, cantidad, costo,
                proveedor_id=None, fabricacion=None) -> int:
    """Crea el lote o suma al existente (mismo número y vencimiento). Devuelve lote_id.

    * Producto debe existir y estar activo (se bloquea la fila).
    * Lote existente: mismo vencimiento y estado que admita ingresos; un lote
      Agotado vuelve a Disponible.
    * El costo del lote existente pasa a promedio ponderado; el proveedor original
      se conserva si ya tenía uno.
    """
    lot, quantity, cost = validate_lot_input(numero_lote, vencimiento, cantidad, costo)

    cursor.execute("SELECT estado FROM productos WHERE id = %s FOR UPDATE", (producto_id,))
    product = cursor.fetchone()
    if not product or product["estado"] != "Activo":
        raise ValueError("Uno de los productos no existe o está inactivo.")

    cursor.execute(
        """
        SELECT id, fecha_vencimiento, estado, cantidad_inicial, precio_compra, proveedor_id
        FROM lotes WHERE producto_id = %s AND numero_lote = %s FOR UPDATE
        """,
        (producto_id, lot),
    )
    existing = cursor.fetchone()

    if existing is None:
        cursor.execute(
            """
            INSERT INTO lotes
                (producto_id, numero_lote, fecha_fabricacion, fecha_vencimiento,
                 cantidad_inicial, cantidad_actual, precio_compra, proveedor_id,
                 fecha_recepcion, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), 'Disponible')
            """,
            (producto_id, lot, fabricacion, vencimiento, quantity, quantity, cost, proveedor_id),
        )
        return cursor.lastrowid

    if existing["fecha_vencimiento"] != vencimiento:
        raise ValueError(
            f"El lote {lot} ya existe con otro vencimiento ({existing['fecha_vencimiento']}). "
            "Revise el número de lote."
        )
    if existing["estado"] in ESTADOS_QUE_NO_REINGRESAN:
        raise ValueError(
            f"El lote {lot} está en estado {existing['estado']}: no se puede reingresar mercadería a él."
        )

    new_cost = weighted_cost(existing["cantidad_inicial"], existing["precio_compra"], quantity, cost)
    cursor.execute(
        """
        UPDATE lotes
        SET cantidad_actual = cantidad_actual + %s,
            cantidad_inicial = cantidad_inicial + %s,
            precio_compra = %s,
            proveedor_id = COALESCE(proveedor_id, %s),
            estado = 'Disponible'
        WHERE id = %s
        """,
        (quantity, quantity, new_cost, proveedor_id, existing["id"]),
    )
    return existing["id"]
