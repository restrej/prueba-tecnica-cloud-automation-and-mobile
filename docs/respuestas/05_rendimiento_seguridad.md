# Parte 5. Pruebas de rendimiento y seguridad

## Ejercicio A: Rendimiento de `orders-api`

**Cálculo de la carga:** pico actual 500 req/min ≈ **8,3 req/s**; con +40% → **700 req/min ≈ 11,7 req/s**.
Se diseña con margen: objetivo de carga = 12 req/s, estrés hasta 4× (≈ 48 req/s).

### 5.1 Plan de pruebas

| Tipo | Objetivo | Configuración (k6) | Métricas a medir | Criterios de aceptación |
|---|---|---|---|---|
| **Carga** | Confirmar que el pico del próximo año (700 req/min) se atiende de forma estable | `ramping-arrival-rate`: subida 5 min a 12 req/s, **meseta 30 min**, bajada 2 min; datos: pedidos únicos sembrados | p50/p95/p99, throughput, % error, instancias de Cloud Run, CPU/memoria, conexiones a Cloud SQL, latencia de Pub/Sub | **p95 < 500 ms, p99 < 1 s, errores < 1%**, sin crecimiento sostenido de latencia |
| **Estrés** | Encontrar el punto de quiebre y verificar recuperación | Escalones de 5 min: 12 → 24 → 36 → 48 req/s y vuelta a 0 | Lo anterior + req/s máximos con p95 < 1 s, tipo de error al saturar (5xx, timeouts, 429), tiempo de recuperación | Degradación **controlada** (429/503 con mensaje, no 500 ni datos corruptos), p95 < 2 s, errores < 5%, recuperación < 2 min; documentar la capacidad máxima |
| **Resistencia (Soak)** | Detectar fugas de memoria, conexiones no liberadas, crecimiento de colas | 9 req/s (pico actual) durante **4 horas** | Memoria por instancia en el tiempo, pool de conexiones, *backlog* de Pub/Sub, p95 por hora, errores | p95 y memoria **estables** (variación < 10% entre la 1.ª y la 4.ª hora), errores < 1%, backlog de Pub/Sub sin crecer |
| **Picos (Spike)** | Simular la apertura simultánea de almacenes a las 7:00 | 2 req/s → **48 req/s en 10 s**, sostener 3 min, bajar en 10 s, observar 3 min | Tiempo de *cold start* y de escalado de Cloud Run, errores durante el salto, p95 | Errores < 2%, p95 < 1,5 s durante el pico, sin 5xx tras 60 s; ajustar `min-instances` si el *cold start* lo impide |

**Herramienta: k6.** Justificación: scripts en JavaScript versionados junto al código y revisables en PR;
**thresholds** que devuelven código de salida ≠ 0 (rompen el pipeline automáticamente); modelo de carga por
**tasa de llegada** (exacto para "N req/min"); muy liviano (miles de VUs en un runner); salida a Prometheus/Grafana
Cloud y a JSON. Frente a **JMeter** (GUI y XML difíciles de versionar/revisar), **Gatling** (Scala/Java, curva mayor)
y **Locust** (Python, buena opción, pero menos eficiente por VU y sin thresholds nativos tan simples).

Implementación: `performance/k6/performance_plan.js` (`-e TEST_TYPE=load|stress|soak|spike`, `-e QUICK=1` para práctica).

### 5.2 Script de carga (50 VUs, 5 min, ramp-up 1 min)

`performance/k6/assign_load_test.js` (extracto):

```javascript
export const options = {
  stages: [
    { duration: '1m', target: 50 },   // ramp-up de 0 a 50 usuarios virtuales
    { duration: '4m', target: 50 },   // 50 usuarios hasta completar 5 minutos
  ],
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],  // med = p50
  thresholds: {
    'http_req_duration{endpoint:assign}': ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],     // tasa de error < 1%
    checks: ['rate>0.99'],
  },
};

export function setup() {                 // una vez: token + pedidos de prueba únicos
  return { token: login(), orderIds: seedOrders(20000) };
}

export default function (data) {          // cada VU, en cada iteración
  const n = exec.scenario.iterationInTest;
  const res = assignOrder(data.token, data.orderIds[n % data.orderIds.length], n);
  assignErrors.add(res.status !== 201);
  sleep(1);                               // think time del supervisor
}
```

**Resultado de la ejecución real** (servicio simulado con 50 ms de latencia artificial de BD):

```text
================ RESULTADO PRUEBA DE CARGA: POST /api/v1/orders/assign ================
Peticiones totales : 12826
Throughput         : 42.59 req/s (2555 req/min)
Tiempo resp. p50   : 53.5 ms
Tiempo resp. p95   : 57.2 ms
Tiempo resp. p99   : 60.9 ms
Tiempo resp. máx   : 111.2 ms
Tasa de error HTTP : 0.00 %
Asignaciones != 201: 0.00 %
VUs máximos        : 50
Umbrales: OK p(95)<500 · OK p(99)<1000 · OK http_req_failed<1% · OK checks>99%
```

> Nota: con 50 VUs y 1 s de *think time* se generan ≈ 2.555 req/min, **5 veces** el pico actual: la prueba
> del enunciado ya cubre holgadamente el +40%.

---

## Ejercicio B: Seguridad

### 5.3 Pruebas de seguridad para `POST /api/v1/orders/assign`

Implementadas en `tests/security/test_assign_security.py` (45 casos) siguiendo OWASP API Security Top 10:

| Área | Pruebas | Esperado |
|---|---|---|
| **Autenticación** | Sin token, token mal formado, firma falsificada, **token expirado**, `alg: none`, payload alterado (rol cambiado) | 401 + `WWW-Authenticate` |
| **Autorización / roles** | Rol `OPERATOR` intenta asignar | 403 |
| **Escalamiento horizontal** | Supervisor de WH-01 asigna en WH-05 (BOLA/IDOR) | 403 |
| **Escalamiento vertical** | *Mass assignment*: enviar `role`, `status`, `assignedBy` extra | 400 (campos extra prohibidos) |
| **Enumeración de usuarios** | Usuario inexistente vs contraseña incorrecta vs usuario bloqueado | Misma respuesta 401 |
| **SQL injection** | `' OR '1'='1`, `; DROP TABLE`, `UNION SELECT` en cada campo | 400, nunca 500 ni 201; sin texto de BD en la respuesta |
| **NoSQL injection** | `{"$ne": null}`, `{"$gt": ""}`, `{"$where": ...}`, arrays | 400 |
| **Command / template injection** | `; ls -la /`, `&& cat /etc/passwd`, `$(curl …)`, `{{7*7}}` | 400 |
| **XSS** | `<script>`, `<img onerror>`, `javascript:`, `"><svg onload>` | 400 y el payload **no se refleja**; `Content-Type: application/json` |
| **Payloads malformados** | JSON cortado, texto, vacío, `null`, array, número gigante, campo de 10.000 caracteres | 400 sin *stack trace* |
| **Content-Type** | `application/xml` | 415 |
| **Headers de seguridad** | CSP (`default-src 'self'`, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, HSTS, `Cache-Control: no-store`, sin `X-Powered-By` | Presentes |
| **CORS** | Preflight desde el origen del Centro de Control vs `https://evil.example` | Sólo el origen confiable; nunca `*` |
| **Rate limiting** | Ráfaga de peticiones de un mismo usuario | 429 + `Retry-After` |

Complementos manuales (por release): pruebas de lógica de negocio con **Burp Suite** (manipular `operatorId` en
tránsito, *replay* de peticiones, *race conditions* con *Turbo Intruder*), revisión de logs (que no contengan tokens).

### 5.4 Herramientas automatizadas y su lugar en el pipeline

| Tipo | Herramienta | Etapa | Política |
|---|---|---|---|
| **SAST** | **Semgrep** (reglas OWASP Top 10), **Bandit** (Python), reglas `S` de Ruff; CodeQL como alternativa nativa de GitHub | **Pull Request** (≈ 1–2 min) | Bloquea con hallazgos *High*; los demás generan comentario |
| **Secretos** | Gitleaks / GitHub secret scanning con *push protection* | **Pre-commit + PR** | Bloquea siempre |
| **SCA** | **pip-audit**, Dependabot, Trivy (imagen Docker) | PR + build de imagen | Bloquea CVE *Critical/High* con fix disponible |
| **DAST** | **OWASP ZAP** (API scan con OpenAPI y token de servicio) | **Merge a main** contra staging (baseline, ≈ 5 min) y **Release Candidate** (full scan) | Bloquea reglas marcadas `FAIL` (inyección, XSS, path traversal) en `security/zap/zap-rules.tsv` |
| **Pentest manual** | **Burp Suite Professional** | Antes de releases mayores / trimestral | Hallazgos críticos bloquean el release |
| **Pruebas de seguridad propias** | pytest (`-m security`) | PR / merge | Tests `@critical` bloquean |

**¿ZAP o Burp Suite?** Burp Suite es el estándar de los pentesters para **pruebas manuales** (proxy, *Repeater*,
*Intruder*); su escáner automático y la integración con CI requieren licencias de pago. **OWASP ZAP** es gratuito,
tiene imágenes Docker y scripts listos para CI (`zap-api-scan.py`). Recomendación: **ZAP automatizado en el pipeline**
+ **Burp para exploración manual** por parte de QA/seguridad.

**Resultado real del escaneo ZAP** sobre la API simulada: **113 reglas PASS, 0 FAIL, 1 WARN**
(*Unexpected Content-Type* en respuestas 404). Reporte: `reports/security/zap-report.html` (artefacto del job `dast-zap`).
