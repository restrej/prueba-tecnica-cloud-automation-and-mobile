"""
PARTE 4 - EJERCICIO A: casos POSITIVOS de ``POST /api/v1/orders/assign``.

Estas pruebas hablan con el servicio REAL por HTTP (servidor levantado por
conftest.py o el indicado en BASE_URL), igual que lo haría PickApp.

Patrón aplicado: API Object (``LogiTrackApi``) + Test Data Builder (``assign_payload``)
+ datos aislados (cada prueba crea su propio pedido con ``create_test_order``).
"""

import pytest

from framework.api.payloads import assign_payload

# Todas las pruebas del archivo son de API y de regresión.
pytestmark = [pytest.mark.api, pytest.mark.regression]


@pytest.mark.smoke
@pytest.mark.critical
@pytest.mark.parametrize("priority", ["NORMAL", "URGENT", "EXPRESS"])
def test_assign_order_successfully_with_each_priority(api, priority):
    """
    Asignación exitosa con cada prioridad -> 201 Created y cuerpo correcto.

    Pasos:
        1. Crear un pedido nuevo listo para asignar (dato propio de la prueba).
        2. Asignarlo al operador OP-312 con la prioridad parametrizada.
        3. Validar código, campos y formato de la respuesta.
    """
    # 1. Arrange: pedido nuevo para esta prueba.
    order_id = api.create_test_order()
    # 2. Act: llamada al endpoint.
    response = api.assign_order(assign_payload(orderId=order_id, priority=priority))
    # 3. Assert: código HTTP.
    assert response.status_code == 201, response.text
    body = response.json()
    # Assert: el cuerpo refleja la petición.
    assert body["orderId"] == order_id
    assert body["operatorId"] == "OP-312"
    assert body["status"] == "ASSIGNED"
    assert body["priority"] == priority
    # Assert: formato de los campos generados por el servidor.
    assert body["assignmentId"].startswith("ASG-")
    assert body["timestamp"].endswith("Z")
    # Assert de "efecto lateral": el servicio publicó el evento en Pub/Sub.
    events = [e for e in api.published_events() if e["data"]["orderId"] == order_id]
    assert len(events) == 1 and events[0]["data"]["priority"] == priority


def test_repeating_same_assignment_is_idempotent(api):
    """Si PickApp reintenta (p. ej. por mala red) la misma asignación, no se duplica: 200 + mismo ID."""
    order_id = api.create_test_order()
    first = api.assign_order(assign_payload(orderId=order_id))
    second = api.assign_order(assign_payload(orderId=order_id))
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["assignmentId"] == first.json()["assignmentId"]


def test_admin_can_also_assign(anonymous_api):
    """El rol ADMIN también tiene permiso de asignar."""
    anonymous_api.login("admin", "Adm1n!2025")
    order_id = anonymous_api.create_test_order()
    assert anonymous_api.assign_order(assign_payload(orderId=order_id)).status_code == 201
