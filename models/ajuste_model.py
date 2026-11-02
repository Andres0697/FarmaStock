from datetime import date
from models.auditoria_model import AuditoriaModel
from utils.permisos import require

MIN_LARGO_MOTIVO = 5
TIPOS = ("Merma", "Vencido", "Devolución a proveedor", "Conteo físico")
_MOVIMIENTO = {"Merma": "Merma", "Vencido": "Vencimiento", "Devolución a proveedor": "Retiro", "Conteo físico": "Ajuste"}


class AjusteModel:
    """Ajustes de inventario por lote, siempre con tipo, motivo y usuario."""

    def __init__(self, db):
        self.db = db

    def lots(self) -> list[dict]:
        sql = """SELECT l.id, CONCAT(p.nombre_comercial,' · lote ',l.numero_lote,' · stock ',l.cantidad_actual) etiqueta, l.cantidad_actual
                 FROM lotes l JOIN productos p ON p.id=l.producto_id WHERE l.estado<>'Retirado' ORDER BY p.nombre_comercial,l.fecha_vencimiento"""
        with self.db.cursor() as (_, c):
            c.execute(sql); return c.fetchall()

    def apply(self, user: dict, tipo: str, lote_id: int, cantidad: int, motivo: str) -> None:
        """Merma/Vencido/Devolución: 'cantidad' es lo que SALE. Conteo físico: 'cantidad' es el conteo real."""
        require(user, "ajustar_inventario")
        if tipo not in TIPOS or len(" ".join(motivo.split())) < MIN_LARGO_MOTIVO:
            raise ValueError(f"Selecciona el tipo de ajuste e indica el motivo (mínimo {MIN_LARGO_MOTIVO} letras).")
        if cantidad < 0 or (tipo != "Conteo físico" and cantidad == 0):
            raise ValueError("La cantidad indicada no es válida.")
        con = self.db.get_connection(); c = con.cursor(dictionary=True)
        try:
            con.start_transaction()
            c.execute("SELECT id,producto_id,cantidad_actual,fecha_vencimiento,estado FROM lotes WHERE id=%s FOR UPDATE", (lote_id,))
            lot = c.fetchone()
            if not lot:
                raise ValueError("Lote no encontrado.")
            if lot["estado"] == "Retirado":
                raise ValueError("El lote está retirado: no admite ajustes.")
            before = lot["cantidad_actual"]
            after = cantidad if tipo == "Conteo físico" else before - cantidad
            if after < 0:
                raise ValueError(f"El lote solo tiene {before} unidad(es).")
            if lot["estado"] == "Cuarentena":
                state = "Cuarentena"  # ajustar la cantidad nunca libera un lote inmovilizado
            else:
                state = "Agotado" if after == 0 else ("Disponible" if lot["fecha_vencimiento"] >= date.today() else "Vencido")
            c.execute("UPDATE lotes SET cantidad_actual=%s, estado=%s WHERE id=%s", (after, state, lote_id))
            c.execute("INSERT INTO ajustes_inventario(tipo,producto_id,lote_id,cantidad_antes,cantidad_despues,motivo,usuario_id) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                      (tipo, lot["producto_id"], lote_id, before, after, motivo.strip(), user["id"]))
            c.execute("INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                      (lot["producto_id"], lote_id, _MOVIMIENTO[tipo], after - before, motivo.strip(), tipo, user["id"]))
            AuditoriaModel.log(c, user["id"], "AJUSTE_STOCK", "lotes", lote_id, f"{tipo}: {before} → {after}. {motivo.strip()}")
            con.commit()
        except Exception:
            con.rollback(); raise
        finally:
            c.close(); con.close()

    def history(self, limit: int = 200) -> list[dict]:
        sql = """SELECT a.fecha,a.tipo,p.nombre_comercial,l.numero_lote,a.cantidad_antes,a.cantidad_despues,a.motivo,u.nombre usuario
                 FROM ajustes_inventario a JOIN productos p ON p.id=a.producto_id JOIN lotes l ON l.id=a.lote_id JOIN usuarios u ON u.id=a.usuario_id
                 ORDER BY a.id DESC LIMIT %s"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (limit,)); return c.fetchall()
