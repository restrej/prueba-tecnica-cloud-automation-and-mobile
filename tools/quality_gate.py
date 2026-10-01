"""
QUALITY GATE: decide si el pipeline pasa o se bloquea a partir de los reportes JUnit.

Uso:
    python tools/quality_gate.py reports/*.xml

Reglas:
    0. Si no se ejecutó ninguna prueba (todas saltadas) -> bloquea (sin evidencia no hay aprobación).
    1. Si falla CUALQUIER test marcado como ``critical`` -> bloquea (exit code 1).
    2. Si el porcentaje de éxito total es menor a MIN_PASS_RATE -> bloquea.
    3. Los tests en cuarentena se informan pero NO cuentan para el bloqueo.

Además escribe un resumen en Markdown en ``$GITHUB_STEP_SUMMARY`` (si existe),
que GitHub Actions muestra en la página de la ejecución del workflow.
"""

# glob: expandir comodines como reports/*.xml; os: variables de entorno; sys: argumentos y exit code.
import glob
import os
import sys

# ElementTree: leer archivos XML (el formato JUnit es XML).
# Los XML los genera nuestro propio pipeline (no son entrada externa), por eso se acepta.
import xml.etree.ElementTree as ET  # nosec B405

# Porcentaje mínimo de éxito para tests no críticos.
MIN_PASS_RATE = float(os.getenv("MIN_PASS_RATE", "95"))


def parse_junit(paths: list[str]) -> list[dict]:
    """
    Lee uno o varios archivos JUnit XML y devuelve una lista de resultados.

    Args:
        paths: rutas a los archivos XML.

    Returns:
        Lista de diccionarios ``{name, outcome, critical, quarantine}`` donde
        ``outcome`` es "passed", "failed" o "skipped".
    """
    results = []
    for path in paths:
        tree = ET.parse(path)  # noqa: S314  # nosec B314
        # Cada <testcase> es una prueba ejecutada.
        for case in tree.iter("testcase"):
            # Las propiedades que agregamos en conftest.py (critical=true, quarantine=true).
            props = {p.get("name"): p.get("value") for p in case.iter("property")}
            if case.find("failure") is not None or case.find("error") is not None:
                outcome = "failed"
            elif case.find("skipped") is not None:
                outcome = "skipped"
            else:
                outcome = "passed"
            results.append({
                "name": f"{case.get('classname')}::{case.get('name')}",
                "outcome": outcome,
                "critical": props.get("critical") == "true",
                "quarantine": props.get("quarantine") == "true",
            })
    return results


def evaluate(results: list[dict]) -> tuple[bool, str]:
    """
    Aplica las reglas del quality gate.

    Args:
        results: salida de :func:`parse_junit`.

    Returns:
        Tupla ``(aprobado, resumen_markdown)``.
    """
    # Excluimos la cuarentena del cálculo.
    counted = [r for r in results if not r["quarantine"]]
    executed = [r for r in counted if r["outcome"] != "skipped"]
    passed = [r for r in executed if r["outcome"] == "passed"]
    failed = [r for r in executed if r["outcome"] == "failed"]
    critical_failed = [r for r in failed if r["critical"]]
    pass_rate = (len(passed) / len(executed) * 100) if executed else 100.0

    # Si no se ejecutó ninguna prueba (todas saltadas o ausentes) NO hay evidencia: se bloquea.
    approved = bool(executed) and not critical_failed and pass_rate >= MIN_PASS_RATE
    lines = [
        f"## Quality Gate: {'✅ APROBADO' if approved else '❌ BLOQUEADO'}",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Tests ejecutados | {len(executed)} |",
        f"| Pasaron | {len(passed)} |",
        f"| Fallaron | {len(failed)} |",
        f"| Críticos fallidos | {len(critical_failed)} |",
        f"| Tasa de éxito | {pass_rate:.1f}% (mínimo {MIN_PASS_RATE:.0f}%) |",
        f"| En cuarentena (no bloquean) | {len([r for r in results if r['quarantine']])} |",
    ]
    if not executed:
        lines += ["", "### No se ejecutó ninguna prueba: no hay evidencia de calidad"]
    if critical_failed:
        lines += ["", "### Tests críticos en rojo", *[f"- `{r['name']}`" for r in critical_failed]]
    return approved, "\n".join(lines)


def main(argv: list[str]) -> int:
    """
    Punto de entrada del script.

    Args:
        argv: patrones de archivos JUnit recibidos por línea de comandos.

    Returns:
        0 si el gate aprueba, 1 si bloquea (GitHub Actions marca el paso en rojo).
    """
    paths = sorted({p for pattern in argv for p in glob.glob(pattern)})
    if not paths:
        print("No se encontraron reportes JUnit: el gate bloquea por falta de evidencia.")
        return 1
    approved, summary = evaluate(parse_junit(paths))
    print(summary)
    # GitHub Actions: escribir en este archivo muestra el resumen en la UI de la ejecución.
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")
    return 0 if approved else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
