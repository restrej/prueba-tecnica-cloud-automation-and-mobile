"""
PRUEBAS UNITARIAS del framework mobile (no necesitan emulador).

Verifican que las capabilities y los locators se construyen bien, para detectar
errores de configuración en segundos en lugar de descubrirlos en un emulador.
"""

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from framework.mobile.barcode import BarcodeScannerSimulator
from framework.mobile.capabilities import build_options
from framework.mobile.locators import by_text, flutter_id

pytestmark = pytest.mark.unit


def test_android_capabilities_defaults(monkeypatch):
    """Por defecto se usa Android + UiAutomator2 con el paquete de PickApp."""
    monkeypatch.delenv("MOBILE_PLATFORM", raising=False)
    caps = build_options().to_capabilities()
    assert caps["platformName"] == "Android"
    assert caps["appium:automationName"] == "UiAutomator2"
    assert caps["appium:appPackage"] == "com.logitrack.pickapp"
    assert caps["appium:autoGrantPermissions"] is True


def test_device_can_be_changed_by_environment(monkeypatch):
    """La matriz de dispositivos se controla con variables de entorno."""
    monkeypatch.setenv("ANDROID_DEVICE_NAME", "Pixel_Tablet_API_34")
    monkeypatch.setenv("ANDROID_PLATFORM_VERSION", "14")
    caps = build_options().to_capabilities()
    assert caps["appium:deviceName"] == "Pixel_Tablet_API_34"
    assert caps["appium:platformVersion"] == "14"


def test_ios_capabilities(monkeypatch):
    """Con MOBILE_PLATFORM=ios se usan capabilities de XCUITest."""
    monkeypatch.setenv("MOBILE_PLATFORM", "ios")
    caps = build_options().to_capabilities()
    assert caps["platformName"] == "iOS"
    assert caps["appium:automationName"] == "XCUITest"


def test_flutter_locators_per_platform(monkeypatch):
    """Android busca por resource-id; iOS por accessibility id."""
    monkeypatch.setenv("MOBILE_PLATFORM", "android")
    assert flutter_id("login-button") == (AppiumBy.ANDROID_UIAUTOMATOR,
                                          'new UiSelector().resourceId("login-button")')
    assert by_text("Ingresar")[0] == AppiumBy.ANDROID_UIAUTOMATOR
    monkeypatch.setenv("MOBILE_PLATFORM", "ios")
    assert flutter_id("login-button") == (AppiumBy.ACCESSIBILITY_ID, "login-button")
    assert by_text("Ingresar")[0] == AppiumBy.IOS_PREDICATE


class FakeElement:
    """Elemento falso que registra las acciones recibidas (doble de prueba)."""

    def __init__(self):
        self.actions = []

    def click(self):
        self.actions.append("click")

    def clear(self):
        self.actions.append("clear")

    def send_keys(self, text):
        self.actions.append(f"keys:{text}")


class FakeDriver:
    """Driver falso: registra teclas y comandos shell."""

    def __init__(self, platform="Android"):
        self.capabilities = {"platformName": platform}
        self.calls = []

    def press_keycode(self, code):
        self.calls.append(f"keycode:{code}")

    def execute_script(self, name, args):
        self.calls.append(f"{name}:{' '.join(args['args'])}")


def test_scanner_type_strategy_types_code_and_enter():
    """Estrategia 'type': escribe el código y presiona ENTER (keycode 66)."""
    driver, field = FakeDriver(), FakeElement()
    BarcodeScannerSimulator(driver).scan(field, "7501234567890")
    assert field.actions == ["click", "clear", "keys:7501234567890"]
    assert driver.calls == ["keycode:66"]


def test_scanner_adb_strategy_uses_shell_input():
    """Estrategia 'adb': inyecta texto y ENTER a nivel de sistema operativo."""
    driver, field = FakeDriver(), FakeElement()
    BarcodeScannerSimulator(driver, strategy="adb").scan(field, "123")
    assert driver.calls == ["mobile: shell:text 123", "mobile: shell:keyevent 66"]


def test_scanner_on_ios_sends_return():
    """En iOS se envía '\\n' (Return) en vez de un keycode."""
    driver, field = FakeDriver("iOS"), FakeElement()
    BarcodeScannerSimulator(driver).scan(field, "123")
    assert field.actions[-1] == "keys:\n"
