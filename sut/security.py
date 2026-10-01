"""
Utilidades de seguridad del servicio simulado.

Incluye:
    1. Hash y verificación de contraseñas (PBKDF2-SHA256, nunca texto plano).
    2. Emisión y validación de tokens JWT firmados con HMAC-SHA256 (HS256).
    3. Rate limiter de ventana deslizante (limita peticiones por usuario/minuto).

Se implementa el JWT "a mano" con la librería estándar para que se pueda leer y
entender cada paso. En un proyecto real se usaría una librería auditada
(p. ej. PyJWT) o el proveedor de identidad (Identity Platform / Auth0).
"""

# base64: codificación Base64URL usada por el formato JWT.
import base64

# hashlib: funciones hash (SHA-256, PBKDF2).
import hashlib

# hmac: firma HMAC y comparación en tiempo constante.
import hmac

# json: serializar el header y el payload del JWT.
import json

# threading: Lock para que el rate limiter sea seguro con múltiples hilos.
import threading

# time: marcas de tiempo (segundos desde epoch) para "iat", "exp" y ventanas.
import time

# deque: cola doble eficiente para guardar timestamps de peticiones.
from collections import deque

# Algoritmo de firma ÚNICO aceptado. Rechazar cualquier otro (p. ej. "none")
# previene el ataque clásico de "alg: none" en JWT.
JWT_ALGORITHM = "HS256"
# Emisor esperado del token (claim "iss").
JWT_ISSUER = "logitrack-auth-service"
# Iteraciones de PBKDF2: más iteraciones = más costoso un ataque de fuerza bruta.
PBKDF2_ITERATIONS = 120_000


class TokenError(Exception):
    """Token ausente, mal formado, con firma inválida o expirado."""


# -----------------------------------------------------------------------------
# 1. Contraseñas
# -----------------------------------------------------------------------------
def hash_password(password: str, salt: bytes) -> str:
    """
    Genera el hash PBKDF2-SHA256 de una contraseña.

    Args:
        password: contraseña en texto plano.
        salt: sal aleatoria única por usuario (evita ataques con tablas rainbow).

    Returns:
        Cadena ``"<sal_hex>$<hash_hex>"`` lista para almacenar.
    """
    # pbkdf2_hmac aplica SHA-256 muchas veces (iteraciones) sobre contraseña+sal.
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    # Guardamos sal y hash juntos para poder verificar después.
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """
    Verifica una contraseña contra el hash almacenado.

    Args:
        password: contraseña recibida en el login.
        stored: valor ``"<sal_hex>$<hash_hex>"`` guardado previamente.

    Returns:
        ``True`` si la contraseña es correcta.
    """
    # Separamos sal y hash.
    salt_hex, _ = stored.split("$", 1)
    # Recalculamos el hash con la misma sal.
    candidate = hash_password(password, bytes.fromhex(salt_hex))
    # compare_digest compara en tiempo constante -> evita ataques de timing.
    return hmac.compare_digest(candidate, stored)


# -----------------------------------------------------------------------------
# 2. JWT
# -----------------------------------------------------------------------------
def _b64url_encode(raw: bytes) -> str:
    """Codifica bytes en Base64URL sin relleno '=' (formato exigido por JWT)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    """Decodifica Base64URL agregando el relleno '=' que se quitó al codificar."""
    # La longitud Base64 debe ser múltiplo de 4; calculamos el relleno faltante.
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_token(claims: dict, secret: str, ttl_seconds: int) -> str:
    """
    Crea un JWT firmado con HS256.

    Args:
        claims: datos del usuario (sub, role, name, warehouses...).
        secret: secreto HMAC del servidor.
        ttl_seconds: segundos de vigencia (puede ser negativo para crear un
            token ya expirado en pruebas de seguridad).

    Returns:
        Token con formato ``header.payload.firma``.
    """
    # Momento actual en segundos.
    now = int(time.time())
    # Header estándar de JWT.
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    # Payload = claims del usuario + claims registrados (emisor, emitido, expiración).
    payload = {**claims, "iss": JWT_ISSUER, "iat": now, "exp": now + ttl_seconds}
    # Codificamos header y payload como JSON compacto en Base64URL.
    signing_input = ".".join(
        _b64url_encode(json.dumps(part, separators=(",", ":")).encode("utf-8")) for part in (header, payload)
    )
    # Firmamos "header.payload" con HMAC-SHA256 usando el secreto.
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    # Resultado final: header.payload.firma
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_token(token: str, secret: str) -> dict:
    """
    Valida un JWT y devuelve sus claims.

    Validaciones (en orden): formato, algoritmo, firma, emisor y expiración.

    Args:
        token: JWT recibido en el header ``Authorization: Bearer <token>``.
        secret: secreto HMAC del servidor.

    Returns:
        Diccionario con los claims del token.

    Raises:
        TokenError: si cualquier validación falla.
    """
    # Un JWT válido tiene exactamente 3 partes separadas por punto.
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Token mal formado")
    header_b64, payload_b64, signature_b64 = parts
    try:
        # Decodificamos header y payload (pueden fallar si no es Base64/JSON).
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Token mal formado") from exc
    # Sólo aceptamos HS256: bloquea "alg: none" y ataques de confusión de algoritmo.
    if header.get("alg") != JWT_ALGORITHM:
        raise TokenError("Algoritmo de firma no permitido")
    # Recalculamos la firma esperada sobre "header.payload".
    expected = hmac.new(
        secret.encode("utf-8"), f"{header_b64}.{payload_b64}".encode("ascii"), hashlib.sha256
    ).digest()
    # Comparación en tiempo constante de la firma.
    if not hmac.compare_digest(expected, signature):
        raise TokenError("Firma inválida")
    # El emisor debe ser nuestro servicio de autenticación.
    if payload.get("iss") != JWT_ISSUER:
        raise TokenError("Emisor inválido")
    # Si la fecha de expiración ya pasó, el token no sirve.
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise TokenError("Token expirado")
    return payload


# -----------------------------------------------------------------------------
# 3. Rate limiting
# -----------------------------------------------------------------------------
class SlidingWindowRateLimiter:
    """
    Rate limiter de **ventana deslizante** en memoria.

    Para cada clave (usuario) guarda los timestamps de sus peticiones en el
    último minuto. Si ya hay ``limit`` peticiones en la ventana, rechaza.
    En producción (Cloud Run con muchas instancias) esto se haría en un
    almacén compartido (Memorystore/Redis) o en el API Gateway / Cloud Armor.
    """

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        """
        Args:
            limit: máximo de peticiones permitidas por ventana.
            window_seconds: tamaño de la ventana en segundos (60 = por minuto).
        """
        self.limit = limit
        self.window_seconds = window_seconds
        # Diccionario clave -> cola de timestamps.
        self._hits: dict[str, deque[float]] = {}
        # Lock para que dos hilos no modifiquen la misma cola a la vez.
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """
        Registra una petición y decide si se permite.

        Args:
            key: identificador del cliente (normalmente el "sub" del token).

        Returns:
            Tupla ``(permitido, segundos_para_reintentar)``.
        """
        # monotonic no se ve afectado por cambios de hora del sistema.
        now = time.monotonic()
        with self._lock:
            # Obtenemos (o creamos) la cola de este cliente.
            hits = self._hits.setdefault(key, deque())
            # Eliminamos los timestamps que ya salieron de la ventana.
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            # Si se alcanzó el límite, calculamos cuánto falta para liberar un cupo.
            if len(hits) >= self.limit:
                retry_after = int(self.window_seconds - (now - hits[0])) + 1
                return False, retry_after
            # Se permite: registramos la petición.
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        """Vacía todos los contadores (usado por el endpoint de reset de pruebas)."""
        with self._lock:
            self._hits.clear()
