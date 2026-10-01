"""
Lógica de negocio (capa de servicio) de ``orders-api``.

Aquí viven las REGLAS de asignación de pedidos. No hay nada de HTTP: recibe
datos ya validados y lanza errores de dominio. Por eso es la capa ideal para
pruebas UNITARIAS (rápidas, sin red, sin servidor).

Reglas implementadas:
    1. Sólo SUPERVISOR o ADMIN pueden asignar.
    2. El usuario sólo puede asignar en almacenes bajo su autoridad
       (previene escalamiento horizontal de privilegios).
    3. El almacén, el pedido y el operador deben existir.
    4. El operador debe estar activo y pertenecer al almacén.
    5. El pedido debe pertenecer al almacén.
    6. Sólo se asignan pedidos en estado READY_FOR_ASSIGNMENT (con stock reservado).
    7. Un pedido no puede quedar asignado a dos operadores (control de concurrencia).
    8. Re-asignar el MISMO pedido al MISMO operador es idempotente (no duplica).
    9. Cada asignación nueva publica el evento ``order.assigned`` en Pub/Sub.
"""

# contextlib.nullcontext: un "lock que no bloquea", para el modo con bug simulado.
import contextlib

# time.sleep: latencia artificial para hacer reproducibles las carreras.
import time

# dataclass para devolver un resultado tipado.
from dataclasses import dataclass

# Fecha/hora en UTC para el campo "timestamp".
from datetime import UTC, datetime

# Importamos los errores de dominio que esta capa puede lanzar.
from sut.errors import (
    ForbiddenError,
    OperatorInactiveError,
    OperatorNotFoundError,
    OrderAlreadyAssignedError,
    OrderNotAssignableError,
    OrderNotFoundError,
    WarehouseMismatchError,
    WarehouseNotFoundError,
)

# Bus de eventos (Pub/Sub simulado) y nombre del topic.
from sut.events import ORDER_ASSIGNED_TOPIC, InMemoryEventBus

# Repositorio de datos.
from sut.repository import InMemoryRepository

# Roles autorizados para asignar pedidos.
ASSIGNER_ROLES = {"SUPERVISOR", "ADMIN"}


@dataclass(frozen=True)
class AssignmentResult:
    """
    Resultado de una operación de asignación.

    Attributes:
        assignment: datos de la asignación (lo que se devuelve en el JSON).
        created: ``True`` si se creó ahora (HTTP 201) o ``False`` si ya existía
            con el mismo operador (respuesta idempotente HTTP 200).
    """

    assignment: dict
    created: bool


class AssignmentService:
    """Servicio de asignación de pedidos a operadores (patrón *Service Layer*)."""

    def __init__(
        self,
        repository: InMemoryRepository,
        event_bus: InMemoryEventBus,
        lock_enabled: bool = True,
        simulated_latency_ms: int = 0,
    ) -> None:
        """
        Inyección de dependencias por constructor: el servicio recibe sus
        colaboradores en lugar de crearlos; así los tests pueden pasar dobles.

        Args:
            repository: acceso a datos.
            event_bus: publicador de eventos.
            lock_enabled: si es ``False`` se omite el lock (reproduce el bug de duplicados).
            simulated_latency_ms: pausa artificial entre "verificar" y "guardar".
        """
        self.repository = repository
        self.event_bus = event_bus
        self.lock_enabled = lock_enabled
        self.simulated_latency_ms = simulated_latency_ms

    def assign(
        self, actor: dict, order_id: str, operator_id: str, warehouse_id: str, priority: str
    ) -> AssignmentResult:
        """
        Asigna un pedido a un operador aplicando todas las reglas de negocio.

        Args:
            actor: claims del usuario autenticado (``sub``, ``role``, ``warehouses``).
            order_id: ID del pedido (ya validado en formato).
            operator_id: ID del operador.
            warehouse_id: ID del almacén.
            priority: ``NORMAL`` | ``URGENT`` | ``EXPRESS``.

        Returns:
            :class:`AssignmentResult` con la asignación creada o existente.

        Raises:
            DomainError: alguna de sus subclases si se viola una regla.
        """
        # Regla 1: rol autorizado.
        if actor.get("role") not in ASSIGNER_ROLES:
            raise ForbiddenError("El rol del usuario no permite asignar pedidos")
        # Regla 3a: el almacén debe existir.
        if not self.repository.warehouse_exists(warehouse_id):
            raise WarehouseNotFoundError(f"El almacén {warehouse_id} no existe")
        # Regla 2: el usuario debe tener autoridad sobre ese almacén.
        if warehouse_id not in actor.get("warehouses", []):
            raise ForbiddenError(f"El usuario no tiene permisos sobre el almacén {warehouse_id}")
        # Regla 3b + 4: operador existente, activo y del mismo almacén.
        operator = self.repository.get_operator(operator_id)
        if operator is None:
            raise OperatorNotFoundError(f"El operador {operator_id} no existe")
        if not operator["active"]:
            raise OperatorInactiveError(f"El operador {operator_id} está inactivo")
        if operator["warehouseId"] != warehouse_id:
            raise WarehouseMismatchError(f"El operador {operator_id} no pertenece al almacén {warehouse_id}")

        # Sección crítica: "leer estado + decidir + escribir" debe ser atómica.
        # Si dos supervisores asignan el mismo pedido a la vez, sólo uno gana.
        # Bloqueamos SÓLO este pedido (no toda la base): otros pedidos se asignan en paralelo.
        guard = self.repository.order_lock(order_id) if self.lock_enabled else contextlib.nullcontext()
        with guard:
            # Regla 3c: el pedido debe existir.
            order = self.repository.get_order(order_id)
            if order is None:
                raise OrderNotFoundError(f"El pedido {order_id} no existe")
            # Regla 5: el pedido debe ser del mismo almacén.
            if order["warehouseId"] != warehouse_id:
                raise WarehouseMismatchError(f"El pedido {order_id} no pertenece al almacén {warehouse_id}")
            # Reglas 7 y 8: ¿ya está asignado?
            existing = self.repository.get_assignment(order_id)
            if existing is not None:
                # Mismo operador -> idempotente: devolvemos la asignación existente.
                if existing["operatorId"] == operator_id:
                    return AssignmentResult(assignment=existing, created=False)
                # Otro operador -> conflicto.
                raise OrderAlreadyAssignedError(
                    f"El pedido {order_id} ya está asignado al operador {existing['operatorId']}"
                )
            # Regla 6: sólo pedidos con stock reservado.
            if order["status"] != "READY_FOR_ASSIGNMENT":
                raise OrderNotAssignableError(
                    f"El pedido {order_id} está en estado {order['status']} y no puede asignarse"
                )
            # Latencia artificial: simula el tiempo de una consulta a Cloud SQL.
            # Sin lock, en esta ventana otro hilo puede pasar las mismas validaciones.
            if self.simulated_latency_ms:
                time.sleep(self.simulated_latency_ms / 1000)
            # Construimos la asignación con el formato del contrato (respuesta 201).
            assignment = {
                "assignmentId": self.repository.next_assignment_id(),
                "orderId": order_id,
                "operatorId": operator_id,
                "warehouseId": warehouse_id,
                "priority": priority,
                "status": "ASSIGNED",
                "assignedBy": actor["sub"],
                "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
            self.repository.save_assignment(assignment)

        # Regla 9: publicamos el evento FUERA del lock (no bloqueamos por E/S).
        self.event_bus.publish(
            ORDER_ASSIGNED_TOPIC,
            data={
                "eventType": "order.assigned",
                "eventVersion": "1.0",
                "assignmentId": assignment["assignmentId"],
                "orderId": order_id,
                "operatorId": operator_id,
                "warehouseId": warehouse_id,
                "priority": priority,
                "occurredAt": assignment["timestamp"],
            },
            attributes={"eventType": "order.assigned", "eventVersion": "1.0", "priority": priority},
        )
        return AssignmentResult(assignment=assignment, created=True)
