"""
PRUEBAS DE INTEGRACIÓN de ``orders-api``.

Nivel: Integration Tests.
    - Prueban que VARIAS piezas funcionan JUNTAS: rutas HTTP + seguridad +
      lógica de negocio + repositorio + publicación en Pub/Sub.
    - Usan ``TestClient`` de FastAPI: la app corre DENTRO del proceso de pytest
      (sin abrir puertos), por eso son rápidas y miden cobertura de código.
    - En un proyecto real se usaría el emulador de Pub/Sub y un PostgreSQL en
      Docker (Testcontainers); aquí el bus y el repositorio en memoria cumplen ese rol.
"""

import pytest

# TestClient: cliente HTTP que llama a la app FastAPI sin red.
from fastapi.testclient import TestClient

from framework.api.payloads import assign_payload
from sut.config import Settings
from sut.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def app():
    """App nueva por prueba (datos limpios), sin latencia artificial."""
    return create_app(Settings(simulated_latency_ms=0))


@pytest.fixture
def client(app):
    """Cliente HTTP en memoria para la app."""
    # raise_server_exceptions=False: si hay un error 500 queremos VER la respuesta,
    # no que la excepción se propague a la prueba.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _login(client, username="supervisor1", password="Sup3rvisor!2025") -> dict:
    """Helper: hace login y devuelve el header Authorization listo para usar."""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.mark.critical
def test_assignment_is_persisted_and_published_to_pubsub(client, app):
    """
    Integración orders-api -> Pub/Sub:
    al asignar, el pedido cambia a ASSIGNED y se publica el evento que
    consumirán inventory-service y notifications-service.
    """
    headers = _login(client)
    response = client.post("/api/v1/orders/assign", json=assign_payload(priority="URGENT"), headers=headers)
    assert response.status_code == 201
    # Verificamos el "lado asíncrono": el mensaje en el topic.
    messages = app.state.event_bus.messages("order-assigned")
    assert len(messages) == 1
    assert messages[0]["data"]["orderId"] == "ORD-2025-007841"
    assert messages[0]["attributes"]["priority"] == "URGENT"


def test_dashboard_listing_reflects_assignment(client):
    """
    Integración API de escritura <-> API de lectura del dashboard.
    Cubre el problema: 'los dashboards no reflejan el estado en tiempo real'.
    """
    headers = _login(client)
    client.post("/api/v1/orders/assign", json=assign_payload(), headers=headers)
    orders = client.get("/api/v1/orders", headers=headers).json()["items"]
    order = next(o for o in orders if o["orderId"] == "ORD-2025-007841")
    assert order["status"] == "ASSIGNED"
    assert order["operatorId"] == "OP-312"


def test_operator_only_sees_own_warehouse_orders(client):
    """El listado se filtra por los almacenes del usuario."""
    headers = _login(client, "operator1", "0perator!2025")
    orders = client.get("/api/v1/orders", headers=headers).json()["items"]
    assert orders and all(o["warehouseId"] == "WH-05" for o in orders)


def test_test_support_endpoints_are_disabled_in_production():
    """Con ENABLE_TEST_SUPPORT=false (producción) los endpoints de soporte NO existen."""
    prod_app = create_app(Settings(enable_test_support=False))
    with TestClient(prod_app) as prod_client:
        assert prod_client.post("/api/v1/test-support/reset").status_code == 404


def test_unexpected_error_returns_generic_500_without_stack_trace(client, app, monkeypatch):
    """Un fallo inesperado (ej. caída de Cloud SQL) responde 500 genérico, sin detalles internos."""
    def broken_get_order(order_id):
        raise RuntimeError("connection to Cloud SQL lost at 10.0.0.5")
    # monkeypatch reemplaza temporalmente un método (sólo durante esta prueba).
    monkeypatch.setattr(app.state.repository, "get_order", broken_get_order)
    response = client.post("/api/v1/orders/assign", json=assign_payload(), headers=_login(client))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "10.0.0.5" not in response.text and "Traceback" not in response.text


def test_request_id_is_propagated_for_log_correlation(client):
    """El X-Request-ID enviado vuelve en la respuesta: permite seguir una petición entre servicios."""
    response = client.get("/health", headers={"X-Request-ID": "trace-me-123"})
    assert response.headers["X-Request-ID"] == "trace-me-123"


def test_web_pages_are_served(client):
    """La raíz redirige al login y las páginas del Centro de Control responden."""
    assert client.get("/", follow_redirects=False).headers["location"] == "/control/login"
    for path in ("/control/login", "/control/dashboard", "/control/forgot-password"):
        assert client.get(path).status_code == 200


def test_test_support_helpers(client):
    """Los helpers de datos de prueba crean pedidos, emiten tokens y resetean."""
    created = client.post("/api/v1/test-support/orders", json={"count": 2}).json()["orderIds"]
    assert len(created) == 2
    token = client.post("/api/v1/test-support/tokens", json={"username": "supervisor1"}).json()["accessToken"]
    assert client.get("/api/v1/orders", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post("/api/v1/test-support/tokens", json={"username": "nadie"}).status_code == 401
    assert client.get("/api/v1/test-support/events").json() == {"messages": []}
    assert client.post("/api/v1/test-support/reset").json() == {"status": "reset"}
