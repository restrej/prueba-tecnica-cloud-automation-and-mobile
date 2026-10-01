# Parte 6. Cloud y troubleshooting

## 6.1 Escenario 1: aumento de 500 tras el despliegue de `orders-api`

**Hipótesis inicial:** Cloud Run escala bien y los logs muestran *timeouts* hacia `inventory-service`; el despliegue
probablemente cambió algo en la **llamada a inventory** (timeout, reintentos, pool de conexiones, nueva consulta) o
inventory se degradó por el **aumento de carga** que genera la nueva versión (p. ej. reintentos agresivos que multiplican las peticiones).

### Herramientas de GCP y orden de uso

| # | Herramienta | Para qué | Qué busco |
|---|---|---|---|
| 1 | **Cloud Monitoring** | Confirmar el **alcance** y la **correlación temporal** | ¿Los 5xx empiezan exactamente con la nueva revisión? Comparar por `revision_name`; latencia p95/p99 de orders-api **y** de inventory-service; CPU, memoria, instancias y concurrencia de inventory; conexiones a Cloud SQL |
| 2 | **Error Reporting** | Ver **qué** errores son nuevos | Grupos de excepciones nuevos desde el despliegue (`TimeoutError`, `ConnectionPool exhausted`), versión donde aparecen por primera vez |
| 3 | **Cloud Logging** | Detalle y **patrón** de los fallos | Endpoints afectados, duración de los timeouts (¿siempre 5 s? = timeout configurado), ¿todas las instancias o algunas?, ¿algún almacén o pedido en particular? |
| 4 | **Cloud Trace** | **Dónde** se va el tiempo dentro de una petición | Spans de orders-api → inventory-service → Cloud SQL; ¿la latencia está en la red, en inventory o en su consulta a la BD? ¿hay N llamadas por petición (N+1)? |

Paso previo: revisar el **diff del despliegue** (código y configuración: timeouts, variables de entorno, `max-instances`,
`concurrency`, conector VPC, versión de librerías). Mitigación inmediata si el impacto es alto: **rollback** de tráfico
a la revisión anterior (`gcloud run services update-traffic orders-api --to-revisions=PREV=100`) e investigar después.

### Filtros de logs (Cloud Logging Query Language)

```text
# 1) Errores 5xx de orders-api desde el despliegue, por revisión
resource.type="cloud_run_revision"
resource.labels.service_name="orders-api"
httpRequest.status>=500
timestamp>="2025-10-15T14:00:00Z"

# 2) Timeouts hacia inventory-service
resource.labels.service_name="orders-api"
severity>=WARNING
(textPayload:"inventory-service" OR jsonPayload.message:"inventory") AND
(textPayload:"timeout" OR jsonPayload.message:"timeout" OR jsonPayload.error:"DeadlineExceeded")

# 3) Lado inventory: peticiones lentas o rechazadas
resource.labels.service_name="inventory-service"
(httpRequest.latency>"3s" OR httpRequest.status>=500 OR httpRequest.status=429)

# 4) Todo lo de UNA petición en todos los servicios (correlación por trace)
trace="projects/logitrack-prod/traces/4bf92f3577b34da6a3ce929d0e0e4736"

# 5) Comparar revisiones
resource.labels.service_name="orders-api" httpRequest.status>=500
resource.labels.revision_name="orders-api-00042-xyz"
```

Útil además: **Log Analytics** (SQL sobre logs) para agrupar `COUNT(*)` de 5xx por `revision_name`, endpoint y minuto.

### Correlación entre microservicios

1. **Trace context**: Cloud Run propaga `traceparent`/`X-Cloud-Trace-Context`; cada servicio lo reenvía en sus llamadas
   salientes y en los **atributos de los mensajes Pub/Sub**, y escribe en cada log el campo
   `logging.googleapis.com/trace` (el servicio simulado ya lo hace: `sut/main.py`). Así un `trace=…` muestra la petición
   completa en todos los servicios.
2. **Correlation/Request ID** de negocio (`X-Request-ID`, `orderId`) en todos los logs estructurados (JSON).
3. **Cloud Trace** para ver la cascada de spans y detectar el servicio lento.
4. **Alinear series de tiempo** en un mismo dashboard: 5xx de orders-api vs p99 de inventory vs conexiones de Cloud SQL
   vs *backlog* de Pub/Sub.
5. Confirmar la relación con la queja de PickApp: la app llama a orders-api → la lentitud de los operadores es el
   mismo timeout visto desde el cliente (Firebase Performance Monitoring / Crashlytics en la app).

### Dashboards y alertas proactivas

| Señal | Alerta (Cloud Monitoring) |
|---|---|
| **Tasa de 5xx** por servicio y revisión | > 1% durante 5 min → página al on-call |
| **Latencia p95/p99** por servicio y endpoint | p95 > 500 ms (o > 2× la línea base) durante 10 min |
| **SLO de disponibilidad** (99,9%) con **burn rate** | Burn rate > 14× en 1 h (rápida) y > 6× en 6 h (lenta) |
| **Errores/timeouts en llamadas salientes** (métrica basada en logs: `inventory timeout`) | > 10/min |
| Instancias, CPU, memoria, **concurrencia** de Cloud Run | Instancias al `max-instances` > 5 min |
| **Cloud SQL**: conexiones activas, CPU, *lock waits* | Conexiones > 80% del máximo |
| **Pub/Sub**: `oldest_unacked_message_age`, *dead-letter* | Mensaje sin procesar > 5 min |
| **Uptime checks / monitoreo sintético** del flujo de asignación | 2 fallos consecutivos |
| Métrica de negocio: **asignaciones por minuto** | Caída > 30% vs misma hora de la semana anterior |
| Comparación por revisión tras despliegue | Alimenta el **rollback automático** del canary |

## 6.2 Escenario 2: E2E que falla 3 de cada 10 ejecuciones

### Proceso paso a paso

1. **Recolectar evidencia sin cambiar nada:** ejecutar el test 30–50 veces (mismo commit, mismo ambiente) y guardar
   para cada ejecución: JUnit, logs de Appium, capturas/video, logs del backend por `trace`/`X-Request-ID`, hora y
   dispositivo. `tools/flaky_report.py` calcula la tasa de fallo.
2. **Clasificar los fallos:** ¿fallan siempre en el **mismo paso** y con el **mismo error**? ¿coinciden con horarios,
   dispositivos, *runners* o ejecución en paralelo?
3. **Reproducir aislando variables:** ejecutar solo (sin paralelismo), con otro dispositivo, contra un ambiente
   dedicado, con red estable vs red degradada.
4. **Aplicar el árbol de decisión** de abajo.
5. **Corregir la causa raíz**, ejecutar 50 veces seguidas en verde y documentar en el ticket. Mientras tanto, el test
   va a **cuarentena** (6.3).

| Sospecha | Cómo lo confirmo | Cómo lo resuelvo |
|---|---|---|
| **Test flaky** (problema del test) | Patrones en el código: `sleep` fijos, esperas implícitas mezcladas con explícitas, locators por XPath/índice/texto, datos compartidos entre tests (mismo `orderId`), dependencia del orden de ejecución, verificación inmediata tras una operación asíncrona (Pub/Sub → Firestore), estado residual de la app (`noReset=true`) | Esperas explícitas por **condición de negocio** (polling hasta que la API devuelva `ASSIGNED`), datos únicos por test creados por API, `data-testid`/Semantics, app limpia por sesión, desactivar animaciones, test idempotente e independiente |
| **Race condition** (bug del sistema) | El backend muestra **dos operaciones concurrentes** sobre el mismo pedido (logs con el mismo `orderId` y timestamps cercanos); el fallo aumenta al ejecutar en paralelo o con latencia artificial; prueba dirigida con `threading.Barrier` (como `test_assign_concurrency.py`), y `ASSIGNMENT_LOCK_ENABLED=false` demuestra el efecto | Es un **defecto del producto**, no del test: bloqueo por fila / `UNIQUE` en BD, idempotency keys, consumidores Pub/Sub idempotentes, lecturas *read-your-writes*. El test se mantiene como detector |
| **Infraestructura** | Correlacionar los fallos con métricas: *cold starts* y escalado de Cloud Run, CPU/memoria del emulador o *runner* de CI, latencia y errores de red, conexiones de Cloud SQL, *backlog* de Pub/Sub, `oldest_unacked_message_age`, *throttling* (429) de servicios externos, salud de la granja de dispositivos | `min-instances` en el ambiente de pruebas, *runners* con KVM y recursos suficientes, ambiente de pruebas dedicado, *health check* previo a la suite, reintento **sólo** de pasos de infraestructura (instalar app, crear sesión) |
| **Timeout mal configurado** | Los fallos son `TimeoutException` justo en el límite (p. ej. siempre 10 s) y la operación termina **poco después** (el log del backend muestra éxito en 11–12 s); la distribución de tiempos (p95/p99) del paso supera el timeout | Timeouts basados en datos: **p99 del paso + margen** (p. ej. 1,5×); timeouts **por tipo de operación** (UI 10 s, propagación asíncrona 30 s con polling), configurables por ambiente (`MOBILE_WAIT_TIMEOUT`), alineados entre cliente HTTP, Appium (`newCommandTimeout`) y backend. Si el p99 real es inaceptable, es un **defecto de rendimiento** |

## 6.3 Gestión de tests flaky (sin bloquear el pipeline y sin ignorarlos)

Estrategia implementada en el repositorio:

1. **Detección automática:** job nocturno que ejecuta la suite N veces y `tools/flaky_report.py`, que clasifica cada
   test: *estable*, **FLAKY** (falla a veces) o **ROTO** (falla siempre). También `pytest-rerunfailures` registra los
   tests que pasaron **sólo tras reintento** (son flaky aunque el pipeline esté verde).
2. **Política de reintentos acotada:** máximo **1 reintento** (`--reruns 1`) en el pipeline de PR/merge, siempre
   visible en el reporte. Nunca reintentos en tests unitarios. Un test que necesita reintento queda marcado.
3. **Cuarentena:** si la tasa de fallo es > 5% (o > 2 reintentos en una semana), se marca `@pytest.mark.quarantine`.
   El pipeline principal ejecuta `-m "not quarantine"`; el job `quarantine` lo sigue ejecutando con
   `continue-on-error: true` (**no bloquea** pero se ve en cada ejecución).
4. **Reglas para que no se ignoren:** cada test en cuarentena tiene **ticket, responsable y fecha límite** (SLA de 2
   sprints); máximo **5% de la suite** en cuarentena (si se supera, se para a estabilizar); los tests **críticos**
   no pueden quedar en cuarentena más de 48 h sin cubrir su riesgo con otra prueba o una verificación manual.
5. **Reportería:** tablero semanal con tasa de flakiness por suite, top 10 tests inestables, tiempo medio en
   cuarentena y tendencia (meta < 2%). Se publica en el resumen del pipeline (`$GITHUB_STEP_SUMMARY`) y en el
   informe de calidad.
6. **Salida de cuarentena:** tras corregir la causa raíz, 50 ejecuciones seguidas en verde → se quita el marker.

Evidencia (`tests/quarantine/test_flaky_demo.py` ejecutado 10 veces):

```text
## Reporte de flakiness (10 ejecuciones)
| Test                                                     | Pasó | Falló | Tasa de fallo | Clasificación                 |
| tests.quarantine.test_flaky_demo::test_flaky_assignment… | 7    | 3     | 30%           | FLAKY -> cuarentena + ticket  |
```
