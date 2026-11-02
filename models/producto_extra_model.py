from models.auditoria_model import AuditoriaModel
from utils.permisos import require

CATEGORIAS_DISPENSACION = ("Venta libre", "Con receta", "Receta retenida", "Controlado")


def classify_equivalence(base: dict, other: dict) -> str:
    """Clasifica un producto frente al original (solo con datos registrados).

    'Equivalente'          mismo principio activo, concentración, unidad, forma y vía.
    'Verificar'            mismo principio activo pero algo difiere o falta (no se asume equivalencia).
    Nunca se fusionan existencias ni se autoriza una sustitución: es información de consulta.
    """
    keys = ("concentracion", "unidad_concentracion", "forma_farmaceutica", "via_administracion")
    for key in keys:
        a, b = base.get(key), other.get(key)
        if a in (None, "") or b in (None, ""):
            return "Verificar"
        if key == "concentracion":
            if float(a) != float(b):
                return "Verificar"
        elif str(a).strip().lower() != str(b).strip().lower():
            return "Verificar"
    return "Equivalente"


class ProductoExtraModel:
    """Datos regulatorios, historial de precios y sustitutos (complementa a ProductoModel sin modificarlo)."""

    def __init__(self, db):
        self.db = db

    def get_regulatory(self, producto_id: int) -> dict:
        with self.db.cursor() as (_, c):
            c.execute("SELECT registro_sanitario,categoria_dispensacion,precio_venta,cantidad_presentacion FROM productos WHERE id=%s", (producto_id,))
            return c.fetchone() or {}

    def save_regulatory(self, user: dict, producto_id: int, registro: str | None, categoria: str, old_price: float, new_price: float,
                        requiere_receta: bool | None = None, control_especial: bool | None = None) -> None:
        """Guarda registro sanitario/categoría y deja historial + auditoría si cambió el precio."""
        if categoria not in CATEGORIAS_DISPENSACION:
            raise ValueError("Categoría de dispensación no válida.")
        con = self.db.get_connection(); c = con.cursor(dictionary=True)
        try:
            con.start_transaction()
            c.execute("UPDATE productos SET registro_sanitario=%s,categoria_dispensacion=%s,requiere_receta=%s,control_especial=%s WHERE id=%s",
                      (registro or None, categoria,
                       (categoria != "Venta libre") if requiere_receta is None else bool(requiere_receta),
                       (categoria == "Controlado") if control_especial is None else bool(control_especial), producto_id))
            if (control_especial if control_especial is not None else categoria == "Controlado") and not (
                    requiere_receta if requiere_receta is not None else categoria != "Venta libre"):
                raise ValueError("Un producto de control especial siempre requiere receta.")
            if round(float(old_price), 2) != round(float(new_price), 2):
                require(user, "cambiar_precios")
                c.execute("INSERT INTO historial_precios(producto_id,precio_anterior,precio_nuevo,usuario_id) VALUES(%s,%s,%s,%s)",
                          (producto_id, old_price, new_price, user["id"]))
                AuditoriaModel.log(c, user["id"], "CAMBIO_PRECIO", "productos", producto_id, f"C$ {float(old_price):.2f} → C$ {float(new_price):.2f}")
            con.commit()
        except Exception:
            con.rollback(); raise
        finally:
            c.close(); con.close()

    def price_history(self, producto_id: int) -> list[dict]:
        sql = """SELECT h.fecha,h.precio_anterior,h.precio_nuevo,u.nombre usuario FROM historial_precios h
                 JOIN usuarios u ON u.id=h.usuario_id WHERE h.producto_id=%s ORDER BY h.id DESC"""
        with self.db.cursor() as (_, c):
            c.execute(sql, (producto_id,)); return c.fetchall()

    def substitutes(self, producto_id: int) -> list[dict]:
        """Productos activos con el mismo principio activo y stock válido, marcando si la equivalencia está confirmada."""
        sql = """SELECT p.id,p.codigo,p.nombre_comercial,p.concentracion,p.unidad_concentracion,p.forma_farmaceutica,
                        p.via_administracion,p.presentacion,p.precio_venta,
                        COALESCE(SUM(CASE WHEN l.estado='Disponible' AND l.fecha_vencimiento>=CURDATE() THEN l.cantidad_actual ELSE 0 END),0) stock
                 FROM productos p JOIN productos o ON o.principio_activo_id=p.principio_activo_id AND o.id=%s
                 LEFT JOIN lotes l ON l.producto_id=p.id
                 WHERE p.id<>%s AND p.estado='Activo' GROUP BY p.id HAVING stock>0 ORDER BY p.precio_venta"""
        with self.db.cursor() as (_, c):
            c.execute("SELECT concentracion,unidad_concentracion,forma_farmaceutica,via_administracion FROM productos WHERE id=%s", (producto_id,))
            base = c.fetchone() or {}
            c.execute(sql, (producto_id, producto_id))
            rows = c.fetchall()
        for row in rows:
            row["equivalencia"] = classify_equivalence(base, row)
        return sorted(rows, key=lambda r: (r["equivalencia"] != "Equivalente", float(r["precio_venta"])))
