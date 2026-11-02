"""Permisos por rol. Punto único de verdad para la interfaz y los modelos."""
ADMIN, REGENTE, VENDEDOR = "Administrador", "Regente", "Vendedor"

PERMISOS: dict[str, set[str]] = {
    ADMIN: {"ajustar_inventario", "cambiar_precios", "anular_ventas", "gestionar_productos", "gestionar_usuarios",
            "ver_auditoria", "compras", "reportes", "libro_controlados", "respaldos", "gestionar_clientes"},
    REGENTE: {"ajustar_inventario", "cambiar_precios", "anular_ventas", "gestionar_productos",
              "ver_auditoria", "compras", "reportes", "libro_controlados", "gestionar_clientes"},
    VENDEDOR: {"gestionar_clientes"},
}


def can(user: dict, permission: str) -> bool:
    """Indica si el rol del usuario tiene el permiso."""
    return permission in PERMISOS.get(user.get("rol", ""), set())


def require(user: dict, permission: str) -> None:
    """Lanza PermissionError si el usuario no tiene el permiso (defensa en la capa de lógica)."""
    if not can(user, permission):
        raise PermissionError("Tu rol no tiene permiso para realizar esta acción.")
