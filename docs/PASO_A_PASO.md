# Paso a paso: instalar, entender y ejecutar todo

Esta guía asume que **nunca has ejecutado este proyecto**. Sigue los pasos en orden.
Cada paso dice: **qué hace**, **el comando** y **qué deberías ver**.

> Convención: los comandos que empiezan con `$` se escriben en una terminal
> (no escribas el `$`). En Windows usa **PowerShell**.

---

## Paso 0. Qué es este proyecto (en 1 minuto)

La prueba técnica habla de una empresa ficticia, **LogiTrack**. Como su sistema no existe,
este repositorio trae **una versión simulada y pequeña** de su API (`sut/`) para que todas
las pruebas se puedan ejecutar de verdad.

```
Tú ejecutas  ──►  pytest / k6 / ZAP  ──►  API simulada de LogiTrack (sut/)
                     (las pruebas)          (el "sistema bajo prueba")
```

| Carpeta | Qué contiene | Parte del PDF |
|---|---|---|
| `sut/` | API simulada `orders-api` + pantalla web de login | (soporte) |
| `framework/` | Código reutilizable: cliente de API, Page Objects, Screen Objects | 4 |
| `tests/unit` | Pruebas unitarias | 1.1 |
| `tests/integration` | Pruebas de integración (API + Pub/Sub simulado) | 1.1 |
| `tests/contract` + `contracts/` | Pruebas de contrato (JSON Schema) | 1.1, Bonus B.2 |
| `tests/api` | Ejercicio A: pruebas de la API `/orders/assign` | 4-A |
| `tests/ui` | Ejercicio B: pruebas web con Playwright | 4-B |
| `tests/mobile` + `mobile-app/` | Ejercicio C: Appium + app Flutter demo | 4-C |
| `tests/security` + `security/` | Pruebas de seguridad + OWASP ZAP | 5.3, 5.4 |
| `performance/k6` | Pruebas de rendimiento con k6 | 5.1, 5.2 |
| `tests/quarantine` + `tools/` | Tests flaky, quality gate, reporte de flakiness | 3.3, 6.3 |
| `.github/workflows` | Pipelines de GitHub Actions | 3.3 |
| `docs/` | Guías y respuestas del PDF | todas |

---

## Paso 1. Instalar los programas necesarios

| Programa | ¿Para qué? | ¿Obligatorio? | Cómo verificar |
|---|---|---|---|
| **Python 3.11 o superior** | Ejecutar la API y las pruebas | Sí | `python --version` |
| **Git** | Descargar el repositorio | Sí | `git --version` |
| **k6** | Pruebas de rendimiento | Para el paso 11 | `k6 version` |
| **Docker Desktop** | Escaneo de seguridad con OWASP ZAP | Para el paso 12 | `docker --version` |
| **Flutter + Android Studio + Node.js** | Pruebas mobile | Para el paso 13 | `flutter --version`, `node --version` |

Instalación de k6: <https://grafana.com/docs/k6/latest/set-up/install-k6/>
(Windows: `winget install k6 --source winget` · macOS: `brew install k6`).

---

## Paso 2. Descargar el proyecto

```bash
$ git clone https://github.com/restrej/prueba-tecnica-cloud-automation-and-mobile.git
$ cd prueba-tecnica-cloud-automation-and-mobile
```

---

## Paso 3. Crear el entorno virtual e instalar dependencias

Un **entorno virtual** (`.venv`) es una carpeta con un Python "aislado" para este
proyecto, así sus librerías no se mezclan con las de otros proyectos.

**macOS / Linux**
```bash
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
$ python -m playwright install chrome firefox webkit
```

**Windows (PowerShell)**
```powershell
$ python -m venv .venv
$ .venv\Scripts\Activate.ps1
$ pip install -r requirements.txt
$ python -m playwright install chrome firefox webkit
```

✅ **Deberías ver** `(.venv)` al inicio de la línea de la terminal.
La última línea descarga los 3 navegadores de las pruebas web: **Google Chrome**, **Firefox** y **WebKit** (el motor de Safari).

> Si PowerShell no deja activar el entorno: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
> **Cada vez que abras una terminal nueva** debes volver a activar el entorno (`source .venv/bin/activate`).

---

## Paso 4. Levantar la API simulada y explorarla (opcional, pero recomendado)

```bash
$ uvicorn sut.main:app --port 8000
```

✅ Deberías ver `Uvicorn running on http://127.0.0.1:8000`. Ahora abre en el navegador:

- <http://localhost:8000/docs> → documentación interactiva. Puedes probar el endpoint
  `POST /api/v1/auth/login` con `{"username": "supervisor1", "password": "Sup3rvisor!2025"}`.
- <http://localhost:8000/control/login> → la pantalla de login del "Centro de Control".

Usuarios de prueba:

| Usuario | Contraseña | Rol | Para qué se usa |
|---|---|---|---|
| `supervisor1` | `Sup3rvisor!2025` | SUPERVISOR | Usuario principal de las pruebas |
| `supervisor2` | `Sup3rvisor!2025` | SUPERVISOR | Segundo supervisor (prueba de concurrencia) |
| `supervisor.wh01` | `Sup3rvisor!2025` | SUPERVISOR solo de WH-01 | Escalamiento de privilegios |
| `operator1` | `0perator!2025` | OPERATOR | Rol sin permiso para asignar |
| `admin` | `Adm1n!2025` | ADMIN | Administrador |

Para detenerla: `Ctrl + C`.

> **No necesitas dejarla corriendo para las pruebas**: `pytest` la levanta y la apaga solo
> (ver `tests/conftest.py`). Para probar contra otro ambiente: `BASE_URL=https://... pytest`.

---

## Paso 5. Pruebas UNITARIAS (la base de la pirámide)

```bash
$ pytest tests/unit -v
```

✅ Deberías ver ~32 pruebas en verde (`PASSED`) en unos segundos.
**Qué prueban:** las reglas de negocio de la asignación (sin red ni servidor) y las utilidades
de seguridad (tokens, contraseñas y rate limiter).

---

## Paso 6. Integración + contrato + COBERTURA (coverage gate)

```bash
$ pytest tests/unit tests/integration tests/contract --cov --cov-report=term-missing
```

✅ Al final deberías ver una tabla de cobertura y la línea
`Required test coverage of 80.0% reached`. Si la cobertura bajara del 80%, el comando fallaría:
eso es un **coverage gate**.

---

## Paso 7. Pruebas de API (Parte 4, Ejercicio A)

```bash
$ pytest tests/api -v
```

✅ ~40 pruebas en verde: casos positivos (3 prioridades), negativos (token, pedido,
operador, almacén), límite (vacíos, formatos, ya asignado) y **concurrencia**.

**Experimento recomendado:** demuestra que la prueba de concurrencia sí detecta el bug
de "asignaciones duplicadas" desactivando el bloqueo del servidor:

```bash
# macOS/Linux
$ ASSIGNMENT_LOCK_ENABLED=false pytest tests/api/test_assign_concurrency.py
# Windows PowerShell
$ $env:ASSIGNMENT_LOCK_ENABLED="false"; pytest tests/api/test_assign_concurrency.py; Remove-Item Env:ASSIGNMENT_LOCK_ENABLED
```

✅ Ahora **debe fallar** con `assert [201, 201] == [201, 409]`: los dos supervisores
"ganaron" el mismo pedido. Así se ve una condición de carrera.

---

## Paso 8. Pruebas de SEGURIDAD (Parte 5.3)

```bash
$ pytest tests/security -v
```

✅ ~45 pruebas: tokens expirados/falsificados, roles, escalamiento de privilegios,
SQL/NoSQL/command injection, XSS, payloads malformados, headers de seguridad, CORS y rate limiting.

---

## Paso 9. Pruebas de UI web con Playwright (Parte 4, Ejercicio B)

```bash
$ pytest tests/ui --browser-channel chrome          # en Google Chrome
$ pytest tests/ui --browser firefox                 # en Firefox
$ pytest tests/ui --browser webkit                  # en WebKit (motor de Safari)
$ pytest tests/ui --browser-channel chrome --headed --slowmo 500   # VIENDO Chrome, en cámara lenta
```

El código de las pruebas es el mismo para los 3 navegadores; sólo cambia la opción del comando.
En GitHub Actions los 3 se ejecutan en paralelo (job `UI web` en `ci.yml`).

✅ 18 pruebas: login exitoso, credenciales inválidas, validaciones de campos, longitud
máxima, enlace "¿Olvidaste tu contraseña?", etc.

---

## Paso 10. Reportes, tests críticos y quality gate

Genera un **reporte HTML** de todo lo funcional:

```bash
$ pytest -m "not quarantine and not mobile" --html=reports/reporte.html --self-contained-html --junitxml=reports/junit.xml
```

Abre `reports/reporte.html` en el navegador.

Ahora aplica el **quality gate** (la regla que decide si el pipeline pasa o se bloquea):

```bash
$ python tools/quality_gate.py "reports/junit.xml"
```

✅ Verás `Quality Gate: ✅ APROBADO`. Si un test marcado `@pytest.mark.critical` fallara,
verías `❌ BLOQUEADO` y el comando terminaría con código 1 (en CI eso pone el pipeline en rojo).

Ejecutar **solo los tests críticos** o **solo el smoke**:
```bash
$ pytest -m critical
$ pytest -m smoke
```

### Demo de tests flaky (Parte 6.3)

`tests/quarantine/test_flaky_demo.py` falla a propósito ~3 de cada 10 veces.

```bash
# macOS/Linux: ejecutarlo 10 veces y generar el reporte de flakiness
$ for i in $(seq 1 10); do pytest tests/quarantine -q --junitxml=reports/flaky/run-$i.xml; done
$ python tools/flaky_report.py "reports/flaky/*.xml"
```
```powershell
# Windows PowerShell
$ 1..10 | ForEach-Object { pytest tests/quarantine -q --junitxml=reports/flaky/run-$_.xml }
$ python tools/flaky_report.py "reports/flaky/*.xml"
```

✅ Verás una tabla con `Pasó 7 | Falló 3 | 30% | FLAKY -> cuarentena + ticket` (los números varían).

---

## Paso 11. Rendimiento con k6 (Parte 5)

En una terminal deja la API corriendo **con el rate limit alto** (queremos medir la API, no el limitador):

```bash
# macOS/Linux
$ RATE_LIMIT_PER_MINUTE=1000000 uvicorn sut.main:app --port 8000
# Windows PowerShell
$ $env:RATE_LIMIT_PER_MINUTE="1000000"; uvicorn sut.main:app --port 8000
```

En **otra terminal**:

```bash
$ k6 run -e QUICK=1 performance/k6/assign_load_test.js   # versión de práctica: 1 minuto
$ k6 run performance/k6/assign_load_test.js              # versión del PDF (5.2): 50 VUs, 5 minutos
```

✅ Al final verás el bloque `RESULTADO PRUEBA DE CARGA` con p50, p95, p99, throughput y tasa
de error, y los umbrales con `OK` o `FALLA`. También queda en `reports/k6/`.

Plan completo (5.1): `-e TEST_TYPE=load | stress | soak | spike` (agrega `-e QUICK=1` para practicar):
```bash
$ k6 run -e TEST_TYPE=spike -e QUICK=1 performance/k6/performance_plan.js
```

---

## Paso 12. Análisis de seguridad automático: SAST y DAST (Parte 5.4)

**SAST** (revisa el código sin ejecutarlo):
```bash
$ ruff check .                                         # calidad + reglas de seguridad
$ bandit -r sut framework tools -c pyproject.toml      # SAST de Python
$ pip-audit -r requirements.txt                        # dependencias con vulnerabilidades conocidas
```

**DAST** (ataca la API en ejecución). Con la API corriendo (paso 11) y Docker abierto:
```bash
$ bash security/zap/run_zap_scan.sh http://localhost:8000
```
✅ Abre `reports/security/zap-report.html`. (En Windows ejecútalo desde **Git Bash**.)

---

## Paso 13. Pruebas MOBILE con Appium (Parte 4, Ejercicio C)

Esta parte necesita un emulador Android, así que tiene más requisitos.

1. Instala **Android Studio**, crea un emulador (Device Manager → *Create device* → Pixel 6, Android 14) y arráncalo.
2. Instala **Flutter** (<https://docs.flutter.dev/get-started/install>) y verifica con `flutter doctor`.
3. Prueba la app sin emulador (pruebas de widgets):
   ```bash
   $ cd mobile-app
   $ flutter pub get
   $ flutter test
   ```
4. Compila el APK:
   ```bash
   $ flutter build apk --debug
   $ cd ..
   ```
5. Instala y arranca **Appium** (requiere Node.js), en otra terminal:
   ```bash
   $ npm install -g appium
   $ appium driver install uiautomator2
   $ appium --allow-insecure=adb_shell
   ```
6. Ejecuta las pruebas (con el entorno virtual activo):
   ```bash
   $ pytest tests/mobile -v
   ```

✅ Verás la app abrirse sola en el emulador: login → pedido → escaneo → guía generada.
Si Appium no está corriendo, las pruebas aparecen como `SKIPPED` con un mensaje explicando por qué.

Datos de la app demo: usuario `OP-312`, contraseña `Pick2025!`, códigos de barras
`7501234567890` y `7501234567891` (pedido ORD-2025-007841).

---

## Paso 14. CI/CD en GitHub Actions (Parte 3)

Los pipelines están en `.github/workflows/`:

| Archivo | Cuándo corre | Qué hace |
|---|---|---|
| `ci.yml` | Cada Pull Request y cada push a `main` | Lint, SAST, SCA, unit + cobertura, API/seguridad/UI, quality gate, k6 corto, ZAP, cuarentena, Slack |
| `mobile.yml` | Manual, cada noche y en tags `rc-*` | Flutter tests + Appium en 2 emuladores |
| `performance.yml` | Manual o semanal | Pruebas k6 completas |

Para verlos: en GitHub entra a la pestaña **Actions**. Cada ejecución publica los
reportes en la sección **Artifacts** (abajo en la página de la ejecución).

**Configurar la notificación de Slack (opcional):**
1. En Slack crea un *Incoming Webhook* (<https://api.slack.com/messaging/webhooks>).
2. En GitHub: *Settings → Secrets and variables → Actions → New repository secret*,
   nombre `SLACK_WEBHOOK_URL`, valor = la URL del webhook.

**Proteger la rama main (Parte 3.2):** *Settings → Branches → Add branch protection rule* →
`main` → marcar *Require a pull request before merging*, *Require approvals (1)*,
*Require status checks to pass* y elegir los checks `Lint + SAST + SCA`,
`Unit + Integration + Contract (coverage gate)` y `API + Security + UI (Playwright)`.

---

## Resumen de comandos

| Quiero... | Comando |
|---|---|
| Correr todo lo que no necesita emulador | `pytest -m "not quarantine and not mobile"` |
| Sólo unitarias | `pytest tests/unit` |
| Sólo API | `pytest -m api` |
| Sólo seguridad | `pytest -m security` |
| Sólo UI, viendo el navegador | `pytest tests/ui --headed` |
| Sólo críticas / smoke | `pytest -m critical` / `pytest -m smoke` |
| Cobertura | `pytest tests/unit tests/integration tests/contract --cov` |
| Rendimiento | `k6 run -e QUICK=1 performance/k6/assign_load_test.js` |
| SAST | `bandit -r sut framework tools -c pyproject.toml` |
| DAST | `bash security/zap/run_zap_scan.sh` |
| Mobile | `pytest tests/mobile` (con Appium + emulador) |
