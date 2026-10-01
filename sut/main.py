"""
Aplicación FastAPI que simula el microservicio ``orders-api`` de LogiTrack
y sirve la pantalla de login del "Centro de Control".

Cómo ejecutarla (desde la raíz del repo, con el entorno virtual activo):

    uvicorn sut.main:app --port 8000

Luego abrir:
    - http://localhost:8000/docs            -> documentación interactiva (Swagger)
    - http://localhost:8000/control/login   -> pantalla de login (web)
"""

# json: para escribir los logs en formato JSON (como los lee Cloud Logging).
import json

# logging: módulo estándar de logs de Python.
import logging

# time: para medir cuánto tarda cada petición (latencia).
import time

# uuid: para generar un ID único por petición (correlación de logs).
import uuid

# Path: manejo de rutas de archivos (ubicar la carpeta web/).
from pathlib import Path

# Componentes de FastAPI:
#   FastAPI  -> la aplicación.
#   Depends  -> inyección de dependencias (p. ej. "usuario autenticado").
#   Request  -> objeto con los datos de la petición HTTP.
#   APIRouter-> agrupa rutas.
from fastapi import APIRouter, Depends, FastAPI, Request

# Error que FastAPI lanza cuando el JSON no cumple el modelo Pydantic.
from fastapi.exceptions import RequestValidationError

# Middleware de CORS (controla qué sitios web pueden llamar a la API).
from fastapi.middleware.cors import CORSMiddleware

# Tipos de respuesta: JSON, archivo (HTML) y redirección.
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

# Para servir archivos estáticos (JS y CSS de la página de login).
from fastapi.staticfiles import StaticFiles

# Módulos propios del servicio simulado.
from sut.config import Settings, get_settings
from sut.errors import DomainError, RateLimitError, UnauthorizedError, UnsupportedMediaTypeError
from sut.events import InMemoryEventBus
from sut.repository import InMemoryRepository
from sut.schemas import AssignOrderRequest, CreateTestOrdersRequest, CreateTestTokenRequest, LoginRequest
from sut.security import SlidingWindowRateLimiter, TokenError, create_token, decode_token, verify_password
from sut.service import AssignmentService

# Carpeta donde están login.html, dashboard.html, app.js y styles.css.
WEB_DIR = Path(__file__).parent / "web"

# Logger del servicio. Escribe en la salida estándar (stdout); en Cloud Run todo
# lo que sale por stdout llega automáticamente a Cloud Logging.
logger = logging.getLogger("orders-api")
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Cabeceras de seguridad que se agregan a TODAS las respuestas.
SECURITY_HEADERS = {
    # CSP: el navegador sólo carga scripts/estilos de nuestro propio dominio (mitiga XSS).
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
    ),
    # Impide que el navegador "adivine" el tipo de contenido.
    "X-Content-Type-Options": "nosniff",
    # Impide que la página se muestre dentro de un iframe (clickjacking).
    "X-Frame-Options": "DENY",
    # Obliga a usar HTTPS durante 1 año.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # No enviar la URL completa como "Referer" a otros sitios.
    "Referrer-Policy": "no-referrer",
    # Desactiva APIs sensibles del navegador que no usamos.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _error_body(request: Request, code: str, message: str, details: list | None = None) -> dict:
    """
    Construye el cuerpo JSON estándar de error.

    Args:
        request: petición actual (de ahí sacamos el requestId).
        code: código de error estable (ej. ``ORDER_NOT_FOUND``).
        message: mensaje legible.
        details: lista opcional con detalle por campo.

    Returns:
        ``{"error": {"code", "message", "details"?}, "requestId": ...}``
    """
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error, "requestId": getattr(request.state, "request_id", None)}


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    *Application factory*: crea una aplicación nueva e independiente.

    Tener una fábrica permite que cada prueba de integración cree su propia app
    con su propia configuración y datos limpios.

    Args:
        settings: configuración a usar; si es ``None`` se lee del entorno.

    Returns:
        Aplicación FastAPI lista para servir.
    """
    # Si no nos pasan configuración, la leemos de las variables de entorno.
    settings = settings or get_settings()

    # Creamos los componentes y los "cableamos" (inyección de dependencias manual).
    repository = InMemoryRepository()
    event_bus = InMemoryEventBus()
    rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
    service = AssignmentService(
        repository,
        event_bus,
        lock_enabled=settings.assignment_lock_enabled,
        simulated_latency_ms=settings.simulated_latency_ms,
    )

    # La aplicación FastAPI. title/version aparecen en la documentación /docs.
    app = FastAPI(title="LogiTrack orders-api (simulado)", version="1.0.0")
    # Guardamos referencias en app.state para que las pruebas puedan inspeccionarlas.
    app.state.settings = settings
    app.state.repository = repository
    app.state.event_bus = event_bus
    app.state.rate_limiter = rate_limiter

    # ------------------------------------------------------------------ CORS
    # Sólo los orígenes de la lista pueden llamar la API desde un navegador.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ------------------------------------------------- Middleware de logging
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """
        Se ejecuta en CADA petición:
            1. Asigna un requestId (o reutiliza el que manda el cliente).
            2. Extrae el trace ID (para correlacionar logs entre microservicios).
            3. Llama a la ruta, mide la latencia y agrega cabeceras de seguridad.
            4. Escribe una línea de log JSON con el formato de Cloud Logging.
        """
        # 1. ID de la petición: si el cliente envía X-Request-ID lo respetamos.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        # 2. "traceparent" (W3C) = "00-<trace_id>-<span_id>-01"; Cloud Run lo propaga.
        traceparent = request.headers.get("traceparent", "")
        trace_id = traceparent.split("-")[1] if traceparent.count("-") >= 3 else uuid.uuid4().hex
        # 3. Medimos el tiempo y ejecutamos la ruta.
        started = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - started
        # Agregamos las cabeceras de seguridad y el requestId a la respuesta.
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        response.headers["X-Request-ID"] = request_id
        # Las respuestas de la API no deben quedar en caché (contienen datos privados).
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        # 4. Log estructurado: Cloud Logging entiende "severity", "httpRequest" y "trace".
        logger.info(json.dumps({
            "severity": "ERROR" if response.status_code >= 500 else "INFO",
            "message": f"{request.method} {request.url.path} -> {response.status_code}",
            "service": settings.service_name,
            "requestId": request_id,
            "logging.googleapis.com/trace": f"projects/{settings.gcp_project}/traces/{trace_id}",
            "httpRequest": {
                "requestMethod": request.method,
                "requestUrl": request.url.path,
                "status": response.status_code,
                "latency": f"{latency:.3f}s",
            },
        }))
        return response

    # ---------------------------------------------- Manejadores de errores
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """Convierte cualquier error de dominio en su respuesta HTTP."""
        headers = {}
        # 401 debe indicar el esquema de autenticación esperado (RFC 6750).
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        # 429 indica cuántos segundos esperar.
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code, content=_error_body(request, exc.code, exc.message), headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Errores de validación (campos vacíos, formato inválido, JSON malformado) -> HTTP 400.

        NO devolvemos el valor recibido ("input"), sólo el campo y el problema:
        reflejar la entrada del usuario puede facilitar ataques XSS.
        """
        details = [
            {"field": ".".join(str(p) for p in err["loc"] if p != "body") or "body", "issue": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=_error_body(request, "VALIDATION_ERROR", "La petición no es válida", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """
        Cualquier error no previsto -> HTTP 500 genérico.
        Nunca exponemos el stack trace al cliente (fuga de información).
        """
        logger.exception("Error no controlado")
        return JSONResponse(status_code=500, content=_error_body(request, "INTERNAL_ERROR", "Error interno"))

    # --------------------------------------------------------- Dependencias
    def current_user(request: Request) -> dict:
        """
        Dependencia: obtiene el usuario autenticado a partir del token Bearer
        y aplica el rate limit por usuario.

        Raises:
            UnauthorizedError: si el token falta o no es válido.
            RateLimitError: si el usuario superó el límite por minuto.
        """
        # Esperamos el header "Authorization: Bearer <token>".
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise UnauthorizedError("Falta el token de acceso")
        try:
            claims = decode_token(token.strip(), settings.jwt_secret)
        except TokenError as exc:
            raise UnauthorizedError(f"Token inválido: {exc}") from exc
        # Rate limiting por usuario ("sub" = nombre de usuario).
        allowed, retry_after = rate_limiter.allow(claims["sub"])
        if not allowed:
            raise RateLimitError("Demasiadas peticiones, intente más tarde", retry_after)
        return claims

    def require_json(request: Request) -> None:
        """Dependencia: exige ``Content-Type: application/json`` en el cuerpo."""
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise UnsupportedMediaTypeError("Content-Type debe ser application/json")

    # ---------------------------------------------------------------- Rutas
    @app.get("/health", tags=["infra"])
    def health() -> dict:
        """Health check: lo usan Cloud Run, los smoke tests y k6 para saber si el servicio vive."""
        return {"status": "UP", "service": settings.service_name}

    @app.post("/api/v1/auth/login", tags=["auth"], dependencies=[Depends(require_json)])
    def login(body: LoginRequest) -> dict:
        """
        Inicia sesión y devuelve un token JWT.

        Usuario inexistente, contraseña incorrecta o usuario inactivo devuelven
        EL MISMO mensaje: así un atacante no puede averiguar qué usuarios existen.
        """
        user = repository.get_user(body.username)
        if user is None or not user["active"] or not verify_password(body.password, user["password_hash"]):
            raise UnauthorizedError("Usuario o contraseña incorrectos")
        claims = {"sub": user["username"], "name": user["name"], "role": user["role"],
                  "warehouses": user["warehouses"]}
        token = create_token(claims, settings.jwt_secret, settings.token_ttl_minutes * 60)
        return {"accessToken": token, "tokenType": "Bearer", "expiresIn": settings.token_ttl_minutes * 60,
                "user": {"username": user["username"], "name": user["name"], "role": user["role"]}}

    @app.post("/api/v1/orders/assign", tags=["orders"], status_code=201,
              dependencies=[Depends(require_json)])
    def assign_order(body: AssignOrderRequest, user: dict = Depends(current_user)) -> JSONResponse:
        """
        Asigna un pedido a un operador.

        Respuestas: 201 creado | 200 ya asignado al mismo operador (idempotente) |
        400 validación | 401 token | 403 permisos | 404 no existe | 409 conflicto |
        415 content-type | 422 regla de negocio | 429 rate limit.
        """
        result = service.assign(user, body.orderId, body.operatorId, body.warehouseId, body.priority.value)
        return JSONResponse(status_code=201 if result.created else 200, content=result.assignment)

    @app.get("/api/v1/orders", tags=["orders"])
    def list_orders(user: dict = Depends(current_user)) -> dict:
        """Lista los pedidos de los almacenes del usuario (alimenta el dashboard)."""
        orders = [o for o in repository.list_orders() if o["warehouseId"] in user["warehouses"]]
        return {"items": orders, "total": len(orders)}

    # --------------------------------------------- Rutas de soporte a pruebas
    # Sólo existen si ENABLE_TEST_SUPPORT=true. include_in_schema=False las oculta de /docs.
    if settings.enable_test_support:
        support = APIRouter(prefix="/api/v1/test-support", include_in_schema=False)

        @support.post("/reset")
        def reset() -> dict:
            """Restaura los datos semilla, borra eventos y reinicia el rate limiter."""
            repository.reset()
            event_bus.clear()
            rate_limiter.reset()
            return {"status": "reset"}

        @support.post("/orders", status_code=201)
        def create_orders(body: CreateTestOrdersRequest) -> dict:
            """Crea pedidos nuevos para que cada prueba use datos propios (aislamiento)."""
            return {"orderIds": repository.create_orders(body.warehouseId, body.status, body.count)}

        @support.get("/events")
        def events(topic: str | None = None) -> dict:
            """Devuelve los mensajes publicados en el Pub/Sub simulado."""
            return {"messages": event_bus.messages(topic)}

        @support.post("/tokens")
        def custom_token(body: CreateTestTokenRequest) -> dict:
            """Emite un token con vigencia a medida (negativa = expirado)."""
            user = repository.get_user(body.username)
            if user is None:
                raise UnauthorizedError("Usuario desconocido")
            claims = {"sub": user["username"], "name": user["name"], "role": user["role"],
                      "warehouses": user["warehouses"]}
            return {"accessToken": create_token(claims, settings.jwt_secret, body.expiresInSeconds)}

        app.include_router(support)

    # ------------------------------------------- Páginas web (Centro de Control)
    # /static/app.js y /static/styles.css
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """La raíz redirige a la pantalla de login."""
        return RedirectResponse("/control/login")

    @app.get("/control/login", include_in_schema=False)
    def login_page() -> FileResponse:
        """Pantalla de login."""
        return FileResponse(WEB_DIR / "login.html")

    @app.get("/control/dashboard", include_in_schema=False)
    def dashboard_page() -> FileResponse:
        """Landing page después del login."""
        return FileResponse(WEB_DIR / "dashboard.html")

    @app.get("/control/forgot-password", include_in_schema=False)
    def forgot_password_page() -> FileResponse:
        """Página de recuperación de contraseña."""
        return FileResponse(WEB_DIR / "forgot-password.html")

    return app


# Instancia que usa uvicorn: "uvicorn sut.main:app".
app = create_app()
