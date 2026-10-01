"""
DEMOSTRACIÓN de gestión de tests FLAKY (Parte 6.3).

Un test "flaky" (inestable) a veces pasa y a veces falla SIN que cambie el código.
Este archivo contiene un test que falla a propósito ~30% de las veces
(3 de cada 10, como el escenario 2 de la Parte 6) para mostrar el proceso:

    1. Se marca con ``@pytest.mark.quarantine`` -> sale del pipeline bloqueante.
    2. El job "quarantine" lo ejecuta con reintentos y NO bloquea el merge.
    3. ``tools/flaky_report.py`` calcula su tasa de fallo en N ejecuciones.
    4. Se crea un ticket con dueño y fecha; se arregla la causa raíz y se saca de cuarentena.

El pipeline principal ejecuta ``-m "not quarantine"``, por eso este test nunca bloquea.
"""

# random: simula el comportamiento no determinista.
import random

import pytest

pytestmark = [pytest.mark.quarantine]


def test_flaky_assignment_sync_demo():
    """
    Simula un test que depende de una espera mal configurada: el dashboard
    a veces aún no refleja la asignación cuando el test verifica.
    """
    # Probabilidad de que "el sistema ya esté sincronizado" cuando el test mira: 70%.
    dashboard_synced = random.random() >= 0.30  # noqa: S311 (no es criptografía)
    assert dashboard_synced, "El dashboard no reflejó la asignación a tiempo (flaky)"
