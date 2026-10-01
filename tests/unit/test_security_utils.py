"""
PRUEBAS UNITARIAS de las utilidades de seguridad (``sut/security.py``):
tokens JWT, contraseñas y rate limiter.
"""

# base64/json: para fabricar a mano un token malicioso con "alg: none".
import base64
import json
import os

import pytest

from sut.security import (
    SlidingWindowRateLimiter,
    TokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit

# Secreto sólo para estas pruebas.
SECRET = "unit-test-secret"


def test_token_round_trip_keeps_claims():
    """Un token recién creado se valida y conserva sus datos."""
    token = create_token({"sub": "supervisor1", "role": "SUPERVISOR"}, SECRET, ttl_seconds=60)
    claims = decode_token(token, SECRET)
    assert claims["sub"] == "supervisor1"
    assert claims["role"] == "SUPERVISOR"


def test_expired_token_is_rejected():
    """Un token con expiración en el pasado se rechaza."""
    token = create_token({"sub": "x"}, SECRET, ttl_seconds=-1)
    with pytest.raises(TokenError, match="expirado"):
        decode_token(token, SECRET)


def test_token_signed_with_other_secret_is_rejected():
    """Un token firmado con otro secreto (falsificado) se rechaza."""
    token = create_token({"sub": "x"}, "otro-secreto", ttl_seconds=60)
    with pytest.raises(TokenError, match="Firma"):
        decode_token(token, SECRET)


def test_tampered_payload_is_rejected():
    """Si un atacante cambia el payload (p. ej. su rol), la firma deja de coincidir."""
    header, _, signature = create_token({"sub": "x", "role": "OPERATOR"}, SECRET, 60).split(".")
    evil_json = json.dumps({"sub": "x", "role": "ADMIN"}).encode()
    evil_payload = base64.urlsafe_b64encode(evil_json).decode().rstrip("=")
    with pytest.raises(TokenError):
        decode_token(f"{header}.{evil_payload}.{signature}", SECRET)


def test_alg_none_token_is_rejected():
    """Ataque clásico: token sin firma con 'alg: none'."""
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'x', 'role': 'ADMIN'})}."
    with pytest.raises(TokenError):
        decode_token(token, SECRET)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b", "a.b.c.d", "%%%.###.$$$"])
def test_malformed_tokens_are_rejected(garbage):
    """Textos que no son un JWT válido se rechazan sin romper el servicio."""
    with pytest.raises(TokenError):
        decode_token(garbage, SECRET)


def test_password_hash_verification():
    """La contraseña correcta valida; una incorrecta no."""
    stored = hash_password("Secreta!1", os.urandom(16))
    assert verify_password("Secreta!1", stored) is True
    assert verify_password("secreta!1", stored) is False


def test_rate_limiter_blocks_after_limit_and_isolates_users():
    """Tras N peticiones el usuario queda bloqueado; otro usuario no se ve afectado."""
    limiter = SlidingWindowRateLimiter(limit=3)
    assert [limiter.allow("ana")[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.allow("ana")
    assert allowed is False and retry_after > 0
    assert limiter.allow("luis")[0] is True
    limiter.reset()
    assert limiter.allow("ana")[0] is True
