"""
Constructores de datos de prueba (payloads).

Patrón **Test Data Builder** en su versión más simple: una función que devuelve
un payload VÁLIDO por defecto, y cada prueba cambia sólo el campo que le
interesa. Así el test muestra claramente qué está probando:

    assign_payload(priority="URGENT")      # sólo cambia la prioridad
    assign_payload(orderId="")             # sólo deja vacío el pedido
"""


def assign_payload(**overrides) -> dict:
    """
    Devuelve el cuerpo de ``POST /api/v1/orders/assign``.

    Args:
        **overrides: campos a reemplazar sobre el payload por defecto.
            Si se pasa un valor ``None`` el campo se ELIMINA (para probar campos faltantes).

    Returns:
        Diccionario listo para enviarse como JSON.
    """
    # Payload válido del enunciado del PDF.
    payload = {
        "orderId": "ORD-2025-007841",
        "operatorId": "OP-312",
        "warehouseId": "WH-05",
        "priority": "NORMAL",
    }
    # Aplicamos los cambios pedidos por la prueba.
    for key, value in overrides.items():
        if value is None:
            payload.pop(key, None)   # None = quitar el campo
        else:
            payload[key] = value
    return payload
