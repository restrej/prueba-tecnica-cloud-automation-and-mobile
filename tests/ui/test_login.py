"""
PARTE 4 - EJERCICIO B: suite de UI de la pantalla de Login del Centro de Control.

Herramienta: Playwright (Python) + pytest-playwright.
    - La fixture ``page`` (de pytest-playwright) entrega una pestaña de navegador nueva
      y aislada por prueba (cookies/sessionStorage limpios).
    - ``expect(...)`` reintenta automáticamente hasta 5 s: no se usan ``sleep``.
Patrón: Page Object Model (``framework/ui/pages``).

Ejecutar viendo el navegador:   pytest tests/ui --headed --slowmo 500
"""

# re: expresiones regulares para validar URLs sin depender del host/puerto.
import re

import pytest
from playwright.sync_api import Page, expect

from framework import config
from framework.ui.pages.dashboard_page import DashboardPage
from framework.ui.pages.login_page import LoginPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """Abre la pantalla de login y devuelve su Page Object."""
    return LoginPage(page).open()


# =============================================================================
# Happy path
# =============================================================================
@pytest.mark.smoke
@pytest.mark.critical
def test_successful_login_shows_landing_page(login_page: LoginPage, page: Page):
    """
    Login exitoso y verificación de la landing page.

    Pasos:
        1. Abrir /control/login (fixture).
        2. Ingresar usuario y contraseña válidos.
        3. Presionar "Entrar".
        4. Verificar URL del panel, título, bienvenida con el nombre y tabla con pedidos.
    """
    login_page.login(config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD)
    DashboardPage(page).should_be_loaded_for("Laura Gómez")


def test_login_with_enter_key(login_page: LoginPage, page: Page):
    """El formulario también se envía con la tecla Enter (uso real de los supervisores)."""
    login_page.fill_credentials(config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD)
    login_page.password_input.press("Enter")
    expect(page).to_have_url(re.compile(r".*/control/dashboard$"))


def test_logout_returns_to_login(login_page: LoginPage, page: Page):
    """Cerrar sesión vuelve al login y borra la sesión."""
    login_page.login(config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD)
    DashboardPage(page).logout_button.click()
    expect(page).to_have_url(re.compile(r".*/control/login$"))


# =============================================================================
# Credenciales inválidas
# =============================================================================
@pytest.mark.critical
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("usuario.incorrecto", config.SUPERVISOR_PASSWORD),
        (config.SUPERVISOR_USER, "ContraseñaIncorrecta1"),
        ("usuario.incorrecto", "ContraseñaIncorrecta1"),
    ],
    ids=["usuario-incorrecto", "contrasena-incorrecta", "ambos-incorrectos"],
)
def test_invalid_credentials_show_generic_error(login_page: LoginPage, page: Page, username, password):
    """Credenciales inválidas -> mensaje genérico, se queda en el login, sin token guardado."""
    login_page.login(username, password)
    expect(login_page.login_error).to_have_text("Usuario o contraseña incorrectos")
    expect(page).to_have_url(re.compile(r".*/control/login$"))
    assert page.evaluate("sessionStorage.getItem('token')") is None


# =============================================================================
# Validaciones de campos
# =============================================================================
@pytest.mark.parametrize(
    ("username", "password", "expect_user_error", "expect_password_error"),
    [
        ("", "", True, True),
        ("", "algo", True, False),
        ("supervisor1", "", False, True),
        ("   ", "algo", True, False),            # sólo espacios = vacío
    ],
    ids=["ambos-vacios", "usuario-vacio", "contrasena-vacia", "solo-espacios"],
)
def test_required_fields_validation(login_page: LoginPage, username, password, expect_user_error,
                                    expect_password_error):
    """Campos vacíos -> mensajes de obligatoriedad y NO se llama a la API."""
    login_page.login(username, password)
    if expect_user_error:
        expect(login_page.username_error).to_have_text("El usuario es obligatorio")
    else:
        expect(login_page.username_error).to_be_hidden()
    if expect_password_error:
        expect(login_page.password_error).to_have_text("La contraseña es obligatoria")
    else:
        expect(login_page.password_error).to_be_hidden()


@pytest.mark.parametrize("username", ["<script>alert(1)</script>", "admin' OR '1'='1", "usuario con espacio",
                                      "ñandú#$%"])
def test_special_characters_in_username_are_rejected(login_page: LoginPage, username):
    """Caracteres especiales no permitidos en el usuario -> mensaje de validación."""
    login_page.login(username, "cualquiera")
    expect(login_page.username_error).to_have_text("El usuario contiene caracteres no permitidos")


def test_username_and_password_max_length(login_page: LoginPage):
    """Longitud máxima: el campo usuario acepta 50 caracteres y la contraseña 64 (el resto se corta)."""
    login_page.username_input.fill("a" * 80)
    login_page.password_input.fill("b" * 100)
    expect(login_page.username_input).to_have_value("a" * 50)
    expect(login_page.password_input).to_have_value("b" * 64)


def test_password_is_masked(login_page: LoginPage):
    """La contraseña no se muestra en texto plano."""
    expect(login_page.password_input).to_have_attribute("type", "password")


def test_forgot_password_link_navigates(login_page: LoginPage, page: Page):
    """El enlace '¿Olvidaste tu contraseña?' lleva a la página de recuperación."""
    login_page.forgot_password_link.click()
    expect(page.get_by_test_id("forgot-title")).to_have_text("Recuperar contraseña")


def test_dashboard_requires_session(page: Page):
    """Entrar directo al panel sin sesión redirige al login (control de acceso en UI)."""
    page.goto("/control/dashboard")
    expect(page).to_have_url(re.compile(r".*/control/login$"))
