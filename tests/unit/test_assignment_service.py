"""
PRUEBAS UNITARIAS de la lógica de asignación (``sut/service.py``).

Nivel: Unit Tests (base de la pirámide de pruebas).
    - Prueban UNA unidad de código aislada (la clase AssignmentService).
    - No usan red, ni servidor, ni base de datos real -> corren en milisegundos.
    - Se ejecutan en CADA Pull Request.

Estructura de cada test: patrón AAA
    Arrange (preparar) -> Act (ejecutar) -> Assert (verificar).
"""

import pytest

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
from sut.events import InMemoryEventBus
from sut.repository import InMemoryRepository
from sut.service import AssignmentService

# Todas las pruebas de este archivo llevan el marker "unit".
pytestmark = pytest.mark.unit

# "Actor" = usuario autenticado que ejecuta la acción (como vendría en el token).
SUPERVISOR = {"sub": "supervisor1", "role": "SUPERVISOR", "warehouses": ["WH-01", "WH-05"]}


@pytest.fixture
def bus() -> InMemoryEventBus:
    """Pub/Sub simulado, vacío, nuevo para cada prueba."""
    return InMemoryEventBus()


@pytest.fixture
def service(bus) -> AssignmentService:
    """Servicio con repositorio en memoria recién creado (datos semilla limpios)."""
    return AssignmentService(InMemoryRepository(), bus)


def test_assign_ready_order_creates_assignment_and_publishes_event(service, bus):
    """Camino feliz: un pedido listo se asigna y se publica UN evento order.assigned."""
    # Act
    result = service.assign(SUPERVISOR, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")
    # Assert: asignación creada con los datos correctos.
    assert result.created is True
    assert result.assignment["status"] == "ASSIGNED"
    assert result.assignment["operatorId"] == "OP-312"
    assert result.assignment["assignmentId"].startswith("ASG-")
    # Assert: exactamente un evento publicado con el orderId correcto.
    events = bus.messages("order-assigned")
    assert len(events) == 1
    assert events[0]["data"]["orderId"] == "ORD-2025-007841"


def test_assign_same_operator_twice_is_idempotent(service, bus):
    """Reintentar la MISMA asignación no duplica ni publica un segundo evento."""
    first = service.assign(SUPERVISOR, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")
    second = service.assign(SUPERVISOR, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")
    assert second.created is False
    assert second.assignment["assignmentId"] == first.assignment["assignmentId"]
    assert len(bus.messages()) == 1


def test_assign_order_already_assigned_to_other_operator_raises_conflict(service):
    """Previene el problema real: 'asignaciones duplicadas de pedidos a operadores'."""
    service.assign(SUPERVISOR, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")
    # pytest.raises verifica que se lance la excepción esperada.
    with pytest.raises(OrderAlreadyAssignedError):
        service.assign(SUPERVISOR, "ORD-2025-007841", "OP-313", "WH-05", "NORMAL")


# parametrize = la MISMA prueba se ejecuta una vez por cada valor de la lista.
@pytest.mark.parametrize("order_id", ["ORD-2025-007900", "ORD-2025-007901"], ids=["sin-stock", "cancelado"])
def test_assign_order_without_stock_or_cancelled_is_rejected(service, order_id):
    """Previene el problema real: 'se procesan pedidos sin inventario'."""
    with pytest.raises(OrderNotAssignableError):
        service.assign(SUPERVISOR, order_id, "OP-312", "WH-05", "NORMAL")


def test_operator_role_cannot_assign(service):
    """Un usuario con rol OPERATOR no puede asignar pedidos."""
    operator = {"sub": "operator1", "role": "OPERATOR", "warehouses": ["WH-05"]}
    with pytest.raises(ForbiddenError):
        service.assign(operator, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")


def test_supervisor_cannot_assign_outside_own_warehouses(service):
    """Un supervisor de WH-01 no puede operar WH-05 (escalamiento horizontal)."""
    wh01_supervisor = {"sub": "supervisor.wh01", "role": "SUPERVISOR", "warehouses": ["WH-01"]}
    with pytest.raises(ForbiddenError):
        service.assign(wh01_supervisor, "ORD-2025-007841", "OP-312", "WH-05", "NORMAL")


# Tabla de casos negativos: (descripción, argumentos, excepción esperada).
@pytest.mark.parametrize(
    ("order_id", "operator_id", "warehouse_id", "expected_error"),
    [
        ("ORD-2025-999999", "OP-312", "WH-05", OrderNotFoundError),
        ("ORD-2025-007841", "OP-404", "WH-05", OperatorNotFoundError),
        ("ORD-2025-007841", "OP-999", "WH-05", OperatorInactiveError),
        ("ORD-2025-007841", "OP-312", "WH-09", WarehouseNotFoundError),
        ("ORD-2025-007841", "OP-100", "WH-01", WarehouseMismatchError),  # pedido es de WH-05
        ("ORD-2025-001001", "OP-312", "WH-05", WarehouseMismatchError),  # pedido es de WH-01
    ],
    ids=["pedido-inexistente", "operador-inexistente", "operador-inactivo",
         "almacen-inexistente", "pedido-de-otro-almacen", "pedido-WH01-en-WH05"],
)
def test_business_rule_violations(service, order_id, operator_id, warehouse_id, expected_error):
    """Cada regla de negocio violada lanza su error de dominio específico."""
    with pytest.raises(expected_error):
        service.assign(SUPERVISOR, order_id, operator_id, warehouse_id, "NORMAL")
