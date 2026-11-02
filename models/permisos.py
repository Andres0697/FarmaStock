"""Comprobación de permisos hecha en la base de datos (no solo en la interfaz)."""

ADMIN, REGENTE = "Administrador", "Regente"


def require_role(cursor, user_id, action, roles=(ADMIN, REGENTE)):
    """Lanza PermissionError si el usuario no está activo o su rol no está en `roles`.

    `action` completa la frase: "Solo un administrador o el regente puede <action>."
    Debe ser coherente con la matriz de utils/permisos.py (que usa la interfaz).
    """
    cursor.execute("SELECT rol, estado FROM usuarios WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or user["rol"] not in roles or user["estado"] != "Activo":
        who = "un administrador" if tuple(roles) == (ADMIN,) else "un administrador o el regente"
        raise PermissionError(f"Solo {who} puede {action}.")


def require_admin(cursor, user_id, action):
    """Solo administradores activos (p. ej. gestión de usuarios)."""
    require_role(cursor, user_id, action, roles=(ADMIN,))
