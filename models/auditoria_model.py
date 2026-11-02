from typing import Optional


class AuditoriaModel:
    """Bitácora de auditoría y consulta de desviaciones FEFO."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def log(cursor, user_id: Optional[int], accion: str, entidad: str, entidad_id=None, detalle: str = "") -> None:
        """Registra un evento usando el cursor (y por tanto la transacción) del llamador."""
        cursor.execute(
            "INSERT INTO bitacora_auditoria(usuario_id,accion,entidad,entidad_id,detalle) VALUES(%s,%s,%s,%s,%s)",
            (user_id, accion, entidad, None if entidad_id is None else str(entidad_id), detalle[:500]),
        )

    def log_now(self, user_id, accion, entidad, entidad_id=None, detalle="") -> None:
        """Registra un evento en su propia transacción."""
        with self.db.cursor() as (con, cur):
            self.log(cur, user_id, accion, entidad, entidad_id, detalle)
            con.commit()

    def list_events(self, accion: str = "", limit: int = 300) -> list[dict]:
        sql = """SELECT b.fecha, COALESCE(u.nombre,'—') usuario, b.accion, b.entidad, b.entidad_id, b.detalle
                 FROM bitacora_auditoria b LEFT JOIN usuarios u ON u.id=b.usuario_id
                 WHERE (%s='' OR b.accion=%s) ORDER BY b.id DESC LIMIT %s"""
        with self.db.cursor() as (_, cur):
            cur.execute(sql, (accion, accion, limit))
            return cur.fetchall()

    def actions(self) -> list[str]:
        with self.db.cursor() as (_, cur):
            cur.execute("SELECT DISTINCT accion FROM bitacora_auditoria ORDER BY accion")
            return [r["accion"] for r in cur.fetchall()]

    def fefo_deviations(self, limit: int = 300) -> list[dict]:
        sql = """SELECT d.fecha, d.venta_id, u.nombre usuario, p.nombre_comercial,
                        ls.numero_lote lote_sugerido, ls.fecha_vencimiento vence_sugerido,
                        lv.numero_lote lote_vendido, lv.fecha_vencimiento vence_vendido, COALESCE(d.motivo,'—') motivo
                 FROM desviaciones_fefo d
                 JOIN usuarios u ON u.id=d.usuario_id
                 JOIN lotes ls ON ls.id=d.lote_sugerido_id
                 JOIN lotes lv ON lv.id=d.lote_vendido_id
                 JOIN productos p ON p.id=lv.producto_id
                 ORDER BY d.id DESC LIMIT %s"""
        with self.db.cursor() as (_, cur):
            cur.execute(sql, (limit,))
            return cur.fetchall()
