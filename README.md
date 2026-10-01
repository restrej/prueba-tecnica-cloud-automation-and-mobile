# Prueba técnica Senior QA Engineer: LogiTrack

Solución de la prueba técnica **"Senior QA Engineer: Cloud, Automation & Mobile"**.

- 📄 **Documento entregable (PDF):** [`docs/entregable/Prueba_Tecnica_LogiTrack.pdf`](docs/entregable/Prueba_Tecnica_LogiTrack.pdf)
  (su texto también se puede leer aquí: [`Prueba_Tecnica_LogiTrack.md`](docs/entregable/Prueba_Tecnica_LogiTrack.md)).
- 🧭 **Cómo instalar y ejecutar todo, paso a paso:** [`docs/PASO_A_PASO.md`](docs/PASO_A_PASO.md)
- 📖 **Términos explicados desde cero** (Cloud Run, Pub/Sub, quality gate, MTTR, SAST/DAST...): [`docs/GUIA_CONCEPTOS.md`](docs/GUIA_CONCEPTOS.md)

## Herramientas usadas

| Para qué | Herramienta |
|---|---|
| Lenguaje y ejecución de pruebas | Python 3.11 + **pytest** |
| Pruebas de API | pytest + httpx |
| Pruebas web | **Playwright** en **Google Chrome, Firefox y WebKit** (motor de Safari) |
| Pruebas móviles | **Appium** (con una app de demostración hecha en Flutter) |
| Rendimiento | **k6** |
| Seguridad | Pruebas propias en pytest + **Bandit** (revisa el código) + **OWASP ZAP** (ataca la API funcionando) |
| Pipeline (CI/CD) | **GitHub Actions** |

## Una pieza de apoyo: la API simulada (`sut/`)

La prueba describe una empresa **ficticia** (LogiTrack). Su sistema no existe, así que no habría contra qué ejecutar
las pruebas. Por eso el repositorio incluye una **versión pequeña y simulada** de su API (`POST /api/v1/orders/assign`)
y de la pantalla de login del Centro de Control, hecha con FastAPI.

**La prueba no la pide**: es solo el "campo de práctica" para que todo el código se pueda ejecutar y mostrar resultados
reales. En un trabajo real, las mismas pruebas apuntarían a la API verdadera cambiando una variable:
`BASE_URL=https://api-real.logitrack.com pytest -m api`.

## Inicio rápido

```bash
git clone https://github.com/restrej/prueba-tecnica-cloud-automation-and-mobile.git
cd prueba-tecnica-cloud-automation-and-mobile
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chrome firefox webkit

pytest -m "not quarantine and not mobile"                 # la API simulada se levanta sola
```

## Comandos principales

| Quiero... | Comando |
|---|---|
| Ver la API y la pantalla de login | `uvicorn sut.main:app --port 8000` → <http://localhost:8000/docs> y <http://localhost:8000/control/login> |
| Pruebas unitarias, integración y contrato (con cobertura mínima de 80%) | `pytest tests/unit tests/integration tests/contract --cov` |
| Pruebas de API (Parte 4-A) | `pytest -m api` |
| Pruebas web (Parte 4-B) | `pytest tests/ui --browser-channel chrome` · `--browser firefox` · `--browser webkit` |
| Pruebas móviles (Parte 4-C) | `pytest tests/mobile` (necesita Appium y un emulador: paso 13 de la guía) |
| Pruebas de seguridad (Parte 5.3) | `pytest -m security` |
| Solo las pruebas críticas | `pytest -m critical` |
| Prueba de carga (Parte 5.2) | `k6 run performance/k6/assign_load_test.js` |
| Revisión de seguridad del código | `bandit -r sut framework tools -c pyproject.toml` |
| Ataque automático con OWASP ZAP | `bash security/zap/run_zap_scan.sh http://localhost:8000` (necesita Docker) |

## Estructura

```
├── sut/                 # API simulada de LogiTrack + pantalla de login (pieza de apoyo)
├── framework/           # Código reutilizable: cliente de API, Page Objects (web), Screen Objects (móvil)
├── tests/               # Pruebas: unit, integration, contract, api, ui, mobile, security, quarantine
├── contracts/           # Formatos acordados (JSON Schema) de la API y de los mensajes
├── performance/k6/      # Pruebas de rendimiento (5.1 y 5.2)
├── security/zap/        # Ataque automático con OWASP ZAP (5.4)
├── tools/               # quality_gate.py (puerta de calidad) y flaky_report.py (pruebas inestables)
├── mobile-app/          # App PickApp de demostración en Flutter (objetivo de Appium)
├── .github/workflows/   # Pipelines de GitHub Actions
└── docs/                # Paso a paso, conceptos, capturas y el documento entregable
```

## Pipelines de GitHub Actions

| Archivo | Qué hace |
|---|---|
| `ejemplo-3-3.yml` | El ejemplo **corto** que pide la Parte 3.3: ejecuta pruebas, publica el reporte, bloquea si hay críticas en rojo y notifica a Slack |
| `ci.yml` | Pipeline completo: estilo y seguridad del código, unitarias, API, seguridad, web en 3 navegadores, k6, OWASP ZAP y pruebas en cuarentena |
| `mobile.yml` | Compila la app Flutter y ejecuta Appium en 2 emuladores Android |
| `performance.yml` | Pruebas de rendimiento completas con k6 (a demanda) |

Para la notificación de Slack se debe crear el secreto `SLACK_WEBHOOK_URL` en *Settings → Secrets and variables → Actions*.

## Resultados reales

| Qué | Resultado |
|---|---|
| Pruebas sin emulador (unitarias, integración, contrato, API, seguridad, web) | **148 en verde**; cobertura de código **96%** |
| Prueba de concurrencia | Detecta la asignación duplicada (`[201, 201]`) cuando se quita el bloqueo |
| Pruebas web en GitHub Actions | En verde en **Chrome, Firefox y WebKit** |
| Prueba de carga 5.2 (50 usuarios, 5 min) | 12.829 peticiones · p50 53 ms · p95 59 ms · p99 66 ms · 0% errores |
| OWASP ZAP | 113 verificaciones superadas · 0 fallas · 1 advertencia menor |
| Bandit | 0 hallazgos abiertos |
| Pruebas móviles (Appium) | 5 de 5 en verde en 2 emuladores: Pixel 6 (Android 14) y Nexus 5 (Android 11) — [ejecución](https://github.com/restrej/prueba-tecnica-cloud-automation-and-mobile/actions/runs/36823127482) |

## Cómo regenerar el PDF

```bash
pip install markdown && npm install mermaid@11
python docs/entregable/build_pdf.py --mermaid node_modules/mermaid/dist/mermaid.min.js
```
