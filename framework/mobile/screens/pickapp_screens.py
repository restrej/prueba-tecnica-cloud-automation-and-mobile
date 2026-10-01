"""
Screen Objects del flujo principal de PickApp:

    LoginScreen -> OrdersScreen -> OrderDetailScreen -> ResultScreen

Cada acción que lleva a otra pantalla DEVUELVE el Screen Object de destino
(patrón "fluent"), así la prueba se lee como el flujo de negocio:

    LoginScreen(driver).login("OP-312", "Pick2025!").open_order("ORD-...").scan(...)
"""

from framework.mobile.barcode import BarcodeScannerSimulator
from framework.mobile.screens.base_screen import BaseScreen


class LoginScreen(BaseScreen):
    """Pantalla de inicio de sesión."""

    def login(self, username: str, password: str) -> "OrdersScreen":
        """
        Inicia sesión y devuelve la lista de pedidos.

        Args:
            username: usuario del operador (ej. ``OP-312``).
            password: contraseña.
        """
        self.type_text("login-username", username)
        self.type_text("login-password", password)
        self.hide_keyboard()
        self.tap("login-button")
        return OrdersScreen(self.driver)

    def login_expecting_error(self, username: str, password: str) -> str:
        """Intenta iniciar sesión con datos inválidos y devuelve el mensaje de error."""
        self.type_text("login-username", username)
        self.type_text("login-password", password)
        self.hide_keyboard()
        self.tap("login-button")
        return self.text_of("login-error")


class OrdersScreen(BaseScreen):
    """Lista de pedidos asignados."""

    def is_loaded(self) -> bool:
        """``True`` si se ve el título de la lista."""
        return self.is_present("orders-title", timeout=10)

    def open_order(self, order_id: str) -> "OrderDetailScreen":
        """Abre el detalle de un pedido de la lista."""
        self.tap(f"order-{order_id}")
        return OrderDetailScreen(self.driver)


class OrderDetailScreen(BaseScreen):
    """Detalle del pedido: productos, escaneo y confirmación."""

    def __init__(self, driver, scanner_strategy: str = "type") -> None:
        """
        Args:
            driver: sesión de Appium.
            scanner_strategy: estrategia del simulador de scanner (``type`` o ``adb``).
        """
        super().__init__(driver)
        self.scanner = BarcodeScannerSimulator(driver, scanner_strategy)

    def scan(self, barcode: str) -> "OrderDetailScreen":
        """Simula la lectura de un código de barras."""
        self.scanner.scan(self.element("scan-input"), barcode)
        return self

    def progress(self) -> str:
        """Texto de avance, ej. ``Escaneados: 1/2``."""
        return self.text_of("scan-progress")

    def wait_for_progress(self, expected: str) -> None:
        """Espera (sin sleep) a que el avance muestre el texto esperado."""
        self.wait.until(lambda _: expected in self.progress(), message=f"Avance distinto de '{expected}'")

    def scan_error(self) -> str:
        """Mensaje de error del escaneo."""
        return self.text_of("scan-error")

    def confirm(self) -> "ResultScreen":
        """Confirma la preparación (el botón sólo se habilita con todo escaneado)."""
        self.hide_keyboard()
        self.tap("confirm-button")
        return ResultScreen(self.driver)

    def reject(self) -> "ResultScreen":
        """Rechaza el pedido por producto no disponible."""
        self.hide_keyboard()
        self.tap("reject-button")
        return ResultScreen(self.driver)


class ResultScreen(BaseScreen):
    """Estado final del pedido."""

    def status(self) -> str:
        """Estado final: ``Guía Generada`` / ``Listo para recoger`` / ``Pendiente de resurtido``."""
        return self.text_of("order-status")

    def guide_number(self) -> str:
        """Número de guía (sólo envío a domicilio)."""
        return self.text_of("guide-number")
