"""
Repositorio en memoria (simula la base de datos Cloud SQL / PostgreSQL).

Patrón **Repository**: encapsula el acceso a datos detrás de métodos con nombre
de negocio (``get_order``, ``save_assignment``...). La lógica de negocio no sabe
si los datos viven en memoria, en PostgreSQL o en Firestore; así se puede
probar con un repositorio en memoria y desplegar con uno real.
"""

# copy.deepcopy: devolvemos copias para que nadie modifique el estado por accidente.
import copy

# itertools.count: contador incremental para generar IDs secuenciales.
import itertools

# threading: RLock (lock re-entrante) para operaciones atómicas.
import threading

# Datos iniciales del sistema.
from sut.data import WAREHOUSES, build_operators, build_orders, build_users


class InMemoryRepository:
    """
    Almacena usuarios, operadores, almacenes, pedidos y asignaciones en memoria.

    Attributes:
        lock: lock re-entrante que protege las estructuras internas del repositorio.
            Para la asignación, el servicio usa ``order_lock(order_id)`` para que
            "verificar si el pedido está libre + asignarlo" sea ATÓMICO por pedido
            (equivale a un ``SELECT ... FOR UPDATE`` en SQL).
    """

    def __init__(self) -> None:
        """Crea el repositorio y lo llena con los datos semilla."""
        self.lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        """Restaura el estado inicial (datos semilla) del repositorio."""
        with self.lock:
            self.users = build_users()
            self.operators = build_operators()
            self.warehouses = set(WAREHOUSES)
            self.orders = build_orders()
            # orderId -> asignación vigente.
            self.assignments: dict[str, dict] = {}
            # IDs de asignación empiezan en 44021 (como el ejemplo del PDF).
            self._assignment_seq = itertools.count(44021)
            # IDs de pedidos generados para pruebas empiezan en ORD-2026-100000.
            self._order_seq = itertools.count(100000)
            # Un lock por pedido (equivale al bloqueo de FILA de "SELECT ... FOR UPDATE"):
            # dos asignaciones del MISMO pedido se serializan; pedidos distintos no se bloquean entre sí.
            self._order_locks: dict[str, threading.Lock] = {}

    def order_lock(self, order_id: str) -> threading.Lock:
        """
        Devuelve el lock exclusivo de un pedido (lo crea la primera vez).

        Args:
            order_id: pedido a bloquear.

        Returns:
            Lock asociado a ese pedido.
        """
        with self.lock:
            return self._order_locks.setdefault(order_id, threading.Lock())

    # --- Lecturas -------------------------------------------------------------
    def get_user(self, username: str) -> dict | None:
        """Devuelve el usuario por nombre o ``None`` si no existe."""
        return self.users.get(username)

    def get_operator(self, operator_id: str) -> dict | None:
        """Devuelve el operador por ID o ``None``."""
        return self.operators.get(operator_id)

    def warehouse_exists(self, warehouse_id: str) -> bool:
        """Indica si el almacén existe."""
        return warehouse_id in self.warehouses

    def get_order(self, order_id: str) -> dict | None:
        """Devuelve una COPIA del pedido o ``None``."""
        order = self.orders.get(order_id)
        return copy.deepcopy(order) if order else None

    def get_assignment(self, order_id: str) -> dict | None:
        """Devuelve la asignación vigente de un pedido o ``None``."""
        assignment = self.assignments.get(order_id)
        return copy.deepcopy(assignment) if assignment else None

    def list_orders(self) -> list[dict]:
        """
        Lista todos los pedidos con su operador asignado (si lo tienen).

        Returns:
            Lista de diccionarios ``{orderId, warehouseId, status, operatorId, items}``.
        """
        with self.lock:
            result = []
            for order_id, order in sorted(self.orders.items()):
                assignment = self.assignments.get(order_id)
                result.append({
                    "orderId": order_id,
                    "warehouseId": order["warehouseId"],
                    "status": order["status"],
                    "operatorId": assignment["operatorId"] if assignment else None,
                    "items": copy.deepcopy(order["items"]),
                })
            return result

    # --- Escrituras -----------------------------------------------------------
    def next_assignment_id(self) -> str:
        """Genera el siguiente ID de asignación (``ASG-44021``, ``ASG-44022``...)."""
        with self.lock:
            return f"ASG-{next(self._assignment_seq)}"

    def save_assignment(self, assignment: dict) -> None:
        """
        Guarda la asignación y cambia el estado del pedido a ``ASSIGNED``.

        Args:
            assignment: diccionario con ``orderId``, ``operatorId``, etc.
        """
        with self.lock:
            self.assignments[assignment["orderId"]] = copy.deepcopy(assignment)
            self.orders[assignment["orderId"]]["status"] = "ASSIGNED"

    def create_orders(self, warehouse_id: str, status: str, count: int) -> list[str]:
        """
        Crea pedidos nuevos (sólo para soporte de pruebas / datos de prueba).

        Args:
            warehouse_id: almacén del pedido.
            status: estado inicial.
            count: cantidad de pedidos a crear.

        Returns:
            Lista con los IDs creados.
        """
        created = []
        with self.lock:
            for _ in range(count):
                order_id = f"ORD-2026-{next(self._order_seq):06d}"
                self.orders[order_id] = {
                    "warehouseId": warehouse_id,
                    "status": status,
                    "items": [{"sku": "SKU-1001", "qty": 1}],
                }
                created.append(order_id)
        return created
