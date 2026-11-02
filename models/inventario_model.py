from datetime import date

from models.auditoria_model import AuditoriaModel
from utils.helpers import clean_text
from utils.permisos import require

MAX_LARGO_LOTE = 80
MIN_LARGO_MOTIVO = 5


class InventarioModel:
    """Lotes y consultas de inventario.

    Todo cambio de existencias deja su movimiento, y los cambios sensibles
    exigen permiso y quedan en la bitácora. Los ajustes de cantidad (merma,
    vencido, devolución, conteo) viven en AjusteModel: aquí no hay otra vía.
    """

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Alta de lote
    # ------------------------------------------------------------------
    def create_lot(self, data, user):
        """Registra un lote nuevo y su movimiento de entrada (atómico).

        data = (producto_id, numero_lote, fecha_fabricacion, fecha_vencimiento,
                cantidad, precio_compra, proveedor_id, fecha_recepcion, ubicacion)
        Un lote que ya existe para el producto NO se suma aquí: use la entrada de
        mercadería por factura, que deja el documento de respaldo.
        """
        require(user, "ajustar_inventario")
        (producto_id, numero_lote, fabricacion, vencimiento, cantidad,
         costo, proveedor_id, recepcion, ubicacion) = data

        numero_lote = clean_text(numero_lote)
        ubicacion = clean_text(ubicacion) or None
        today = date.today()
        if not numero_lote:
            raise ValueError("El número de lote es obligatorio.")
        if len(numero_lote) > MAX_LARGO_LOTE:
            raise ValueError(f"El número de lote admite máximo {MAX_LARGO_LOTE} caracteres.")
        if int(cantidad) <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if float(costo) < 0:
            raise ValueError("El precio de compra no puede ser negativo.")
        if vencimiento is None or vencimiento <= today:
            raise ValueError("El lote está vencido o vence hoy: no se puede recibir.")
        if fabricacion and (fabricacion > vencimiento or fabricacion > today):
            raise ValueError("La fecha de fabricación no es válida.")
        if recepcion and recepcion > today:
            raise ValueError("La fecha de recepción no puede ser futura.")

        with self.db.transaction() as cursor:
            cursor.execute("SELECT estado FROM productos WHERE id = %s FOR UPDATE", (producto_id,))
            product = cursor.fetchone()
            if not product:
                raise ValueError("Producto no encontrado.")
            if product["estado"] != "Activo":
                raise ValueError("El producto está inactivo.")

            if proveedor_id is not None:
                cursor.execute("SELECT estado FROM proveedores WHERE id = %s", (proveedor_id,))
                provider = cursor.fetchone()
                if not provider or provider["estado"] != "Activo":
                    raise ValueError("El proveedor no existe o está inactivo.")

            cursor.execute(
                "SELECT id FROM lotes WHERE producto_id = %s AND numero_lote = %s FOR UPDATE",
                (producto_id, numero_lote),
            )
            if cursor.fetchone():
                raise ValueError(
                    f"El lote {numero_lote} ya existe para este producto. Para sumar unidades "
                    "use «Entradas de mercadería» (con la factura del proveedor)."
                )

            cursor.execute(
                """
                INSERT INTO lotes (producto_id, numero_lote, fecha_fabricacion,
                    fecha_vencimiento, cantidad_inicial, cantidad_actual,
                    precio_compra, proveedor_id, fecha_recepcion, estado, ubicacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Disponible', %s)
                """,
                (producto_id, numero_lote, fabricacion, vencimiento, cantidad, cantidad,
                 costo, proveedor_id, recepcion or today, ubicacion),
            )
            lot_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO movimientos_inventario
                    (producto_id, lote_id, tipo_movimiento, cantidad, motivo, referencia, usuario_id)
                VALUES (%s, %s, 'Entrada', %s, 'Entrada de inventario', %s, %s)
                """,
                (producto_id, lot_id, cantidad, f"Lote {numero_lote}", user["id"]),
            )
            AuditoriaModel.log(cursor, user["id"], "LOTE_CREADO", "lotes", lot_id,
                               f"{numero_lote}: {cantidad} unidades, vence {vencimiento}")
            return lot_id

    # ------------------------------------------------------------------
    # Bloqueo / desbloqueo de lote (cuarentena)
    # ------------------------------------------------------------------
    def set_blocked(self, user, lot_id, blocked, motivo):
        """Inmoviliza (Cuarentena) o libera un lote. La cantidad física no cambia.

        Un lote en cuarentena no se vende ni entra en las existencias disponibles.
        """
        require(user, "ajustar_inventario")
        motivo = clean_text(motivo)
        if len(motivo) < MIN_LARGO_MOTIVO:
            raise ValueError(f"Escriba el motivo (mínimo {MIN_LARGO_MOTIVO} letras).")

        with self.db.transaction() as cursor:
            cursor.execute(
                "SELECT numero_lote, estado, cantidad_actual, fecha_vencimiento FROM lotes WHERE id = %s FOR UPDATE",
                (lot_id,),
            )
            lot = cursor.fetchone()
            if not lot:
                raise ValueError("Lote no encontrado.")

            if blocked:
                if lot["estado"] == "Cuarentena":
                    raise ValueError("El lote ya está en cuarentena.")
                if lot["estado"] == "Retirado":
                    raise ValueError("El lote está retirado.")
                new_state, action = "Cuarentena", "LOTE_BLOQUEADO"
            else:
                if lot["estado"] != "Cuarentena":
                    raise ValueError("El lote no está en cuarentena.")
                action = "LOTE_LIBERADO"
                if lot["cantidad_actual"] == 0:
                    new_state = "Agotado"
                elif lot["fecha_vencimiento"] < date.today():
                    new_state = "Vencido"
                else:
                    new_state = "Disponible"

            cursor.execute("UPDATE lotes SET estado = %s WHERE id = %s", (new_state, lot_id))
            AuditoriaModel.log(cursor, user["id"], action, "lotes", lot_id,
                               f"{lot['numero_lote']}: {lot['estado']} -> {new_state}. {motivo}")
            return new_state

    def sync_expired(self):
        with self.db.cursor() as (connection, cursor):
            cursor.execute(
                """
                UPDATE lotes
                SET estado = 'Vencido'
                WHERE cantidad_actual > 0
                AND fecha_vencimiento < CURDATE()
                AND estado IN ('Disponible', 'Agotado')
                """
            )
            connection.commit()

    def low_stock(self):
        sql = """
            SELECT
                p.codigo,
                p.nombre_comercial,
                COALESCE(
                    SUM(
                        CASE
                            WHEN l.estado = 'Disponible'
                            AND l.fecha_vencimiento >= CURDATE()
                            THEN l.cantidad_actual
                            ELSE 0
                        END
                    ),
                    0
                ) AS stock,
                p.stock_minimo
            FROM productos p
            LEFT JOIN lotes l
                ON l.producto_id = p.id
            WHERE p.estado = 'Activo'
            GROUP BY p.id
            HAVING stock <= p.stock_minimo
            ORDER BY stock, p.nombre_comercial
            LIMIT 12
        """

        with self.db.cursor() as (_, cursor):
            cursor.execute(sql)
            return cursor.fetchall()

    def expiring(self, days=90):
        """Lotes con stock que vencen dentro de `days` días (por defecto 90)."""
        sql = """
            SELECT
                p.codigo,
                p.nombre_comercial,
                l.numero_lote,
                l.fecha_vencimiento,
                l.cantidad_actual,
                DATEDIFF(
                    l.fecha_vencimiento,
                    CURDATE()
                ) AS dias
            FROM lotes l
            JOIN productos p
                ON p.id = l.producto_id
            WHERE l.cantidad_actual > 0
            AND l.fecha_vencimiento <= DATE_ADD(
                CURDATE(),
                INTERVAL %s DAY
            )
            ORDER BY l.fecha_vencimiento
            LIMIT 12
        """

        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, (int(days),))
            return cursor.fetchall()

    def movements(self, limit=100):
        """Kardex reciente con el saldo acumulado de cada lote tras el movimiento."""
        sql = """
            SELECT * FROM (
                SELECT
                    mi.id,
                    mi.fecha,
                    p.codigo,
                    p.nombre_comercial,
                    l.numero_lote,
                    mi.tipo_movimiento,
                    mi.cantidad,
                    CASE WHEN mi.lote_id IS NULL THEN NULL
                         ELSE SUM(mi.cantidad) OVER (PARTITION BY mi.lote_id ORDER BY mi.id)
                    END AS saldo_lote,
                    mi.motivo,
                    u.nombre AS usuario
                FROM movimientos_inventario mi
                JOIN productos p ON p.id = mi.producto_id
                LEFT JOIN lotes l ON l.id = mi.lote_id
                JOIN usuarios u ON u.id = mi.usuario_id
            ) kardex
            ORDER BY id DESC
            LIMIT %s
        """

        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, (limit,))
            return cursor.fetchall()
