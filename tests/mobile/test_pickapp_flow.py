"""
PARTE 4 - EJERCICIO C: suite mobile de PickApp (Flutter) con Appium.

Flujo: Login -> Lista de Pedidos -> Seleccionar Pedido -> Detalle de Productos
       -> Escanear Producto -> Confirmar Preparación -> Generar Guía de Envío

Datos de la app demo (mobile-app/lib/data.dart):
    Usuario OP-312 / Pick2025!
    ORD-2025-007841 (domicilio): códigos 7501234567890 y 7501234567891
    ORD-2025-007842 (tienda):    código 7501234567892
"""

import pytest

from framework.mobile.screens.pickapp_screens import LoginScreen

pytestmark = [pytest.mark.mobile, pytest.mark.regression]

OPERATOR = "OP-312"
PASSWORD = "Pick2025!"


@pytest.mark.smoke
@pytest.mark.critical
def test_happy_path_preparation_generates_shipping_guide(driver):
    """Happy path completo: login -> preparación -> guía generada."""
    # Login (C.3: acción de login en la app mobile).
    orders = LoginScreen(driver).login(OPERATOR, PASSWORD)
    assert orders.is_loaded()
    # Seleccionar pedido y ver sus productos.
    detail = orders.open_order("ORD-2025-007841")
    detail.wait_for_progress("0/2")
    # Escanear cada producto (scanner simulado) y verificar el avance.
    detail.scan("7501234567890")
    detail.wait_for_progress("1/2")
    detail.scan("7501234567891")
    detail.wait_for_progress("2/2")
    # Confirmar y verificar la guía generada.
    result = detail.confirm()
    assert "Guía Generada" in result.status()
    assert "GUIA-2025-007841" in result.guide_number()


def test_store_pickup_ends_ready_for_pickup(driver):
    """Recogida en tienda: termina en 'Listo para recoger'."""
    detail = LoginScreen(driver).login(OPERATOR, PASSWORD).open_order("ORD-2025-007842")
    detail.scan("7501234567892")
    detail.wait_for_progress("1/1")
    assert "Listo para recoger" in detail.confirm().status()


def test_reject_order_when_product_unavailable(driver):
    """Rechazo: el pedido queda 'Pendiente de resurtido'."""
    detail = LoginScreen(driver).login(OPERATOR, PASSWORD).open_order("ORD-2025-007841")
    assert "Pendiente de resurtido" in detail.reject().status()


def test_scanning_product_not_in_order_shows_error(driver):
    """Scanner lee un código que no pertenece al pedido -> error y el avance no cambia."""
    detail = LoginScreen(driver).login(OPERATOR, PASSWORD).open_order("ORD-2025-007841")
    detail.scan("0000000000000")
    assert "no pertenece al pedido" in detail.scan_error()
    detail.wait_for_progress("0/2")


def test_invalid_credentials_show_error(driver):
    """Credenciales inválidas -> mensaje de error y no se avanza."""
    message = LoginScreen(driver).login_expecting_error(OPERATOR, "incorrecta")
    assert "Credenciales inválidas" in message
