"""
Datos semilla (seed data) del servicio simulado.

Representan el estado inicial "conocido" del sistema. Contar con datos
deterministas es una buena práctica de testing: cada prueba sabe de antemano
qué usuarios, operadores, almacenes y pedidos existen.

IMPORTANTE: las contraseñas de abajo son credenciales SINTÉTICAS de un entorno
local de pruebas. En un sistema real nunca se versionan contraseñas; se usan
secretos (GitHub Secrets / Secret Manager) y usuarios de prueba dedicados.
"""

# os.urandom genera bytes aleatorios seguros (para las sales de contraseña).
import os

# Usamos el hash de contraseñas del módulo de seguridad.
from sut.security import hash_password

# Almacenes válidos de la cadena (formato WH-NN).
WAREHOUSES: set[str] = {"WH-01", "WH-02", "WH-03", "WH-04", "WH-05"}

# Contraseñas SINTÉTICAS de la demo, definidas una sola vez. El comentario
# "nosec" le indica al SAST (Bandit) que este hallazgo fue revisado y aceptado.
_SUPERVISOR_PASSWORD = "Sup3rvisor!2025"  # noqa: S105  # nosec B105
_OPERATOR_PASSWORD = "0perator!2025"  # noqa: S105  # nosec B105
_ADMIN_PASSWORD = "Adm1n!2025"  # noqa: S105  # nosec B105

# Usuarios del Centro de Control / API.
#   role: SUPERVISOR y ADMIN pueden asignar pedidos; OPERATOR no.
#   warehouses: almacenes sobre los que el usuario tiene autoridad.
#   active: un usuario inactivo no puede iniciar sesión.
_RAW_USERS: list[dict] = [
    {"username": "supervisor1", "password": _SUPERVISOR_PASSWORD, "name": "Laura Gómez",
     "role": "SUPERVISOR", "warehouses": sorted(WAREHOUSES), "active": True},
    {"username": "supervisor2", "password": _SUPERVISOR_PASSWORD, "name": "Carlos Pérez",
     "role": "SUPERVISOR", "warehouses": sorted(WAREHOUSES), "active": True},
    {"username": "supervisor.wh01", "password": _SUPERVISOR_PASSWORD, "name": "Ana Ruiz",
     "role": "SUPERVISOR", "warehouses": ["WH-01"], "active": True},
    {"username": "sup.ratelimit", "password": _SUPERVISOR_PASSWORD, "name": "Rate Limit Probe",
     "role": "SUPERVISOR", "warehouses": sorted(WAREHOUSES), "active": True},
    {"username": "operator1", "password": _OPERATOR_PASSWORD, "name": "Pedro Operador",
     "role": "OPERATOR", "warehouses": ["WH-05"], "active": True},
    {"username": "admin", "password": _ADMIN_PASSWORD, "name": "Admin LogiTrack",
     "role": "ADMIN", "warehouses": sorted(WAREHOUSES), "active": True},
    {"username": "supervisor.locked", "password": _SUPERVISOR_PASSWORD, "name": "Usuario Bloqueado",
     "role": "SUPERVISOR", "warehouses": sorted(WAREHOUSES), "active": False},
]


def build_users() -> dict[str, dict]:
    """
    Construye el diccionario de usuarios con la contraseña ya HASHEADA.

    Returns:
        Diccionario ``username -> datos del usuario`` donde el campo
        ``password`` se reemplaza por ``password_hash``.
    """
    users: dict[str, dict] = {}
    for raw in _RAW_USERS:
        # Copiamos el registro para no mutar la lista original.
        user = dict(raw)
        # Quitamos la contraseña en texto plano y guardamos sólo su hash con sal aleatoria.
        user["password_hash"] = hash_password(user.pop("password"), os.urandom(16))
        users[user["username"]] = user
    return users


def build_operators() -> dict[str, dict]:
    """
    Operadores de almacén (usuarios de la app PickApp).

    Returns:
        Diccionario ``operatorId -> {name, warehouseId, active}``.
    """
    return {
        "OP-312": {"name": "Juan Torres", "warehouseId": "WH-05", "active": True},
        "OP-313": {"name": "María López", "warehouseId": "WH-05", "active": True},
        "OP-314": {"name": "Diego Castro", "warehouseId": "WH-05", "active": True},
        "OP-100": {"name": "Sofía Díaz", "warehouseId": "WH-01", "active": True},
        # Operador inactivo: sirve para el caso negativo "operador inactivo".
        "OP-999": {"name": "Operador De Baja", "warehouseId": "WH-05", "active": False},
    }


def build_orders() -> dict[str, dict]:
    """
    Pedidos iniciales.

    Estados posibles:
        - READY_FOR_ASSIGNMENT: stock reservado, listo para asignar.
        - ASSIGNED: ya tiene operador.
        - PENDING_RESTOCK: sin stock (no se debe asignar).
        - CANCELLED: cancelado (no se debe asignar).

    Returns:
        Diccionario ``orderId -> datos del pedido``.
    """
    # Lista de productos de ejemplo (SKU + cantidad) que verá el operador.
    items = [{"sku": "SKU-1001", "qty": 2}, {"sku": "SKU-2002", "qty": 1}]
    orders: dict[str, dict] = {
        # El pedido del enunciado del PDF.
        "ORD-2025-007841": {"warehouseId": "WH-05", "status": "READY_FOR_ASSIGNMENT", "items": items},
        # Pedido de otro almacén (para probar escalamiento de privilegios / mismatch).
        "ORD-2025-001001": {"warehouseId": "WH-01", "status": "READY_FOR_ASSIGNMENT", "items": items},
        # Pedido sin stock: reproduce el problema "pedidos sin inventario".
        "ORD-2025-007900": {"warehouseId": "WH-05", "status": "PENDING_RESTOCK", "items": items},
        # Pedido cancelado.
        "ORD-2025-007901": {"warehouseId": "WH-05", "status": "CANCELLED", "items": items},
    }
    # 20 pedidos adicionales listos para asignar en WH-05 (ORD-2025-007842 ... 007861).
    for number in range(7842, 7862):
        orders[f"ORD-2025-{number:06d}"] = {
            "warehouseId": "WH-05", "status": "READY_FOR_ASSIGNMENT", "items": items,
        }
    return orders
