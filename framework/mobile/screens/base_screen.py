"""
Clase base de todos los Screen Objects.

Centraliza la SINCRONIZACIÓN: en vez de ``time.sleep(5)`` (lento y frágil),
usamos ESPERAS EXPLÍCITAS: "espera HASTA que el elemento sea visible, máximo N
segundos". Si aparece en 0,3 s, seguimos en 0,3 s; si no aparece, falla con un
mensaje claro.
"""

import os

# WebDriverWait + expected_conditions: esperas explícitas de Selenium (Appium las hereda).
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from framework.mobile.locators import FOCUSED_INPUT_ANDROID, editable_child_android, flutter_id

# Tiempo máximo de espera por elemento (configurable para dispositivos lentos / granjas en la nube).
DEFAULT_TIMEOUT = int(os.getenv("MOBILE_WAIT_TIMEOUT", "15"))


class BaseScreen:
    """Operaciones comunes a todas las pantallas."""

    def __init__(self, driver) -> None:
        """
        Args:
            driver: sesión activa de Appium (``appium.webdriver.Remote``).
        """
        self.driver = driver
        # Una espera reutilizable; poll_frequency = cada cuánto vuelve a mirar.
        self.wait = WebDriverWait(driver, DEFAULT_TIMEOUT, poll_frequency=0.3)

    def element(self, identifier: str):
        """Espera a que el elemento con ese Semantics identifier sea VISIBLE y lo devuelve."""
        return self.wait.until(EC.visibility_of_element_located(flutter_id(identifier)))

    def tap(self, identifier: str) -> None:
        """Espera a que el elemento sea CLICKEABLE (visible + habilitado) y lo toca."""
        self.wait.until(EC.element_to_be_clickable(flutter_id(identifier))).click()

    def focus_input(self, identifier: str):
        """
        Toca un campo de texto y devuelve el elemento EDITABLE que quedó con el foco.

        En Flutter, el identificador (Semantics) puede quedar en un contenedor y no
        en la caja de texto real. Por eso, después de tocarlo, buscamos en Android
        "el elemento que tiene el foco", que siempre es la caja donde se escribe.
        """
        field = self.element(identifier)
        field.click()
        if self.driver.capabilities.get("platformName", "").lower() != "android":
            return field
        # 1) La caja de texto que quedó con el foco después del toque.
        # 2) Si no aparece, la caja de texto que está dentro del contenedor.
        for locator in (FOCUSED_INPUT_ANDROID, editable_child_android(identifier)):
            try:
                return WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(locator))
            except TimeoutException:  # no apareció: probamos la siguiente opción
                continue
        return field

    def type_text(self, identifier: str, text: str) -> None:
        """Toca un campo de texto, lo limpia y escribe."""
        target = self.focus_input(identifier)
        target.clear()
        target.send_keys(text)

    def save_evidence(self, name: str) -> None:
        """Guarda una captura de pantalla en reports/mobile/ (evidencia de la ejecución)."""
        os.makedirs("reports/mobile", exist_ok=True)
        self.driver.save_screenshot(f"reports/mobile/{name}.png")

    def text_of(self, identifier: str) -> str:
        """Devuelve el texto visible de un elemento."""
        element = self.element(identifier)
        # En Flutter el texto puede venir en "text" o en la descripción de accesibilidad.
        return element.text or element.get_attribute("content-desc") or ""

    def is_present(self, identifier: str, timeout: float = 2) -> bool:
        """Indica si el elemento aparece dentro de ``timeout`` segundos (sin fallar)."""
        try:
            WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located(flutter_id(identifier)))
            return True
        except Exception:  # noqa: BLE001 (TimeoutException u otros: "no está")
            return False

    def hide_keyboard(self) -> None:
        """Oculta el teclado si está abierto (puede tapar botones en pantallas pequeñas)."""
        try:
            self.driver.hide_keyboard()
        # Si no había teclado abierto, Appium lanza un error que podemos ignorar.
        except Exception:  # noqa: BLE001,S110  # nosec B110
            pass
