"""
Modelos de entrada (request bodies) validados con Pydantic.

Pydantic revisa AUTOMÁTICAMENTE que el JSON recibido tenga los campos correctos,
con el tipo y el formato correctos. Si algo no cumple, FastAPI responde un error
de validación antes de llegar a la lógica de negocio.
"""

# StrEnum: lista cerrada de valores de texto permitidos (para "priority").
from enum import StrEnum

# BaseModel = clase base de los modelos; ConfigDict = configuración; Field = reglas por campo.
from pydantic import BaseModel, ConfigDict, Field

# Expresiones regulares con el formato exacto de cada ID.
#   ^ y $ obligan a que TODO el texto cumpla (no sólo una parte).
ORDER_ID_PATTERN = r"^ORD-\d{4}-\d{6}$"     # Ej: ORD-2025-007841
OPERATOR_ID_PATTERN = r"^OP-\d{1,6}$"       # Ej: OP-312
WAREHOUSE_ID_PATTERN = r"^WH-\d{2}$"        # Ej: WH-05


class Priority(StrEnum):
    """Prioridades válidas de un pedido."""

    NORMAL = "NORMAL"
    URGENT = "URGENT"
    EXPRESS = "EXPRESS"


class AssignOrderRequest(BaseModel):
    """Cuerpo de ``POST /api/v1/orders/assign``."""

    # extra="forbid": si llegan campos no esperados (p. ej. "role": "ADMIN"),
    # se rechaza la petición. Evita ataques de "mass assignment".
    model_config = ConfigDict(extra="forbid")

    # Cada campo: obligatorio (...), con longitud máxima y patrón de formato.
    orderId: str = Field(..., min_length=1, max_length=20, pattern=ORDER_ID_PATTERN)
    operatorId: str = Field(..., min_length=1, max_length=10, pattern=OPERATOR_ID_PATTERN)
    warehouseId: str = Field(..., min_length=1, max_length=5, pattern=WAREHOUSE_ID_PATTERN)
    # Sólo acepta los valores del Enum Priority.
    priority: Priority


class LoginRequest(BaseModel):
    """Cuerpo de ``POST /api/v1/auth/login``."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=64)


class CreateTestOrdersRequest(BaseModel):
    """Cuerpo del endpoint de soporte que crea pedidos de prueba."""

    warehouseId: str = Field("WH-05", pattern=WAREHOUSE_ID_PATTERN)
    status: str = Field("READY_FOR_ASSIGNMENT")
    # Entre 1 y 50 000 pedidos por llamada (k6 crea muchos de una vez).
    count: int = Field(1, ge=1, le=50_000)


class CreateTestTokenRequest(BaseModel):
    """Cuerpo del endpoint de soporte que emite tokens a medida (p. ej. expirados)."""

    username: str
    # Segundos de vida del token; un valor negativo crea un token YA expirado.
    expiresInSeconds: int = -60
