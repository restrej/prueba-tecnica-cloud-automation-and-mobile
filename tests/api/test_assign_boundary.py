"""
PARTE 4 - EJERCICIO A: casos LÍMITE (boundary) de ``POST /api/v1/orders/assign``.

Los casos límite prueban los "bordes" de lo permitido: campos vacíos,
formatos casi correctos, longitudes máximas, campos faltantes y estados
de negocio en conflicto (pedido ya asignado a otro operador).
"""

import pytest

from framework.api.payloads import assign_payload

pytestmark = [pytest.mark.api, pytest.mark.regression]


@pytest.mark.parametrize("field", ["orderId", "operatorId", "warehouseId", "priority"])
def test_empty_field_returns_400(api, field):
    """Cada campo vacío ("") -> 400 VALIDATION_ERROR indicando el campo."""
    response = api.assign_order(assign_payload(**{field: ""}))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == field for detail in body["error"]["details"])


@pytest.mark.parametrize("field", ["orderId", "operatorId", "warehouseId", "priority"])
def test_missing_field_returns_400(api, field):
    """Cada campo AUSENTE del JSON -> 400 (``None`` en el builder elimina el campo)."""
    response = api.assign_order(assign_payload(**{field: None}))
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("orderId", "ORD-25-7841"),          # año con 2 dígitos
        ("orderId", "ord-2025-007841"),      # minúsculas
        ("orderId", "ORD-2025-0078410"),     # 7 dígitos (uno de más)
        ("orderId", " ORD-2025-007841"),     # espacio al inicio
        ("operatorId", "OP312"),             # sin guion
        ("operatorId", "OP-1234567"),        # 7 dígitos (excede máximo)
        ("warehouseId", "WH-5"),             # 1 dígito
        ("priority", "normal"),              # enum en minúsculas
        ("priority", "LOW"),                 # valor fuera del enum
        ("orderId", 7841),                   # tipo numérico en lugar de texto
    ],
)
def test_invalid_id_formats_return_400(api, field, value):
    """IDs con formato inválido -> 400 (nunca 500 ni 201)."""
    response = api.assign_order(assign_payload(**{field: value}))
    assert response.status_code == 400


@pytest.mark.parametrize("operator_id", ["OP-1", "OP-999999"], ids=["min-1-digito", "max-6-digitos"])
def test_operator_id_length_limits_pass_validation(api, operator_id):
    """
    Valores EN el límite (1 y 6 dígitos) pasan la validación de formato.
    Como esos operadores no existen, la respuesta es 404 (y no 400): prueba
    que el borde se acepta sintácticamente.
    """
    response = api.assign_order(assign_payload(orderId=api.create_test_order(), operatorId=operator_id))
    assert response.status_code == 404


@pytest.mark.critical
def test_order_already_assigned_to_other_operator_returns_409(api):
    """Pedido ya asignado a OP-312 y se intenta asignar a OP-313 -> 409 sin cambiar el dueño."""
    order_id = api.create_test_order()
    assert api.assign_order(assign_payload(orderId=order_id, operatorId="OP-312")).status_code == 201
    response = api.assign_order(assign_payload(orderId=order_id, operatorId="OP-313"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ALREADY_ASSIGNED"
    # El pedido sigue asignado al primer operador.
    order = next(o for o in api.list_orders().json()["items"] if o["orderId"] == order_id)
    assert order["operatorId"] == "OP-312"


def test_empty_body_returns_400(api):
    """Cuerpo JSON vacío ``{}`` -> 400 con un detalle por cada campo faltante."""
    response = api.assign_order({})
    assert response.status_code == 400
    assert len(response.json()["error"]["details"]) == 4
