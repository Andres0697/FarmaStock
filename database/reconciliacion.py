"""Conciliación entre las existencias de cada lote y su Kardex (movimientos).

Invariante que debe cumplirse en toda la aplicación:

    lotes.cantidad_actual == SUMA(movimientos_inventario.cantidad del lote)

(las entradas suman, las salidas se guardan con signo negativo).

Uso:
    python -m database.reconciliacion                      # solo informe, no modifica nada
    python -m database.reconciliacion --aplicar --usuario-id 1 --motivo "Conciliación inicial"

`--aplicar` NO toca `lotes`: toma la existencia actual del lote como la verdad física
y agrega UN movimiento de tipo 'Ajuste' por lote descuadrado para que el Kardex la
refleje. Es repetible: después de aplicarlo el informe queda vacío.
"""
import argparse

DISCREPANCIAS_SQL = """
SELECT l.id AS lote_id, p.codigo, p.nombre_comercial, l.numero_lote,
       l.cantidad_inicial, l.cantidad_actual,
       COALESCE(SUM(m.cantidad), 0) AS kardex,
       l.cantidad_actual - COALESCE(SUM(m.cantidad), 0) AS diferencia
FROM lotes l
JOIN productos p ON p.id = l.producto_id
LEFT JOIN movimientos_inventario m ON m.lote_id = l.id
GROUP BY l.id, p.codigo, p.nombre_comercial, l.numero_lote, l.cantidad_inicial, l.cantidad_actual
HAVING diferencia <> 0
ORDER BY p.nombre_comercial, l.numero_lote
"""

REFERENCIA = "RECONCILIACION"


def discrepancias(db) -> list[dict]:
    """Lotes cuya existencia no coincide con la suma de sus movimientos."""
    with db.cursor() as (_, cur):
        cur.execute(DISCREPANCIAS_SQL)
        return cur.fetchall()


def aplicar(db, usuario_id: int, motivo: str) -> int:
    """Agrega un movimiento de ajuste por lote descuadrado. Devuelve cuántos agregó."""
    motivo = " ".join((motivo or "").split())
    if len(motivo) < 5:
        raise ValueError("Escriba un motivo de al menos 5 caracteres.")
    with db.transaction() as cur:
        cur.execute("SELECT id FROM usuarios WHERE id=%s AND estado='Activo'", (usuario_id,))
        if not cur.fetchone():
            raise ValueError("El usuario indicado no existe o está inactivo.")
        cur.execute(DISCREPANCIAS_SQL)
        rows = cur.fetchall()
        for row in rows:
            cur.execute("SELECT producto_id FROM lotes WHERE id=%s", (row["lote_id"],))
            producto_id = cur.fetchone()["producto_id"]
            cur.execute(
                "INSERT INTO movimientos_inventario(producto_id,lote_id,tipo_movimiento,cantidad,motivo,referencia,usuario_id) "
                "VALUES(%s,%s,'Ajuste',%s,%s,%s,%s)",
                (producto_id, row["lote_id"], int(row["diferencia"]), motivo, REFERENCIA, usuario_id),
            )
            cur.execute(
                "INSERT INTO bitacora_auditoria(usuario_id,accion,entidad,entidad_id,detalle) VALUES(%s,'RECONCILIACION','lotes',%s,%s)",
                (usuario_id, str(row["lote_id"]),
                 f"Kardex {row['kardex']} -> {row['cantidad_actual']} (ajuste {int(row['diferencia']):+d}). {motivo}"[:500]),
            )
        return len(rows)


def _imprimir(rows: list[dict]) -> None:
    if not rows:
        print("Conciliación correcta: todas las existencias coinciden con el Kardex.")
        return
    print(f"{'Lote':>5}  {'Código':<8} {'N.º lote':<12} {'Inicial':>7} {'Actual':>7} {'Kardex':>7} {'Dif.':>6}  Producto")
    for r in rows:
        print(f"{r['lote_id']:>5}  {r['codigo']:<8} {r['numero_lote']:<12} {r['cantidad_inicial']:>7} "
              f"{r['cantidad_actual']:>7} {int(r['kardex']):>7} {int(r['diferencia']):>+6}  {r['nombre_comercial']}")
    print(f"\n{len(rows)} lote(s) descuadrado(s). Revise el stock físico antes de usar --aplicar.")


if __name__ == "__main__":
    from database.connection import Database

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aplicar", action="store_true", help="agrega los movimientos de ajuste")
    parser.add_argument("--usuario-id", type=int, help="usuario responsable del ajuste")
    parser.add_argument("--motivo", default="", help="motivo del ajuste de conciliación")
    args = parser.parse_args()
    database = Database()
    _imprimir(discrepancias(database))
    if args.aplicar:
        if not args.usuario_id:
            parser.error("--aplicar requiere --usuario-id")
        print("Movimientos agregados:", aplicar(database, args.usuario_id, args.motivo))
