"""Ejecutor de migraciones numeradas.

Archivos: sql/migraciones/NNN_nombre.sql y NNN_nombre_down.sql

Reglas:
  * Cada versión (NNN) debe ser única. Si hay dos archivos con la misma versión
    se lanza un error en lugar de omitir uno en silencio.
  * Una migración se registra en `schema_migraciones` solo cuando TODAS sus
    sentencias terminaron bien. MySQL confirma el DDL de forma implícita, por lo
    que no hay rollback posible: por eso las migraciones correctivas son
    idempotentes y pueden volver a ejecutarse tras un fallo.
  * Directiva opcional antes de una sentencia:
        -- @skip_if: SELECT COUNT(*) FROM information_schema.columns WHERE ...
    Si la consulta devuelve un número mayor que 0, la sentencia se omite.
"""
import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "sql" / "migraciones"
_CREATE_CONTROL = """
CREATE TABLE IF NOT EXISTS schema_migraciones (
    version VARCHAR(10) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    aplicada_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB
"""
# Migraciones antiguas que compartían número con otras y nunca se aplicaban. Si quedaron
# en la carpeta (por ejemplo, al copiar una versión nueva sobre la anterior) se ignoran.
OBSOLETAS = {
    "001_ventas_pago_anulacion_desviaciones",
    "002_entradas_mercaderia",
}
_DIRECTIVE = re.compile(r"^--\s*@skip_if:\s*(.+)$")


class MigrationError(RuntimeError):
    """Error de configuración o ejecución de migraciones."""


def parse_script(text: str) -> list[tuple[str | None, str]]:
    """Divide un script en [(condición_skip_if | None, sentencia)].

    Respeta comillas simples, dobles y acentos graves (un `;` dentro de un
    texto no corta la sentencia) y descarta los comentarios `-- ...`.
    """
    result: list[tuple[str | None, str]] = []
    buffer: list[str] = []
    pending_skip: str | None = None
    quote: str | None = None
    i, n = 0, len(text)
    at_line_start = True

    def flush():
        nonlocal buffer, pending_skip
        statement = "".join(buffer).strip()
        buffer = []
        if statement:
            result.append((pending_skip, statement))
            pending_skip = None

    while i < n:
        ch = text[i]
        if quote:
            buffer.append(ch)
            if ch == "\\" and quote != "`" and i + 1 < n:
                buffer.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                if i + 1 < n and text[i + 1] == quote:  # comilla duplicada ''
                    buffer.append(text[i + 1])
                    i += 2
                    continue
                quote = None
            at_line_start = ch == "\n"
            i += 1
            continue

        if ch == "-" and text.startswith("--", i) and (at_line_start or text[i - 1] in " \t"):
            end = text.find("\n", i)
            end = n if end == -1 else end
            comment = text[i:end].strip()
            directive = _DIRECTIVE.match(comment)
            if directive and not "".join(buffer).strip():
                pending_skip = directive.group(1).strip().rstrip(";")
            i = end
            continue

        if ch in ("'", '"', "`"):
            quote = ch
            buffer.append(ch)
        elif ch == ";":
            flush()
        else:
            buffer.append(ch)
        at_line_start = ch == "\n" or (at_line_start and ch in " \t")
        i += 1

    flush()
    return result


def _split_name(path: Path) -> tuple[str, str]:
    version, _, name = path.stem.partition("_")
    return version, name


def up_files() -> list[Path]:
    """Migraciones hacia adelante, ordenadas. Falla si una versión se repite."""
    files = sorted(
        p for p in MIGRATIONS_DIR.glob("*.sql")
        if not p.stem.endswith("_down") and p.stem not in OBSOLETAS
    )
    seen: dict[str, Path] = {}
    for path in files:
        version, _ = _split_name(path)
        if not version.isdigit():
            raise MigrationError(f"Nombre de migración inválido: {path.name}")
        if version in seen:
            raise MigrationError(
                f"Versión de migración repetida ({version}): {seen[version].name} y {path.name}. "
                "Cada migración debe tener un número único."
            )
        seen[version] = path
    return files


def applied_versions(db) -> set[str]:
    with db.cursor() as (con, cur):
        cur.execute(_CREATE_CONTROL)
        cur.execute("SELECT version FROM schema_migraciones")
        return {row["version"] for row in cur.fetchall()}


def pending(db) -> list[Path]:
    done = applied_versions(db)
    return [p for p in up_files() if _split_name(p)[0] not in done]


def run_script(cur, path: Path) -> int:
    """Ejecuta un script; devuelve cuántas sentencias se ejecutaron (sin las omitidas)."""
    executed = 0
    for skip_sql, statement in parse_script(path.read_text(encoding="utf-8")):
        if skip_sql:
            cur.execute(skip_sql)
            rows = cur.fetchall()  # se lee todo el resultado para dejar libre el cursor
            row = rows[0] if rows else None
            value = (next(iter(row.values())) if isinstance(row, dict) else row[0]) if row else 0
            if value and int(value) > 0:
                continue
        cur.execute(statement)
        executed += 1
    return executed


def apply_pending(db) -> list[str]:
    """Aplica en orden las migraciones pendientes. Devuelve las versiones aplicadas."""
    applied = []
    for path in pending(db):
        version, name = _split_name(path)
        with db.cursor() as (con, cur):
            try:
                run_script(cur, path)
            except Exception as exc:
                raise MigrationError(f"La migración {path.name} falló: {exc}") from exc
            cur.execute("INSERT INTO schema_migraciones(version,nombre) VALUES(%s,%s)", (version, name))
            con.commit()
        applied.append(version)
    return applied


def rollback_last(db) -> str | None:
    """Revierte la última migración aplicada usando su script *_down.sql."""
    with db.cursor() as (con, cur):
        cur.execute(_CREATE_CONTROL)
        cur.execute("SELECT version,nombre FROM schema_migraciones ORDER BY version DESC LIMIT 1")
        last = cur.fetchone()
    if not last:
        return None
    down = MIGRATIONS_DIR / f"{last['version']}_{last['nombre']}_down.sql"
    if not down.exists():
        raise MigrationError(f"No existe el script de reversión {down.name}.")
    with db.cursor() as (con, cur):
        run_script(cur, down)
        cur.execute("DELETE FROM schema_migraciones WHERE version=%s", (last["version"],))
        con.commit()
    return last["version"]


if __name__ == "__main__":  # python -m database.migrations [rollback]
    import sys

    from database.connection import Database

    database = Database()
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("Revertida:", rollback_last(database))
    else:
        print("Aplicadas:", apply_pending(database) or "ninguna (al día)")
