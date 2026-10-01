"""
Configuración de las pruebas (URLs y credenciales).

Todo se puede cambiar con variables de entorno, así el MISMO código de pruebas
corre contra local, staging o un ambiente efímero de un Pull Request:

    BASE_URL=https://staging.logitrack.example pytest -m api
"""

# os.getenv lee variables de entorno con un valor por defecto.
import os

# URL base del servicio. Si está vacía, conftest.py levanta un servidor local solo.
BASE_URL = os.getenv("BASE_URL", "")

# Credenciales de usuarios de prueba (en CI vendrían de GitHub Secrets).
SUPERVISOR_USER = os.getenv("SUPERVISOR_USER", "supervisor1")
SUPERVISOR_PASSWORD = os.getenv("SUPERVISOR_PASSWORD", "Sup3rvisor!2025")
SECOND_SUPERVISOR_USER = os.getenv("SECOND_SUPERVISOR_USER", "supervisor2")
SECOND_SUPERVISOR_PASSWORD = os.getenv("SECOND_SUPERVISOR_PASSWORD", "Sup3rvisor!2025")
OPERATOR_USER = os.getenv("OPERATOR_USER", "operator1")
OPERATOR_PASSWORD = os.getenv("OPERATOR_PASSWORD", "0perator!2025")

# Tiempo máximo (segundos) que esperamos una respuesta HTTP antes de fallar.
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
