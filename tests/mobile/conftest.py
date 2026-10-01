"""
Fixtures de las pruebas mobile (Appium).

Requisitos para que estas pruebas se EJECUTEN (si no, se marcan como "skipped"):
    1. Servidor Appium corriendo:        appium  (por defecto en http://127.0.0.1:4723)
    2. Emulador/dispositivo Android:     adb devices  (debe listar uno)
    3. APK de PickApp compilado:         cd mobile-app && flutter build apk --debug
Ver docs/PASO_A_PASO.md, paso 8.
"""

import os
from pathlib import Path

import httpx
import pytest

# webdriver de Appium: crea la sesión remota contra el servidor Appium.
from appium import webdriver

from framework.mobile.capabilities import build_options

# URL del servidor Appium.
APPIUM_SERVER_URL = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")


def _appium_is_running() -> bool:
    """Consulta el endpoint /status de Appium para saber si está disponible."""
    try:
        return httpx.get(f"{APPIUM_SERVER_URL}/status", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture
def driver(request):
    """
    Abre una sesión de Appium NUEVA por prueba (app limpia) y la cierra al final.

    Si la prueba falla, guarda una captura de pantalla en reports/mobile/ como evidencia.
    """
    if not _appium_is_running():
        pytest.skip(f"Appium no está disponible en {APPIUM_SERVER_URL} (ver docs/PASO_A_PASO.md paso 8)")
    session = webdriver.Remote(APPIUM_SERVER_URL, options=build_options())
    # Espera implícita en 0: usamos SOLO esperas explícitas (BaseScreen) -> tiempos predecibles.
    session.implicitly_wait(0)
    yield session
    # rep_call lo deja el hook de abajo: sabemos si la prueba falló.
    report = getattr(request.node, "rep_call", None)
    if report is not None and report.failed:
        evidence_dir = Path("reports/mobile")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        session.save_screenshot(str(evidence_dir / f"{request.node.name}.png"))
    session.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Guarda el resultado de cada fase (setup/call/teardown) en el item para usarlo en la fixture."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
