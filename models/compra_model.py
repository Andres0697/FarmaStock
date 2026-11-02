"""Órdenes de compra, recepciones (parciales, varios lotes por línea), cuentas por pagar y reabastecimiento."""
from datetime import date, timedelta
from decimal import Decimal

from models.auditoria_model import AuditoriaModel
from models.lotes_service import money, receive_lot, validate_lot_input
from utils.helpers import clean_text
from utils.permisos import require

MIN_LARGO_MOTIVO = 5
MAX_LARGO_DOCUMENTO = 60
MAX_LARGO_OBSERVACIONES = 255
MAX_DIAS_CREDITO = 365


def plan_receipt(lines: list[dict], items: list[dict]) -> list[dict]:
    """Valida una recepción contra las líneas de la orden (función pura, sin base de datos).

    lines: [{id, producto_id, cantidad, recibido, costo_unitario, nombre_comercial?}]
    items: [{detalle_id, numero_lote, fecha_vencimiento, cantidad}]
    Devuelve los ítems normalizados con producto_id y costo_unitario de la orden.
    Reglas: al menos un ítem; cada ítem pertenece a la orden; cantidad > 0; la suma por
    línea no supera lo pendiente; no se repite el mismo lote dentro de una línea.
    """
    if not items:
        raise ValueError("Indique al menos una cantidad a recibir.")
    by_id = {int(l["id"]): l for l in lines}
    received_now: dict[int, int] = {}
    seen: set[tuple[int, str]] = set()
    plan = []
    for item in items:
        detail_id = int(item["detalle_id"])
        line = by_id.get(detail_id)
        if line is None:
            raise ValueError("Una de las líneas no pertenece a esta orden.")
        lot, quantity, cost = validate_lot_input(
            item.get("numero_lote"), item.get("fecha_vencimiento"), item.get("cantidad"), line["costo_unitario"]
        )
        key = (detail_id, lot.upper())
        if key in seen:
            raise ValueError(f"El lote {lot} está repetido en la misma línea; sume las cantidades en una sola fila.")
        seen.add(key)
        received_now[detail_id] = received_now.get(detail_id, 0) + quantity
        plan.append({
            "detalle_id": detail_id,
            "producto_id": line["producto_id"],
            "numero_lote": lot,
            "fecha_vencimiento": item["fecha_vencimiento"],
            "cantidad": quantity,
            "costo_unitario": cost,
        })
    for detail_id, quantity in received_now.items():
        line = by_id[detail_id]
        pending = int(line["cantidad"]) - int(line.get("recibido") or 0)
        if quantity > pending:
            name = line.get("nombre_comercial") or f"línea {detail_id}"
            raise ValueError(f"{name}: se intenta recibir {quantity} u. pero solo faltan {pending}.")
    return plan


def clean_order_lines(lines: list[dict]) -> list[dict]:
    """Normaliza las líneas de una nueva orden (cantidad > 0, costo >= 0, Decimal)."""
    if not lines:
        raise ValueError("La orden no tiene productos.")
    clean = []
    for line in lines:
        try:
            quantity = int(line["cantidad"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("Cantidad inválida en una línea de la orden.") from exc
        cost = money(line["costo_unitario"])
        if quantity <= 0:
            raise ValueError("Las cantidades de la orden deben ser mayores que cero.")
        if cost < 0:
            raise ValueError("Los costos de la orden no pueden ser negativos.")
        clean.append({"producto_id": line["producto_id"], "cantidad": quantity, "costo_unitario": cost})
    return clean


class CompraModel:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Órdenes
    # ------------------------------------------------------------------
    def create_order(self, user: dict, proveedor_id: int, lines: list[dict], dias_credito: int = 0) -> int:
        """lines: [{producto_id, cantidad, costo_unitario}]"""
        require(user, "compras")
        clean = clean_order_lines(lines)
        dias_credito = int(dias_credito)
        if not 0 <= dias_credito <= MAX_DIAS_CREDITO:
            raise ValueError(f"Los días de crédito deben estar entre 0 y {MAX_DIAS_CREDITO}.")
        total = sum((l["cantidad"] * l["costo_unitario"] for l in clean), Decimal("0.00"))
        with self.db.transaction() as c:
            c.execute("SELECT estado FROM proveedores WHERE id=%s FOR UPDATE", (proveedor_id,))
            provider = c.fetchone()
            if not provider or provider["estado"] != "Activo":
                raise ValueError("El proveedor no existe o está inactivo.")
            for line in clean:
                c.execute("SELECT estado FROM productos WHERE id=%s", (line["producto_id"],))
                product = c.fetchone()
                if not product or product["estado"] != "Activo":
                    raise ValueError("Uno de los productos no existe o está inactivo.")
            c.execute(
                "INSERT INTO ordenes_compra(proveedor_id,total,dias_credito,usuario_id) VALUES(%s,%s,%s,%s)",
                (proveedor_id, total, dias_credito, user["id"]),
            )
            order_id = c.lastrowid
            for line in clean:
                c.execute(
                    "INSERT INTO detalle_orden_compra(orden_id,producto_id,cantidad,costo_unitario) VALUES(%s,%s,%s,%s)",
                    (order_id, line["producto_id"], line["cantidad"], line["costo_unitario"]),
                )
            AuditoriaModel.log(c, user["id"], "ORDEN_COMPRA", "ordenes_compra", order_id, f"Total C$ {total:.2f}")
            return order_id

    def order_lines(self, order_id: int) -> list[dict]:
        """Líneas con lo ya recibido (`recibido`) y lo que falta (`pendiente`)."""
        sql = """SELECT d.id, d.producto_id, p.nombre_comercial, d.cantidad, d.costo_unitario,
                        COALESCE((SELECT SUM(r.cantidad) FROM recepcion_detalle r WHERE r.detalle_orden_id = d.id), 0) AS recibido
                 FROM detalle_orden_compra d JOIN productos p ON p.id = d.producto_id
                 WHERE d.orden_id = %s ORDER BY d.id"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (order_id,))
            rows = c.fetchall()
        for row in rows:
            row["recibido"] = int(row["recibido"])
            row["pendiente"] = int(row["cantidad"]) - row["recibido"]
        return rows

    def orders(self) -> list[dict]:
        sql = """SELECT o.id, o.fecha, pr.nombre proveedor, o.total, o.estado,
                        (SELECT COALESCE(SUM(d.cantidad),0) FROM detalle_orden_compra d WHERE d.orden_id = o.id) AS pedido,
                        (SELECT COALESCE(SUM(r.cantidad),0) FROM recepcion_detalle r
                           JOIN recepciones_compra rc ON rc.id = r.recepcion_id WHERE rc.orden_id = o.id) AS recibido
                 FROM ordenes_compra o JOIN proveedores pr ON pr.id = o.proveedor_id
                 ORDER BY o.id DESC LIMIT 200"""
        with self.db.cursor() as (_, c):
            c.execute(sql)
            return c.fetchall()

    def receptions(self, order_id: int | None = None) -> list[dict]:
        """Historial de recepciones (una fila por lote recibido)."""
        sql = """SELECT rc.id AS recepcion_id, rc.orden_id, rc.fecha, u.nombre AS usuario, rc.numero_documento,
                        p.nombre_comercial, l.numero_lote, l.fecha_vencimiento, r.cantidad, r.costo_unitario
                 FROM recepciones_compra rc
                 JOIN recepcion_detalle r ON r.recepcion_id = rc.id
                 JOIN productos p ON p.id = r.producto_id
                 JOIN lotes l ON l.id = r.lote_id
                 JOIN usuarios u ON u.id = rc.usuario_id
                 WHERE (%s IS NULL OR rc.orden_id = %s)
                 ORDER BY rc.id DESC, r.id LIMIT 500"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (order_id, order_id))
            return c.fetchall()

    def receive(self, user: dict, order_id: int, items: list[dict], numero_documento: str | None = None,
                observaciones: str | None = None) -> int:
        """Registra una recepción (total o parcial). Devuelve el id de la recepción.

        items: [{detalle_id, numero_lote, fecha_vencimiento, cantidad}]; una línea puede
        recibirse en varios lotes. Todo o nada. Genera una cuenta por pagar por la recepción.
        """
        require(user, "compras")
        document = clean_text(numero_documento)
        notes = clean_text(observaciones)
        if len(document) > MAX_LARGO_DOCUMENTO:
            raise ValueError(f"El número de documento admite máximo {MAX_LARGO_DOCUMENTO} caracteres.")
        if len(notes) > MAX_LARGO_OBSERVACIONES:
            raise ValueError("Las observaciones son demasiado largas.")

        with self.db.transaction() as c:
            c.execute(
                "SELECT id, proveedor_id, dias_credito, estado FROM ordenes_compra WHERE id=%s FOR UPDATE", (order_id,)
            )
            order = c.fetchone()
            if not order:
                raise ValueError("La orden no existe.")
            if order["estado"] not in ("Pendiente", "Parcial"):
                raise ValueError(f"La orden está {order['estado'].lower()}; ya no admite recepciones.")
            c.execute("SELECT estado FROM proveedores WHERE id=%s", (order["proveedor_id"],))
            provider = c.fetchone()
            if not provider or provider["estado"] != "Activo":
                raise ValueError("El proveedor de la orden está inactivo.")
            if document:
                c.execute(
                    "SELECT id FROM recepciones_compra WHERE orden_id=%s AND numero_documento=%s", (order_id, document)
                )
                if c.fetchone():
                    raise ValueError(f"El documento {document} ya fue registrado en esta orden.")

            c.execute(
                """SELECT d.id, d.producto_id, d.cantidad, d.costo_unitario,
                          COALESCE((SELECT SUM(r.cantidad) FROM recepcion_detalle r WHERE r.detalle_orden_id = d.id), 0) AS recibido
                   FROM detalle_orden_compra d WHERE d.orden_id=%s""",
                (order_id,),
            )
            lines = c.fetchall()
            plan = plan_receipt(lines, items)

            c.execute(
                "INSERT INTO recepciones_compra(orden_id, usuario_id, numero_documento, observaciones) VALUES(%s,%s,%s,%s)",
                (order_id, user["id"], document or None, notes or None),
            )
            reception_id = c.lastrowid
            reference = f"OC #{order_id} · Recepción #{reception_id}"
            amount = Decimal("0.00")
            for item in plan:
                lot_id = receive_lot(
                    c, item["producto_id"], item["numero_lote"], item["fecha_vencimiento"],
                    item["cantidad"], item["costo_unitario"], order["proveedor_id"],
                )
                c.execute(
                    """INSERT INTO recepcion_detalle(recepcion_id,detalle_orden_id,producto_id,lote_id,cantidad,costo_unitario)
                       VALUES(%s,%s,%s,%s,%s,%s)""",
                    (reception_id, item["detalle_id"], item["producto_id"], lot_id, item["cantidad"], item["costo_unitario"]),
                )
                c.execute(
                    """INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id)
                       VALUES(%s,%s,'Entrada',%s,'Recepción de orden de compra',%s,%s)""",
                    (item["producto_id"], lot_id, item["cantidad"], reference, user["id"]),
                )
                amount += item["cantidad"] * item["costo_unitario"]

            complete = all(
                int(l["recibido"]) + sum(i["cantidad"] for i in plan if i["detalle_id"] == l["id"]) >= int(l["cantidad"])
                for l in lines
            )
            c.execute("UPDATE ordenes_compra SET estado=%s WHERE id=%s", ("Recibida" if complete else "Parcial", order_id))

            if amount > 0:
                due = date.today() + timedelta(days=int(order["dias_credito"]))
                c.execute(
                    """INSERT INTO cuentas_por_pagar(orden_id,recepcion_id,proveedor_id,monto,saldo,fecha_emision,fecha_vencimiento)
                       VALUES(%s,%s,%s,%s,%s,CURDATE(),%s)""",
                    (order_id, reception_id, order["proveedor_id"], amount, amount, due),
                )
            AuditoriaModel.log(
                c, user["id"], "RECEPCION_COMPRA", "ordenes_compra", order_id,
                f"Recepción #{reception_id}: {len(plan)} lote(s), C$ {amount:.2f}, orden {'completa' if complete else 'parcial'}",
            )
            return reception_id

    def cancel_order(self, user: dict, order_id: int, motivo: str) -> None:
        """Anula una orden que no ha recibido nada."""
        require(user, "compras")
        reason = clean_text(motivo)
        if len(reason) < MIN_LARGO_MOTIVO:
            raise ValueError(f"Indique el motivo de la anulación (mínimo {MIN_LARGO_MOTIVO} caracteres).")
        with self.db.transaction() as c:
            c.execute("SELECT estado FROM ordenes_compra WHERE id=%s FOR UPDATE", (order_id,))
            order = c.fetchone()
            if not order:
                raise ValueError("La orden no existe.")
            if order["estado"] != "Pendiente":
                raise ValueError("Solo se puede anular una orden pendiente sin recepciones. Si ya recibió parte, ciérrela con faltante.")
            c.execute("SELECT COUNT(*) AS n FROM recepciones_compra WHERE orden_id=%s", (order_id,))
            if c.fetchone()["n"]:
                raise ValueError("La orden ya tiene recepciones; no se puede anular.")
            c.execute("UPDATE ordenes_compra SET estado='Anulada' WHERE id=%s", (order_id,))
            AuditoriaModel.log(c, user["id"], "ORDEN_COMPRA_ANULADA", "ordenes_compra", order_id, reason)

    def close_order(self, user: dict, order_id: int, motivo: str) -> None:
        """Cierra una orden parcialmente recibida aceptando el faltante."""
        require(user, "compras")
        reason = clean_text(motivo)
        if len(reason) < MIN_LARGO_MOTIVO:
            raise ValueError(f"Indique el motivo del faltante (mínimo {MIN_LARGO_MOTIVO} caracteres).")
        with self.db.transaction() as c:
            c.execute("SELECT estado FROM ordenes_compra WHERE id=%s FOR UPDATE", (order_id,))
            order = c.fetchone()
            if not order:
                raise ValueError("La orden no existe.")
            if order["estado"] != "Parcial":
                raise ValueError("Solo se puede cerrar con faltante una orden parcialmente recibida.")
            c.execute("UPDATE ordenes_compra SET estado='Recibida' WHERE id=%s", (order_id,))
            AuditoriaModel.log(c, user["id"], "ORDEN_COMPRA_CERRADA", "ordenes_compra", order_id, f"Cerrada con faltante: {reason}")

    # ------------------------------------------------------------------
    # Cuentas por pagar
    # ------------------------------------------------------------------
    def payables(self) -> list[dict]:
        sql = """SELECT x.id,x.orden_id,x.recepcion_id,pr.nombre proveedor,x.monto,x.saldo,x.fecha_emision,x.fecha_vencimiento,x.estado,
                        DATEDIFF(x.fecha_vencimiento,CURDATE()) dias
                 FROM cuentas_por_pagar x JOIN proveedores pr ON pr.id=x.proveedor_id ORDER BY x.estado,x.fecha_vencimiento"""
        with self.db.cursor() as (_, c):
            c.execute(sql)
            return c.fetchall()

    def pay(self, user: dict, cuenta_id: int, monto) -> None:
        require(user, "compras")
        amount = money(monto)
        with self.db.transaction() as c:
            c.execute("SELECT saldo FROM cuentas_por_pagar WHERE id=%s FOR UPDATE", (cuenta_id,))
            row = c.fetchone()
            if not row:
                raise ValueError("La cuenta por pagar no existe.")
            balance = Decimal(str(row["saldo"]))
            if amount <= 0 or amount > balance:
                raise ValueError("El monto debe ser mayor que cero y no superar el saldo.")
            new_balance = balance - amount
            c.execute(
                "UPDATE cuentas_por_pagar SET saldo=%s, estado=%s WHERE id=%s",
                (new_balance, "Pagada" if new_balance <= 0 else "Pendiente", cuenta_id),
            )
            c.execute("INSERT INTO pagos_proveedor(cuenta_id,monto,usuario_id) VALUES(%s,%s,%s)", (cuenta_id, amount, user["id"]))
            AuditoriaModel.log(c, user["id"], "PAGO_PROVEEDOR", "cuentas_por_pagar", cuenta_id, f"C$ {amount:.2f}")

    def restock_suggestions(self, days: int = 30, cover_days: int = 30) -> list[dict]:
        """Sugiere cantidad a pedir para cubrir 'cover_days' según la rotación de los últimos 'days' días."""
        sql = """SELECT p.codigo,p.nombre_comercial,p.stock_minimo,
                   COALESCE((SELECT SUM(l.cantidad_actual) FROM lotes l WHERE l.producto_id=p.id AND l.estado='Disponible' AND l.fecha_vencimiento>=CURDATE()),0) stock,
                   COALESCE((SELECT SUM(dv.cantidad) FROM detalle_venta dv JOIN ventas v ON v.id=dv.venta_id
                             WHERE dv.producto_id=p.id AND v.estado='Completada' AND v.fecha>=DATE_SUB(NOW(),INTERVAL %s DAY)),0) vendido
                 FROM productos p WHERE p.estado='Activo'"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (days,))
            rows = c.fetchall()
        out = []
        for r in rows:
            daily = float(r["vendido"]) / days
            target = max(int(round(daily * cover_days)), int(r["stock_minimo"]))
            need = target - int(r["stock"])
            if need > 0:
                out.append({**r, "rotacion_diaria": round(daily, 2), "sugerido": need})
        return sorted(out, key=lambda x: x["sugerido"], reverse=True)
