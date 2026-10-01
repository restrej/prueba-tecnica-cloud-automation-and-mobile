"""
PARTE 4 - EJERCICIO A: casos de CONCURRENCIA.

Escenario del PDF: "dos supervisores asignan el mismo pedido simultáneamente".
Resultado correcto: exactamente UNA asignación gana (201) y la otra recibe 409.
Si ambas reciben 201 hay una CONDICIÓN DE CARRERA (race condition) -> el bug
real de "asignaciones duplicadas".

Técnica: ``threading.Barrier`` hace que todos los hilos esperen en la "línea de
salida" y disparen la petición en el MISMO instante, maximizando la colisión.

Demostración del bug: levantar el servidor con ASSIGNMENT_LOCK_ENABLED=false y
ejecutar estas pruebas: fallarán porque habrá más de un 201.
"""

# ThreadPoolExecutor: ejecuta funciones en varios hilos a la vez.
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from framework import config
from framework.api.logitrack_api import LogiTrackApi
from framework.api.payloads import assign_payload

pytestmark = [pytest.mark.api, pytest.mark.concurrency]


def _login_as(base_url: str, username: str, password: str) -> LogiTrackApi:
    """Crea un cliente independiente (con su propia conexión) logueado como el usuario dado."""
    client = LogiTrackApi(base_url)
    assert client.login(username, password).status_code == 200
    return client


@pytest.mark.critical
def test_two_supervisors_assign_same_order_simultaneously(base_url, api):
    """Supervisor 1 -> OP-312 y Supervisor 2 -> OP-313 sobre el mismo pedido, al mismo tiempo."""
    order_id = api.create_test_order()
    supervisor_1 = _login_as(base_url, config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD)
    supervisor_2 = _login_as(base_url, config.SECOND_SUPERVISOR_USER, config.SECOND_SUPERVISOR_PASSWORD)
    # Barrera para 2 hilos: ninguno avanza hasta que ambos lleguen.
    barrier = threading.Barrier(2)

    def assign(client: LogiTrackApi, operator_id: str):
        """Trabajo de cada hilo: esperar en la barrera y asignar."""
        barrier.wait()
        return client.assign_order(assign_payload(orderId=order_id, operatorId=operator_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(assign, supervisor_1, "OP-312"), pool.submit(assign, supervisor_2, "OP-313")]
        statuses = sorted(f.result().status_code for f in futures)

    # Exactamente un ganador (201) y un perdedor (409).
    assert statuses == [201, 409], f"Posible condición de carrera: {statuses}"
    # Exactamente UN evento publicado para ese pedido (no se notificó dos veces).
    events = [e for e in api.published_events() if e["data"]["orderId"] == order_id]
    assert len(events) == 1
    supervisor_1.close()
    supervisor_2.close()


def test_many_parallel_assignments_produce_single_owner(base_url, api):
    """Prueba de estrés de concurrencia: 6 peticiones simultáneas a 3 operadores distintos."""
    order_id = api.create_test_order()
    operators = ["OP-312", "OP-313", "OP-314"] * 2
    clients = [_login_as(base_url, config.SUPERVISOR_USER, config.SUPERVISOR_PASSWORD) for _ in operators]
    barrier = threading.Barrier(len(operators))

    def assign(client: LogiTrackApi, operator_id: str):
        barrier.wait()
        return client.assign_order(assign_payload(orderId=order_id, operatorId=operator_id))

    with ThreadPoolExecutor(max_workers=len(operators)) as pool:
        responses = list(pool.map(assign, clients, operators))

    created = [r for r in responses if r.status_code == 201]
    # Sólo una creación; el resto son 409 (otro operador) o 200 (mismo operador, idempotente).
    assert len(created) == 1
    winner = created[0].json()["operatorId"]
    for response in responses:
        if response.status_code == 200:
            assert response.json()["operatorId"] == winner
        elif response.status_code != 201:
            assert response.status_code == 409
    for client in clients:
        client.close()
