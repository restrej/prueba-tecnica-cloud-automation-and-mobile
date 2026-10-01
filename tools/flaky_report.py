"""
REPORTE DE FLAKINESS: detecta tests inestables comparando VARIAS ejecuciones.

Un test es "flaky" si en las mismas condiciones a veces pasa y a veces falla.

Uso:
    # 1) Ejecutar la suite N veces guardando un JUnit por ejecución:
    for i in 1 2 3 4 5 6 7 8 9 10; do pytest -m quarantine --junitxml=reports/flaky/run-$i.xml; done
    # 2) Generar el reporte:
    python tools/flaky_report.py "reports/flaky/*.xml"

Salida: tabla Markdown (y en $GITHUB_STEP_SUMMARY si existe) con la tasa de fallo de cada test.
"""

import glob
import os
import sys
from collections import defaultdict

# Reutilizamos el lector JUnit del quality gate (no duplicar código).
from quality_gate import parse_junit

# Umbral: si un test falla en más de este % de ejecuciones, se considera roto (no flaky).
BROKEN_THRESHOLD = 90.0


def build_report(paths: list[str]) -> str:
    """
    Calcula pasadas/fallas por test a través de todas las ejecuciones.

    Args:
        paths: archivos JUnit (uno por ejecución).

    Returns:
        Reporte en Markdown.
    """
    # stats[nombre] = {"passed": n, "failed": m}
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0})
    for path in paths:
        for result in parse_junit([path]):
            if result["outcome"] in ("passed", "failed"):
                stats[result["name"]][result["outcome"]] += 1

    lines = [f"## Reporte de flakiness ({len(paths)} ejecuciones)", "",
             "| Test | Pasó | Falló | Tasa de fallo | Clasificación |", "|---|---|---|---|---|"]
    # Ordenamos de mayor a menor tasa de fallo.
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1]["failed"]):
        total = s["passed"] + s["failed"]
        rate = s["failed"] / total * 100 if total else 0
        if s["failed"] == 0:
            label = "estable"
        elif rate >= BROKEN_THRESHOLD:
            label = "ROTO (falla siempre)"
        else:
            label = "FLAKY -> cuarentena + ticket"
        lines.append(f"| `{name}` | {s['passed']} | {s['failed']} | {rate:.0f}% | {label} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """Imprime el reporte; siempre devuelve 0 (es informativo, no bloquea)."""
    paths = sorted({p for pattern in argv for p in glob.glob(pattern)})
    if not paths:
        print("No hay reportes JUnit para analizar.")
        return 0
    report = build_report(paths)
    print(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
