"""Page Object del panel principal (landing page después del login)."""

# re: expresiones regulares (validar la URL sin depender del host/puerto).
import re

# Page = pestaña del navegador; expect = aserciones con espera automática.
from playwright.sync_api import Page, expect


class DashboardPage:
    """Representa la pantalla ``/control/dashboard``."""

    PATH = "/control/dashboard"

    def __init__(self, page: Page) -> None:
        """
        Args:
            page: pestaña del navegador.
        """
        self.page = page
        self.title = page.get_by_test_id("dashboard-title")
        self.welcome_message = page.get_by_test_id("welcome-message")
        self.orders_table = page.get_by_test_id("orders-table")
        self.logout_button = page.get_by_test_id("logout-button")

    def should_be_loaded_for(self, user_name: str) -> None:
        """
        Verifica que la landing page cargó correctamente para un usuario.

        ``expect`` reintenta la verificación hasta 5 s (por defecto), así que
        tolera la navegación y la carga de datos sin esperas fijas.

        Args:
            user_name: nombre completo que debe aparecer en la bienvenida.
        """
        expect(self.page).to_have_url(re.compile(f".*{self.PATH}$"))
        expect(self.title).to_have_text("Panel de pedidos")
        expect(self.welcome_message).to_have_text(f"Bienvenido, {user_name}")
        # Al menos una fila de pedidos cargada desde la API.
        expect(self.orders_table.locator("tbody tr").first).to_be_visible()
