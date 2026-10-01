"""
PRUEBAS DE CONTRATO.

Nivel: Contract Tests.
Un "contrato" es el acuerdo de formato entre quien PROVEE un dato (orders-api)
y quien lo CONSUME (PickApp, Centro de Control, inventory-service...).
Si orders-api cambia un campo (lo renombra, lo quita, cambia su tipo), estas
pruebas fallan en el Pull Request ANTES de romper a los consumidores en producción.

Los contratos están en la carpeta ``contracts/`` como JSON Schema.
En la Parte Bonus (B.2) se explica cómo escalar esto con Pact (contratos
dirigidos por el consumidor).
"""

# json: leer los archivos de esquema; Path: ubicarlos.
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# validate: compara un JSON contra un JSON Schema; lanza ValidationError si no cumple.
from jsonschema import validate

from framework.api.payloads import assign_payload
from sut.config import Settings
from sut.main import create_app

pytestmark = pytest.mark.contract

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _schema(name: str) -> dict:
    """Carga un JSON Schema de la carpeta contracts/."""
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def app():
    """App nueva por prueba."""
    return create_app(Settings(simulated_latency_ms=0))


@pytest.fixture
def auth_client(app):
    """Cliente en memoria ya autenticado como supervisor."""
    with TestClient(app) as client:
        token = client.post(
            "/api/v1/auth/login", json={"username": "supervisor1", "password": "Sup3rvisor!2025"}
        ).json()["accessToken"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.mark.critical
def test_assign_response_matches_consumer_contract(auth_client):
    """Contrato PickApp/Centro de Control <-> orders-api (respuesta 201)."""
    response = auth_client.post("/api/v1/orders/assign", json=assign_payload())
    assert response.status_code == 201
    validate(instance=response.json(), schema=_schema("assign_response.schema.json"))


@pytest.mark.parametrize(
    "payload",
    [assign_payload(orderId=""), assign_payload(orderId="ORD-2025-999999")],
    ids=["400-validacion", "404-no-existe"],
)
def test_error_responses_follow_standard_error_contract(auth_client, payload):
    """Todos los errores comparten un formato único que los clientes saben interpretar."""
    response = auth_client.post("/api/v1/orders/assign", json=payload)
    assert response.status_code in (400, 404)
    validate(instance=response.json(), schema=_schema("error_response.schema.json"))


@pytest.mark.critical
def test_order_assigned_event_matches_pubsub_contract(auth_client, app):
    """Contrato orders-api -> Pub/Sub -> inventory-service / notifications-service."""
    auth_client.post("/api/v1/orders/assign", json=assign_payload(priority="EXPRESS"))
    message = app.state.event_bus.messages("order-assigned")[0]
    validate(instance=message["data"], schema=_schema("order_assigned_event.schema.json"))
    # Los atributos permiten filtrar suscripciones sin leer el cuerpo.
    assert message["attributes"]["eventVersion"].startswith("1.")


def test_openapi_spec_publishes_assign_endpoint_with_required_fields(app):
    """
    La especificación OpenAPI (documento /openapi.json) es el contrato publicado.
    Verificamos que el endpoint existe y que los 4 campos siguen siendo obligatorios.
    """
    spec = app.openapi()
    assert "/api/v1/orders/assign" in spec["paths"]
    request_schema = spec["components"]["schemas"]["AssignOrderRequest"]
    assert set(request_schema["required"]) == {"orderId", "operatorId", "warehouseId", "priority"}
