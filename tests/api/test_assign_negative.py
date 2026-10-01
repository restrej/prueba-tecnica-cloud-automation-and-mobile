"""
PARTE 4 - EJERCICIO A: casos NEGATIVOS de ``POST /api/v1/orders/assign``.

Un caso negativo verifica que el sistema RECHAZA correctamente lo que no debe
aceptar, con el código HTTP y el código de error correctos.
"""

import pytest

from framework.api.payloads import assign_payload

pytestmark = [pytest.mark.api, pytest.mark.regression]


@pytest.mark.critical
@pytest.mark.parametrize(
    "token",
    ["", "token-invalido", "a.b.c", "eyJhbGciOiJIUzI1NiJ9.e30.firmaFalsa"],
    ids=["vacio", "texto-libre", "jwt-basura", "firma-falsa"],
)
def test_invalid_token_is_rejected_with_401(anonymous_api, token):
    """Token inválido o ausente -> 401 + header WWW-Authenticate."""
    order_id = anonymous_api.create_test_order()
    # Pasamos el token "a mano"; "" significa sin header Authorization.
    response = anonymous_api.assign_order(assign_payload(orderId=order_id), token=token)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_nonexistent_order_returns_404(api):
    """Pedido con formato válido pero que no existe -> 404 ORDER_NOT_FOUND."""
    response = api.assign_order(assign_payload(orderId="ORD-2025-999999"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_inactive_operator_returns_422(api):
    """Operador dado de baja (OP-999) -> 422 OPERATOR_INACTIVE."""
    order_id = api.create_test_order()
    response = api.assign_order(assign_payload(orderId=order_id, operatorId="OP-999"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "OPERATOR_INACTIVE"


@pytest.mark.parametrize(
    ("warehouse_id", "expected_status", "expected_code"),
    [
        ("WH-99", 404, "WAREHOUSE_NOT_FOUND"),   # formato válido, no existe
        ("BODEGA-5", 400, "VALIDATION_ERROR"),   # formato inválido
        ("WH-01", 422, "WAREHOUSE_MISMATCH"),    # existe, pero el operador/pedido no son de ahí
    ],
    ids=["no-existe", "formato-invalido", "no-corresponde"],
)
def test_invalid_warehouse_is_rejected(api, warehouse_id, expected_status, expected_code):
    """Almacén inválido -> error específico según el tipo de invalidez."""
    order_id = api.create_test_order()
    response = api.assign_order(assign_payload(orderId=order_id, warehouseId=warehouse_id))
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


def test_nonexistent_operator_returns_404(api):
    """Operador que no existe -> 404 OPERATOR_NOT_FOUND."""
    order_id = api.create_test_order()
    response = api.assign_order(assign_payload(orderId=order_id, operatorId="OP-404"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OPERATOR_NOT_FOUND"


@pytest.mark.critical
def test_order_without_stock_cannot_be_assigned(api):
    """Pedido en PENDING_RESTOCK (sin inventario) -> 409 ORDER_NOT_ASSIGNABLE."""
    order_id = api.create_test_order(status="PENDING_RESTOCK")
    response = api.assign_order(assign_payload(orderId=order_id))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_ASSIGNABLE"
