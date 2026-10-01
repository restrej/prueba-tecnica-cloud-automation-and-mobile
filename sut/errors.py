"""
Errores de dominio del servicio ``orders-api``.

Patrón utilizado: **jerarquía de excepciones de dominio**. La lógica de negocio
(``service.py``) lanza excepciones que describen QUÉ pasó (pedido inexistente,
operador inactivo...), sin saber nada de HTTP. Luego, un único manejador en
``main.py`` traduce cada excepción a su código HTTP y a un cuerpo JSON uniforme.
Esto mantiene el dominio desacoplado de la capa web y hace la lógica fácil de
probar con pruebas unitarias.
"""


class DomainError(Exception):
    """
    Clase base de todos los errores de negocio.

    Attributes:
        status_code: código HTTP con el que se responderá.
        code: identificador estable y legible por máquinas (los tests lo validan).
        message: descripción legible por humanos.
    """

    # Valores por defecto que las subclases sobrescriben.
    status_code: int = 400
    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        """
        Inicializa el error con un mensaje descriptivo.

        Args:
            message: texto que explica el error al consumidor de la API.
        """
        # Llamamos al constructor de Exception para que str(error) funcione.
        super().__init__(message)
        # Guardamos el mensaje para serializarlo en la respuesta JSON.
        self.message = message


class OrderNotFoundError(DomainError):
    """El ``orderId`` no existe en el sistema -> HTTP 404."""

    status_code = 404
    code = "ORDER_NOT_FOUND"


class OperatorNotFoundError(DomainError):
    """El ``operatorId`` no existe -> HTTP 404."""

    status_code = 404
    code = "OPERATOR_NOT_FOUND"


class WarehouseNotFoundError(DomainError):
    """El ``warehouseId`` tiene formato válido pero no existe -> HTTP 404."""

    status_code = 404
    code = "WAREHOUSE_NOT_FOUND"


class OperatorInactiveError(DomainError):
    """El operador existe pero está inactivo (baja/vacaciones) -> HTTP 422."""

    status_code = 422
    code = "OPERATOR_INACTIVE"


class WarehouseMismatchError(DomainError):
    """El pedido o el operador no pertenecen al almacén indicado -> HTTP 422."""

    status_code = 422
    code = "WAREHOUSE_MISMATCH"


class OrderAlreadyAssignedError(DomainError):
    """El pedido ya está asignado a OTRO operador -> HTTP 409 (conflicto)."""

    status_code = 409
    code = "ORDER_ALREADY_ASSIGNED"


class OrderNotAssignableError(DomainError):
    """
    El pedido está en un estado que no permite asignación (p. ej. sin stock /
    "PENDING_RESTOCK" o cancelado) -> HTTP 409.

    Cubre el problema real reportado: "se procesan pedidos con productos que ya
    no están en inventario".
    """

    status_code = 409
    code = "ORDER_NOT_ASSIGNABLE"


class ForbiddenError(DomainError):
    """El usuario autenticado no tiene permiso para la operación -> HTTP 403."""

    status_code = 403
    code = "FORBIDDEN"


class UnauthorizedError(DomainError):
    """No hay token, el token es inválido/expirado o las credenciales fallan -> HTTP 401."""

    status_code = 401
    code = "UNAUTHORIZED"


class UnsupportedMediaTypeError(DomainError):
    """El cliente no envió ``Content-Type: application/json`` -> HTTP 415."""

    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"


class RateLimitError(DomainError):
    """El usuario superó el límite de peticiones por minuto -> HTTP 429."""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str, retry_after: int) -> None:
        """
        Args:
            message: descripción del error.
            retry_after: segundos que el cliente debe esperar (header ``Retry-After``).
        """
        super().__init__(message)
        self.retry_after = retry_after
