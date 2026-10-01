"""
Bus de eventos en memoria que SIMULA Google Cloud Pub/Sub.

En LogiTrack, ``orders-api`` publica un evento en un *topic* de Pub/Sub cuando
asigna un pedido; otros microservicios (inventory-service, notifications-service)
lo consumen de forma asíncrona mediante *subscriptions*.

Aquí guardamos los mensajes publicados en una lista para que las pruebas de
integración y de contrato puedan verificar QUÉ se publicó y CON QUÉ FORMATO.
"""

# json: el cuerpo de un mensaje Pub/Sub son bytes; aquí usamos JSON.
import json

# threading: protege la lista de mensajes ante publicaciones concurrentes.
import threading

# uuid: genera identificadores únicos de mensaje (messageId).
import uuid

# datetime/UTC: fecha de publicación en formato ISO-8601 UTC.
from datetime import UTC, datetime

# Nombre del topic (en GCP sería projects/<proyecto>/topics/order-assigned).
ORDER_ASSIGNED_TOPIC = "order-assigned"


class InMemoryEventBus:
    """
    Implementación en memoria de un publicador Pub/Sub.

    Expone la misma idea que el cliente real (``publish(topic, data, attributes)``)
    para que cambiarlo por ``google.cloud.pubsub_v1.PublisherClient`` en un
    entorno real sea trivial (patrón *Adapter* / inyección de dependencias).
    """

    def __init__(self) -> None:
        """Crea el bus vacío con su lock de concurrencia."""
        # Lista de mensajes publicados (cada uno con topic, data y atributos).
        self._messages: list[dict] = []
        # Lock para que dos hilos no escriban la lista al mismo tiempo.
        self._lock = threading.Lock()

    def publish(self, topic: str, data: dict, attributes: dict[str, str] | None = None) -> str:
        """
        Publica un mensaje en un topic.

        Args:
            topic: nombre del topic destino.
            data: cuerpo del evento (se serializa a JSON, como en Pub/Sub).
            attributes: metadatos clave/valor (p. ej. tipo y versión del evento).

        Returns:
            ``messageId`` asignado al mensaje.
        """
        # Pub/Sub asigna un ID único a cada mensaje publicado.
        message_id = str(uuid.uuid4())
        message = {
            "messageId": message_id,
            "topic": topic,
            # Simulamos la serialización real (bytes JSON) y la deshacemos para inspección.
            "data": json.loads(json.dumps(data)),
            "attributes": attributes or {},
            "publishTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        with self._lock:
            self._messages.append(message)
        return message_id

    def messages(self, topic: str | None = None) -> list[dict]:
        """
        Devuelve una copia de los mensajes publicados.

        Args:
            topic: si se indica, filtra por ese topic.

        Returns:
            Lista de mensajes (copia, para que el llamador no altere el estado interno).
        """
        with self._lock:
            return [m for m in self._messages if topic is None or m["topic"] == topic]

    def clear(self) -> None:
        """Elimina todos los mensajes (usado al reiniciar datos de prueba)."""
        with self._lock:
            self._messages.clear()
