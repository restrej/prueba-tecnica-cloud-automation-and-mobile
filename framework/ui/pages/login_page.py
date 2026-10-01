"""
Page Object de la pantalla de Login del Centro de Control.

Patrón **Page Object Model (POM)**:
    - Los LOCATORS (cómo encontrar cada elemento) viven sólo aquí.
    - Las ACCIONES (escribir usuario, presionar Entrar) son métodos con nombre de negocio.
    - Las pruebas sólo dicen QUÉ hacer: ``login_page.login("user", "pass")``.

Estrategia de locators (de más estable a menos estable):
    1. ``get_by_test_id``  -> atributo ``data-testid``, pensado SOLO para pruebas.
    2. ``get_by_role``     -> rol accesible + nombre visible (robusto y valida accesibilidad).
    3. CSS simple          -> sólo si no hay alternativa.
    4. XPath / IDs autogenerados (``mat-input-0``) -> EVITAR: se rompen con cualquier cambio del DOM.
"""

# Page = pestaña del navegador; expect = aserciones con espera automática.
from playwright.sync_api import Page, expect


class LoginPage:
    """Representa la pantalla ``/control/login``."""

    # Ruta relativa de la página (se combina con base_url).
    PATH = "/control/login"

    def __init__(self, page: Page) -> None:
        """
        Guarda la página y define los locators.

        Un *locator* de Playwright es "perezoso": no busca el elemento al crearlo,
        sino cada vez que se usa, y ESPERA automáticamente a que esté listo
        (visible, habilitado). Por eso no hacen falta ``sleep``.

        Args:
            page: pestaña del navegador entregada por la fixture de pytest-playwright.
        """
        self.page = page
        # Campos y botones, todos por data-testid (locator estable).
        self.username_input = page.get_by_test_id("login-username")
        self.password_input = page.get_by_test_id("login-password")
        self.submit_button = page.get_by_test_id("login-submit")
        # Mensajes de error.
        self.username_error = page.get_by_test_id("username-error")
        self.password_error = page.get_by_test_id("password-error")
        self.login_error = page.get_by_test_id("login-error")
        # Enlace de recuperación (por rol + texto visible: también es estable).
        self.forgot_password_link = page.get_by_role("link", name="¿Olvidaste tu contraseña?")

    def open(self) -> "LoginPage":
        """Navega a la pantalla de login y verifica que cargó. Devuelve self para encadenar."""
        self.page.goto(self.PATH)
        expect(self.page.get_by_test_id("login-title")).to_be_visible()
        return self

    def fill_credentials(self, username: str, password: str) -> None:
        """Escribe usuario y contraseña (``fill`` limpia el campo antes de escribir)."""
        self.username_input.fill(username)
        self.password_input.fill(password)

    def submit(self) -> None:
        """Presiona el botón Entrar."""
        self.submit_button.click()

    def login(self, username: str, password: str) -> None:
        """Acción completa de negocio: escribir credenciales y enviar."""
        self.fill_credentials(username, password)
        self.submit()
