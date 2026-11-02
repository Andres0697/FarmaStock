from models.auditoria_model import AuditoriaModel


class CajaModel:
    """Turnos de caja con apertura, arqueo y cierre."""

    def __init__(self, db):
        self.db = db

    def current(self, user_id: int) -> dict | None:
        with self.db.cursor() as (_, c):
            c.execute("SELECT * FROM turnos_caja WHERE usuario_id=%s AND estado='Abierto' ORDER BY id DESC LIMIT 1", (user_id,))
            return c.fetchone()

    def open(self, user_id: int, monto_inicial: float) -> int:
        if monto_inicial < 0:
            raise ValueError("El monto inicial no puede ser negativo.")
        if self.current(user_id):
            raise ValueError("Ya tienes un turno abierto.")
        with self.db.cursor() as (con, c):
            c.execute("INSERT INTO turnos_caja(usuario_id,monto_inicial) VALUES(%s,%s)", (user_id, monto_inicial))
            shift_id = c.lastrowid  # capturar antes de que la bitácora cambie lastrowid
            AuditoriaModel.log(c, user_id, "APERTURA_CAJA", "turnos_caja", shift_id, f"Monto inicial C$ {monto_inicial:.2f}")
            con.commit(); return shift_id

    def summary(self, turno_id: int) -> dict:
        """Totales por método de pago y efectivo esperado (inicial + ventas en efectivo - devoluciones en efectivo)."""
        with self.db.cursor() as (_, c):
            c.execute("SELECT monto_inicial FROM turnos_caja WHERE id=%s", (turno_id,))
            initial = float(c.fetchone()["monto_inicial"])
            c.execute("SELECT metodo_pago,COALESCE(SUM(total),0) total,COUNT(*) n FROM ventas WHERE turno_id=%s AND estado='Completada' GROUP BY metodo_pago", (turno_id,))
            by_method = {r["metodo_pago"]: float(r["total"]) for r in c.fetchall()}
            c.execute("""SELECT COALESCE(SUM(nc.monto),0) m FROM notas_credito nc JOIN ventas v ON v.id=nc.venta_id
                         WHERE v.turno_id=%s AND v.metodo_pago='Efectivo'""", (turno_id,))
            refunds = float(c.fetchone()["m"])
        return {"inicial": initial, "por_metodo": by_method, "devoluciones_efectivo": refunds,
                "efectivo_esperado": initial + by_method.get("Efectivo", 0.0) - refunds}

    def close(self, user_id: int, turno_id: int, contado: float) -> dict:
        if contado < 0:
            raise ValueError("El efectivo contado no puede ser negativo.")
        summary = self.summary(turno_id)
        diff = contado - summary["efectivo_esperado"]
        with self.db.cursor() as (con, c):
            c.execute("UPDATE turnos_caja SET estado='Cerrado',cierre=NOW(),efectivo_esperado=%s,efectivo_contado=%s,diferencia=%s WHERE id=%s AND estado='Abierto'",
                      (summary["efectivo_esperado"], contado, diff, turno_id))
            AuditoriaModel.log(c, user_id, "CIERRE_CAJA", "turnos_caja", turno_id, f"Esperado {summary['efectivo_esperado']:.2f} · contado {contado:.2f} · dif {diff:.2f}")
            con.commit()
        return {**summary, "contado": contado, "diferencia": diff}

    def history(self, limit: int = 50) -> list[dict]:
        sql = """SELECT t.id,u.nombre usuario,t.apertura,t.cierre,t.monto_inicial,t.efectivo_esperado,t.efectivo_contado,t.diferencia,t.estado
                 FROM turnos_caja t JOIN usuarios u ON u.id=t.usuario_id ORDER BY t.id DESC LIMIT %s"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (limit,)); return c.fetchall()
