# LogiTrack QA Framework: prueba técnica Senior QA Engineer (Cloud, Automation & Mobile)

Implementación ejecutable de la prueba técnica **"Senior QA Engineer — Cloud, Automation & Mobile"**
para la plataforma ficticia **LogiTrack**: estrategia de calidad, automatización de **API**,
**UI web**, **mobile**, **rendimiento**, **seguridad** y **CI/CD**.

> 🧭 **¿Primera vez?** Lee [`docs/PASO_A_PASO.md`](docs/PASO_A_PASO.md): instala y ejecuta todo en orden,
> con el comando exacto y lo que deberías ver en cada paso.
> 📖 **¿Algún término no te suena?** (Cloud Run, Pub/Sub, quality gate, canary, MTTR, SAST/DAST, flaky...)
> Están explicados desde cero en [`docs/GUIA_CONCEPTOS.md`](docs/GUIA_CONCEPTOS.md).

---

## Stack tecnológico

| Necesidad | Herramienta | Por qué |
|---|---|---|
| Lenguaje y runner de pruebas | **Python 3.11 + pytest** | Sintaxis simple, fixtures, markers para armar suites, gran ecosistema |
| API testing | **pytest + httpx** + JSON Schema | Cliente HTTP simple; contratos validados con `jsonschema` |
| UI web | **Playwright** (Python) en **Chrome, Firefox y WebKit** | Espera automática (menos flaky), locators por `data-testid`/rol, trazas y capturas |
| Mobile | **Appium** (UiAutomator2/XCUITest) + Python | Caja negra sobre el APK real, multiplataforma, mismo lenguaje que el resto |
| Rendimiento | **k6** | Scripts en JS versionables, umbrales que hacen fallar el pipeline, bajo consumo |
| Seguridad | **pytest (OWASP)** + **Bandit** (SAST) + **pip-audit** (SCA) + **OWASP ZAP** (DAST) | Gratuitas y automatizables en CI |
| CI/CD | **GitHub Actions** | Integrado con el repositorio, artefactos, required checks |
| Sistema bajo prueba | **FastAPI** (simulación de `orders-api`) | Permite ejecutar todo sin el backend real |

## Requisitos

| Programa | Versión | Necesario para |
|---|---|---|
| Python | 3.11+ | Todo |
| Git | cualquiera | Descargar el repo |
| k6 | 1.x | Rendimiento (opcional) |
| Docker | 24+ | DAST con ZAP (opcional) |
| Flutter, Android Studio (emulador), Node.js 20+ + Appium 2/3 | Flutter 3.35 | Mobile (opcional) |

## Inicio rápido (5 minutos)

```bash
git clone https://github.com/restrej/prueba-tecnica-cloud-automation-and-mobile.git
cd prueba-tecnica-cloud-automation-and-mobile
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chrome firefox webkit

# Ejecuta TODO lo que no necesita emulador (la API simulada se levanta sola)
pytest -m "not quarantine and not mobile" --html=reports/reporte.html --self-contained-html
```

Abre `reports/reporte.html` para ver el resultado.

## Comandos principales

| Quiero... | Comando |
|---|---|
| Ver la API y la web | `uvicorn sut.main:app --port 8000` → <http://localhost:8000/docs> y <http://localhost:8000/control/login> |
| Unitarias + integración + contrato con coverage gate (80%) | `pytest tests/unit tests/integration tests/contract --cov` |
| API (Ejercicio A) | `pytest -m api` |
| UI web (Ejercicio B) | `pytest tests/ui --browser-channel chrome` · `--browser firefox` · `--browser webkit` (agrega `--headed` para ver el navegador) |
| Mobile (Ejercicio C) | `pytest tests/mobile` (requiere Appium + emulador; ver paso 13) |
| Seguridad (5.3) | `pytest -m security` |
| Sólo tests críticos / smoke | `pytest -m critical` / `pytest -m smoke` |
| Quality gate sobre un JUnit | `python tools/quality_gate.py reports/junit.xml` |
| Carga 5.2 (50 VUs, 5 min) | `k6 run performance/k6/assign_load_test.js` (API con `RATE_LIMIT_PER_MINUTE=1000000`) |
| Plan de rendimiento 5.1 | `k6 run -e TEST_TYPE=load\|stress\|soak\|spike [-e QUICK=1] performance/k6/performance_plan.js` |
| SAST / SCA | `bandit -r sut framework tools -c pyproject.toml` · `pip-audit -r requirements.txt` |
| DAST | `bash security/zap/run_zap_scan.sh http://localhost:8000` |
| Lint | `ruff check .` |

## Estructura del repositorio

```
├── sut/                    # Sistema bajo prueba SIMULADO: orders-api (FastAPI) + web de login
│   ├── main.py             #   rutas, middlewares (logs JSON, headers de seguridad), manejo de errores
│   ├── service.py          #   reglas de negocio de la asignación (incluye control de concurrencia)
│   ├── security.py         #   JWT, hash de contraseñas, rate limiting
│   ├── events.py           #   Pub/Sub simulado
│   └── web/                #   pantalla de login y dashboard del "Centro de Control"
├── framework/              # Código reutilizable de automatización
│   ├── api/                #   API Object (LogiTrackApi) + Test Data Builder (payloads)
│   ├── ui/pages/           #   Page Objects (Playwright)
│   └── mobile/             #   capabilities, locators Flutter, simulador de scanner, Screen Objects
├── tests/
│   ├── unit/ integration/ contract/      # base de la pirámide
│   ├── api/                # Ejercicio A: positivos, negativos, límite, concurrencia
│   ├── ui/                 # Ejercicio B: login del Centro de Control
│   ├── mobile/             # Ejercicio C: flujo PickApp con Appium
│   ├── security/           # 5.3: authn/authz, inyección, XSS, headers, CORS, rate limit
│   └── quarantine/         # 6.3: demo de test flaky en cuarentena
├── contracts/              # JSON Schemas: respuesta de la API, errores y evento Pub/Sub
├── performance/k6/         # 5.1 plan (load/stress/soak/spike) y 5.2 script de carga
├── security/zap/           # 5.4 DAST con OWASP ZAP
├── tools/                  # quality_gate.py y flaky_report.py
├── mobile-app/             # PickApp demo en Flutter (objetivo de Appium) + widget tests
├── .github/workflows/      # ci.yml, mobile.yml, performance.yml
└── docs/                   # paso a paso, conceptos, respuestas y entregable PDF
```

## Mapa: partes del PDF → implementación

| Parte | Dónde está |
|---|---|
| 1. Estrategia, factibilidad, métricas | `docs/respuestas/` + `docs/entregable/` |
| 2. Casos de prueba funcionales | `docs/respuestas/` + `docs/entregable/` |
| 3.1 / 3.2 Pipeline ideal y mecanismos | `docs/respuestas/` |
| 3.3 Pipeline funcional | `.github/workflows/ci.yml` + `tools/quality_gate.py` |
| 4-A API | `tests/api/`, `framework/api/` |
| 4-B UI web | `tests/ui/`, `framework/ui/pages/`, `sut/web/` |
| 4-C Mobile | `tests/mobile/`, `framework/mobile/`, `mobile-app/`, `.github/workflows/mobile.yml` |
| 5.1 / 5.2 Rendimiento | `performance/k6/` |
| 5.3 / 5.4 Seguridad | `tests/security/`, `security/zap/`, jobs SAST/DAST de `ci.yml` |
| 6. Troubleshooting y flaky | `docs/respuestas/`, `tests/quarantine/`, `tools/flaky_report.py` |
| 7. Comunicación | `docs/respuestas/` |
| Bonus | `docs/respuestas/`, `contracts/`, `tests/contract/` |

## Resultados de la ejecución local

| Suite | Resultado |
|---|---|
| Unit + Integration + Contract | 45 pruebas OK · cobertura **96%** (gate 80%) |
| **Total sin emulador** | **148 pruebas OK** · quality gate APROBADO |
| API (Ejercicio A) | 40 OK, incluida la concurrencia (y **falla** como debe con `ASSIGNMENT_LOCK_ENABLED=false`) |
| Seguridad (5.3) | 45 OK |
| UI Playwright (Ejercicio B) | 18 OK |
| Mobile | 7 pruebas unitarias del framework OK · 5 E2E de Appium listas (se saltan si no hay emulador) · 5 widget tests de Flutter OK |
| k6 5.2 (50 VUs, 5 min) | 12.826 peticiones · 42,6 req/s · p50 53 ms · p95 57 ms · p99 61 ms · 0% errores |
| SAST (Bandit, Ruff) | 0 hallazgos abiertos |
| DAST (OWASP ZAP API scan) | 113 reglas OK · 0 FAIL · 1 WARN (Content-Type en rutas 404) |
| Flaky demo | 7 pasa / 3 falla en 10 ejecuciones → clasificado FLAKY |
| **GitHub Actions** (`ci.yml`) | [Ejecución #2](https://github.com/restrej/prueba-tecnica-cloud-automation-and-mobile/actions/runs/36812798479): 7/7 jobs en verde en ≈ 4 min |

## Documento entregable (PDF)

El entregable pedido por la prueba está en
[`docs/entregable/Prueba_Tecnica_Senior_QA_LogiTrack.pdf`](docs/entregable/Prueba_Tecnica_Senior_QA_LogiTrack.pdf).
Se genera a partir de las respuestas en Markdown de [`docs/respuestas/`](docs/respuestas/) (que también se leen
directamente en GitHub, con sus diagramas):

```bash
pip install markdown && npm install mermaid@11
python docs/entregable/build_pdf.py --mermaid node_modules/mermaid/dist/mermaid.min.js
```

## CI/CD

- **`ci.yml`** (cada PR y push a `main`): Lint + SAST + SCA → Unit/Integration/Contract con coverage gate →
  API/Security/UI + **quality gate** (bloquea si falla un test `@critical`) → k6 smoke → OWASP ZAP →
  cuarentena (no bloqueante) → **notificación a Slack** (secreto `SLACK_WEBHOOK_URL`). Todos los reportes
  se publican como **artefactos**.
- **`mobile.yml`**: widget tests de Flutter + Appium en una matriz de 2 emuladores (manual, nocturno y tags `rc-*`).
- **`performance.yml`**: pruebas k6 completas bajo demanda/semanales.

## Limitaciones conocidas (transparencia)

- El backend de LogiTrack es **simulado** (`sut/`): base de datos y Pub/Sub en memoria. Los tiempos de k6
  incluyen una latencia artificial de 50 ms (`SIMULATED_LATENCY_MS`) para imitar una consulta a Cloud SQL.
- Los endpoints `/api/v1/test-support/*` existen sólo para preparar datos de prueba y se desactivan con
  `ENABLE_TEST_SUPPORT=false` (como debe ser en producción).
- Las pruebas E2E de Appium no se ejecutaron en el entorno de desarrollo de esta entrega (sin emulador
  Android disponible); la app compila (`flutter analyze` sin hallazgos) y sus widget tests pasan.
  Se ejecutan con el paso 13 de la guía o con el workflow `mobile.yml`.
