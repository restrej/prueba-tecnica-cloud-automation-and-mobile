"""
conftest.py raíz: fixtures (piezas reutilizables) y hooks compartidos por TODAS las pruebas.

¿Qué es una fixture? Una función que prepara algo que la prueba necesita
(un servidor, un cliente logueado...) y lo "inyecta" por nombre de parámetro:

    def test_algo(api):      # pytest ve "api" y ejecuta la fixture api()
        ...

Este archivo:
    1. Levanta automáticamente el servidor simulado si no se indicó BASE_URL.
    2. Entrega clientes de API listos (anónimo y logueado).
    3. Marca los tests "critical" en el reporte JUnit para el quality gate.
"""

# os: variables de entorno; socket: buscar un puerto libre.
import os
import socket

# subprocess: lanzar el servidor uvicorn como proceso aparte; sys: ruta del Python actual.
import subprocess
import sys

# time: esperar a que el servidor arranque.
import time

# Path: rutas de archivos para los logs del servidor.
from pathlib import Path

# httpx: para consultar /health mientras el servidor arranca.
import httpx
import pytest

from framework import config
from framework.api.logitrack_api import LogiTrackApi

# Carpeta raíz del repositorio (este archivo está en tests/).
ROOT_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# Hooks: personalizan el comportamiento de pytest
# =============================================================================
def pytest_collection_modifyitems(config, items):
    """
    Se ejecuta después de que pytest descubre las pruebas.

    Para cada prueba marcada con ``@pytest.mark.critical`` agregamos la propiedad
    ``critical=true`` al reporte JUnit XML. El script ``tools/quality_gate.py``
    lee esa propiedad para decidir si el pipeline debe bloquearse.
    """
    for item in items:
        if item.get_closest_marker("critical"):
            item.user_properties.append(("critical", "true"))
        if item.get_closest_marker("quarantine"):
            item.user_properties.append(("quarantine", "true"))


# =============================================================================
# Servidor bajo prueba
# =============================================================================
def _free_port() -> int:
    """Pide al sistema operativo un puerto TCP libre y lo devuelve."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))         # puerto 0 = "dame uno libre"
        return sock.getsockname()[1]


def _wait_until_healthy(url: str, timeout_seconds: float = 20) -> None:
    """
    Consulta ``/health`` hasta que responda 200 o se agote el tiempo.

    Es una ESPERA ACTIVA CON CONDICIÓN (polling), no un sleep fijo: termina
    apenas el servidor está listo.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                return
        except httpx.TransportError:
            pass                              # todavía no acepta conexiones
        time.sleep(0.2)
    raise RuntimeError(f"El servidor {url} no respondió /health en {timeout_seconds}s")


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    """
    URL del sistema bajo prueba (alcance "session" = una sola vez por ejecución).

    Prioridad:
        1. Opción ``--base-url`` de la línea de comandos.
        2. Variable de entorno ``BASE_URL``.
        3. Si no hay ninguna: levanta ``uvicorn sut.main:app`` en un puerto libre
           y lo apaga al terminar las pruebas.

    Nota: esta fixture también la usa pytest-playwright, así ``page.goto("/control/login")``
    se resuelve contra esta URL.
    """
    explicit = pytestconfig.getoption("base_url", default=None) or config.BASE_URL
    if explicit:
        yield explicit.rstrip("/")
        return

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    # Guardamos los logs del servidor en reports/ para revisarlos si algo falla.
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    log_file = open(reports_dir / "sut-server.log", "w")  # noqa: SIM115 (se cierra al final)
    # Lanzamos uvicorn con el mismo intérprete de Python (el del entorno virtual).
    process = subprocess.Popen(  # noqa: S603 (comando fijo, sin entrada del usuario)
        [sys.executable, "-m", "uvicorn", "sut.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT_DIR, stdout=log_file, stderr=subprocess.STDOUT, env={**os.environ},
    )
    try:
        _wait_until_healthy(url)
        yield url                              # <- aquí corren todas las pruebas
    finally:
        # Teardown: apagamos el servidor aunque las pruebas fallen.
        process.terminate()
        process.wait(timeout=10)
        log_file.close()


# =============================================================================
# Clientes de API
# =============================================================================
@pytest.fixture
def anonymous_api(base_url):
    """Cliente de API SIN login (para probar 401, login fallido, etc.)."""
    client = LogiTrackApi(base_url)
    yield client
    client.close()


@pytest.fixture
def api(base_url):
    """Cliente de API logueado como supervisor (el usuario que asigna pedidos)."""
    client = LogiTrackApi(base_url)
    response = client.login(config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD)
    # Si el login falla no tiene sentido seguir: error claro en vez de fallos en cascada.
    assert response.status_code == 200, f"Login de supervisor falló: {response.text}"
    yield client
    client.close()
