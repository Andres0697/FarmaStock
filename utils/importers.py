"""Lectura y validación de archivos CSV de categorías (sin acceso a la base de datos)."""
import csv
from pathlib import Path

from utils.helpers import clean_text

MAX_BYTES = 2 * 1024 * 1024
MAX_FILAS = 2000
ESTADOS = {"activo": "Activo", "inactivo": "Inactivo"}


class ArchivoInvalido(ValueError):
    """Archivo inválido (no se puede leer o no tiene el formato esperado)."""


def parse_categorias_csv(path) -> tuple[list[dict], list[str]]:
    """Devuelve (filas válidas, errores por línea). Cabecera: nombre[,descripcion[,estado]]."""
    file = Path(path)
    if file.suffix.lower() != ".csv":
        raise ArchivoInvalido("Seleccione un archivo con extensión .csv.")
    if not file.is_file():
        raise ArchivoInvalido("El archivo no existe o no se puede abrir.")
    if file.stat().st_size > MAX_BYTES:
        raise ArchivoInvalido("El archivo supera el límite de 2 MB.")
    try:
        text = file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArchivoInvalido("El archivo debe estar guardado en UTF-8.") from exc
    except OSError as exc:
        raise ArchivoInvalido(f"No se pudo leer el archivo: {exc.strerror or exc}") from exc

    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    headers = [clean_text(h).lower() for h in (reader.fieldnames or [])]
    if "nombre" not in headers:
        raise ArchivoInvalido("Falta la columna «nombre» en la primera línea del archivo.")
    reader.fieldnames = headers

    rows, errors, seen = [], [], set()
    for number, raw in enumerate(reader, start=2):
        if len(rows) + len(errors) >= MAX_FILAS:
            errors.append(f"Se procesaron solo las primeras {MAX_FILAS} filas.")
            break
        name = clean_text(raw.get("nombre"))
        description = clean_text(raw.get("descripcion"))
        status_raw = clean_text(raw.get("estado")).lower() or "activo"
        if not name:
            if any(clean_text(v) for v in raw.values() if v):
                errors.append(f"Línea {number}: el nombre está vacío.")
            continue
        if len(name) > 100:
            errors.append(f"Línea {number}: el nombre supera 100 caracteres.")
        elif len(description) > 255:
            errors.append(f"Línea {number}: la descripción supera 255 caracteres.")
        elif status_raw not in ESTADOS:
            errors.append(f"Línea {number}: el estado debe ser Activo o Inactivo.")
        elif name.lower() in seen:
            errors.append(f"Línea {number}: «{name}» está repetida en el archivo.")
        else:
            seen.add(name.lower())
            rows.append({"nombre": name, "descripcion": description, "estado": ESTADOS[status_raw]})
    return rows, errors
