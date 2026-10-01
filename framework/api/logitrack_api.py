"""
Cliente de la API de LogiTrack para las pruebas.

Patrón **API Object** (equivalente al Page Object, pero para APIs): una clase
con un método por operación de negocio. Las pruebas NO arman URLs ni headers;
llaman métodos con nombres claros (``login``, ``assign_order``). Si cambia la
URL de un endpoint, se corrige aquí y todas las pruebas siguen funcionando.
"""

# httpx: cliente HTTP (similar a "requests", pero moderno).
import httpx

# Timeout configurable.
from framework.config import HTTP_TIMEOUT_SECONDS


class LogiTrackApi:
    """
    Cliente HTTP de alto nivel para ``orders-api``.

    Ejemplo:
        api = LogiTrackApi("http://localhost:8000")
        api.login("supervisor1", "Sup3rvisor!2025")
        response = api.assign_order({"orderId": ..., ...})
    """

    def __init__(self, base_url: str) -> None:
        """
        Args:
            base_url: URL raíz del servicio (ej. ``http://localhost:8000``).
        """
        # Un único cliente reutiliza conexiones (más rápido que abrir una por petición).
        self.http = httpx.Client(base_url=base_url, timeout=HTTP_TIMEOUT_SECONDS)
        # Token del usuario actual (None hasta hacer login).
        self.token: str | None = None

    # ------------------------------------------------------------------ Auth
    def login(self, username: str, password: str) -> httpx.Response:
        """
        Inicia sesión. Si es exitoso, guarda el token para las siguientes llamadas.

        Returns:
            La respuesta HTTP completa (para que la prueba pueda validarla).
        """
        response = self.http.post("/api/v1/auth/login", json={"username": username, "password": password})
        if response.status_code == 200:
            self.token = response.json()["accessToken"]
        return response

    def auth_headers(self, token: str | None = None) -> dict:
        """
        Construye el header ``Authorization``.

        Args:
            token: token a usar; si es ``None`` se usa el del login.

        Returns:
            Diccionario de headers (vacío si no hay token).
        """
        token = token if token is not None else self.token
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ---------------------------------------------------------------- Orders
    def assign_order(
        self, payload: dict, token: str | None = None, headers: dict | None = None
    ) -> httpx.Response:
        """
        Llama ``POST /api/v1/orders/assign``.

        Args:
            payload: cuerpo JSON (ver ``framework.api.payloads.assign_payload``).
            token: permite probar con un token distinto (inválido, expirado...).
            headers: headers extra (ej. Origin para probar CORS).

        Returns:
            Respuesta HTTP sin procesar.
        """
        all_headers = {**self.auth_headers(token), **(headers or {})}
        return self.http.post("/api/v1/orders/assign", json=payload, headers=all_headers)

    def list_orders(self) -> httpx.Response:
        """Llama ``GET /api/v1/orders``."""
        return self.http.get("/api/v1/orders", headers=self.auth_headers())

    # ----------------------------------------------- Soporte a pruebas (test data)
    def reset_data(self) -> None:
        """Restaura los datos semilla del servidor."""
        self.http.post("/api/v1/test-support/reset").raise_for_status()

    def create_test_order(self, warehouse_id: str = "WH-05", status: str = "READY_FOR_ASSIGNMENT") -> str:
        """
        Crea un pedido NUEVO para que la prueba no dependa de otras (aislamiento).

        Returns:
            El ``orderId`` creado.
        """
        response = self.http.post(
            "/api/v1/test-support/orders", json={"warehouseId": warehouse_id, "status": status, "count": 1}
        )
        response.raise_for_status()
        return response.json()["orderIds"][0]

    def expired_token(self, username: str) -> str:
        """Pide al servidor un token ya expirado para un usuario."""
        body = {"username": username, "expiresInSeconds": -60}
        response = self.http.post("/api/v1/test-support/tokens", json=body)
        response.raise_for_status()
        return response.json()["accessToken"]

    def published_events(self, topic: str = "order-assigned") -> list[dict]:
        """Devuelve los mensajes publicados en el Pub/Sub simulado."""
        return self.http.get("/api/v1/test-support/events", params={"topic": topic}).json()["messages"]

    def close(self) -> None:
        """Cierra las conexiones HTTP abiertas."""
        self.http.close()
