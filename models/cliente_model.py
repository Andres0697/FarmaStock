class ClienteModel:
    """Clientes, historial de compras y cuentas por cobrar (ventas a crédito - abonos)."""

    def __init__(self, db):
        self.db = db

    def list_all(self, search: str = "") -> list[dict]:
        sql = """SELECT c.id,c.nombre,c.documento,c.ruc,c.telefono,c.direccion,c.limite_credito,c.estado,
                 COALESCE((SELECT SUM(total) FROM ventas v WHERE v.cliente_id=c.id AND v.metodo_pago='Crédito' AND v.estado='Completada'),0)
                 - COALESCE((SELECT SUM(monto) FROM abonos_cliente a WHERE a.cliente_id=c.id),0) AS saldo
                 FROM clientes c WHERE (%s='' OR c.nombre LIKE %s OR c.documento LIKE %s) ORDER BY c.nombre"""
        with self.db.cursor() as (_, cur):
            pattern = f"%{search}%"  # el comodín va en el parámetro, no en el SQL
            cur.execute(sql, (search, pattern, pattern)); return cur.fetchall()

    def active(self) -> list[dict]:
        return [c for c in self.list_all() if c["estado"] == "Activo"]

    def save(self, data: dict, cliente_id: int | None = None) -> None:
        if not data["nombre"].strip():
            raise ValueError("El nombre del cliente es obligatorio.")
        values = (data["nombre"].strip(), data.get("documento") or None, data.get("ruc") or None, data.get("telefono") or None,
                  data.get("direccion") or None, data.get("limite_credito", 0), data.get("estado", "Activo"))
        with self.db.cursor() as (con, c):
            if cliente_id:
                c.execute("UPDATE clientes SET nombre=%s,documento=%s,ruc=%s,telefono=%s,direccion=%s,limite_credito=%s,estado=%s WHERE id=%s", (*values, cliente_id))
            else:
                c.execute("INSERT INTO clientes(nombre,documento,ruc,telefono,direccion,limite_credito,estado) VALUES(%s,%s,%s,%s,%s,%s,%s)", values)
            con.commit()

    def purchases(self, cliente_id: int) -> list[dict]:
        sql = "SELECT id,fecha,metodo_pago,total,estado,numero_factura FROM ventas WHERE cliente_id=%s ORDER BY id DESC LIMIT 200"
        with self.db.cursor() as (_, c):
            c.execute(sql, (cliente_id,)); return c.fetchall()

    def add_payment(self, user_id: int, cliente_id: int, monto: float) -> None:
        if monto <= 0:
            raise ValueError("El abono debe ser mayor que cero.")
        saldo = next(c["saldo"] for c in self.list_all() if c["id"] == cliente_id)
        if monto > float(saldo):
            raise ValueError(f"El abono supera el saldo pendiente (C$ {float(saldo):,.2f}).")
        with self.db.cursor() as (con, c):
            c.execute("INSERT INTO abonos_cliente(cliente_id,monto,usuario_id) VALUES(%s,%s,%s)", (cliente_id, monto, user_id))
            con.commit()
