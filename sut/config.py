"""
Configuración del servicio simulado ``orders-api``.

Sigue el principio de "12-Factor App": toda la configuración que cambia entre
ambientes (dev, staging, producción) se lee de VARIABLES DE ENTORNO y no se
escribe en el código. Así el mismo artefacto (imagen Docker en Cloud Run) se
despliega en todos los ambientes cambiando sólo el entorno.
"""

# "os" permite leer variables de entorno del sistema operativo.
import os

# "secrets" genera valores aleatorios criptográficamente seguros.
import secrets

# "dataclass" crea clases de datos con __init__ automático; "field" permite
# definir valores por defecto calculados (factory).
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    """
    Lee una variable de entorno y la interpreta como booleano.

    Args:
        name: nombre de la variable de entorno (p. ej. ``"ENABLE_TEST_SUPPORT"``).
        default: valor a usar si la variable no está definida.

    Returns:
        ``True`` si el valor es "1", "true", "yes" u "on" (sin importar mayúsculas).
    """
    # os.getenv devuelve None si la variable no existe.
    raw = os.getenv(name)
    # Si no existe, devolvemos el valor por defecto.
    if raw is None:
        return default
    # Normalizamos (minúsculas, sin espacios) y comparamos con valores "verdaderos".
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    """
    Lee una variable de entorno con valores separados por comas y la convierte en lista.

    Args:
        name: nombre de la variable.
        default: texto por defecto (también separado por comas).

    Returns:
        Lista de cadenas sin espacios y sin elementos vacíos.
    """
    # Tomamos el valor (o el default) y lo partimos por comas.
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """
    Parámetros de configuración inmutables (``frozen=True``) del servicio.

    Cada atributo tiene un valor por defecto pensado para ejecución LOCAL,
    y puede sobrescribirse con la variable de entorno indicada.
    """

    # Nombre lógico del servicio; aparece en los logs estructurados (Cloud Logging).
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "orders-api"))
    # Ambiente actual: "local", "staging", "production"...
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    # Proyecto de GCP (se usa para construir el campo "trace" de los logs).
    gcp_project: str = field(default_factory=lambda: os.getenv("GCP_PROJECT", "logitrack-local"))
    # Secreto para firmar los JWT. Si no se define, se genera uno aleatorio por
    # proceso (nunca se deja un secreto fijo en el código: lo detectaría el SAST).
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET") or secrets.token_urlsafe(32))
    # Minutos de vigencia del token de acceso.
    token_ttl_minutes: int = field(default_factory=lambda: int(os.getenv("TOKEN_TTL_MINUTES", "30")))
    # Límite de peticiones por minuto por usuario (protección contra abuso / DoS).
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "300")))
    # Orígenes permitidos por CORS (sólo el Centro de Control y el entorno local).
    cors_allowed_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "CORS_ALLOWED_ORIGINS", "https://control.logitrack.example,http://localhost:8000"
        )
    )
    # Habilita endpoints de soporte a pruebas (reset de datos, inspección de eventos).
    # En producción SIEMPRE debe estar en False.
    enable_test_support: bool = field(default_factory=lambda: _env_bool("ENABLE_TEST_SUPPORT", True))
    # Bloqueo de concurrencia en la asignación. Ponerlo en False reproduce a
    # propósito el bug de "asignaciones duplicadas" (útil para demostrar el test de concurrencia).
    assignment_lock_enabled: bool = field(default_factory=lambda: _env_bool("ASSIGNMENT_LOCK_ENABLED", True))
    # Latencia artificial (ms) dentro de la asignación: ensancha la "ventana de carrera"
    # para que los problemas de concurrencia sean reproducibles en pruebas.
    simulated_latency_ms: int = field(default_factory=lambda: int(os.getenv("SIMULATED_LATENCY_MS", "50")))


def get_settings() -> Settings:
    """
    Construye y devuelve un objeto ``Settings`` leyendo el entorno en ese momento.

    Returns:
        Nueva instancia de :class:`Settings`.
    """
    return Settings()
