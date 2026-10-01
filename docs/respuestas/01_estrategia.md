# Parte 1. Estrategia de calidad y factibilidad de automatización

## 1.1 Estrategia de pruebas para el flujo principal

Flujo: *Pedido recibido → orders-api → Pub/Sub → inventory-service (reserva stock) → asignación a operador (PickApp) → escaneo → shipping-service (guía) → notifications-service → entrega.*

Principio rector: **pirámide de pruebas** (muchas pruebas rápidas y baratas abajo, pocas lentas y costosas arriba) y **shift-left** (detectar el defecto lo antes posible, donde es más barato corregirlo). Los 4 problemas actuales se asignan explícitamente al nivel que mejor los detecta.

| Nivel | Qué valida | Herramientas | Riesgos que cubre |
|---|---|---|---|
| **Unit Tests** | Reglas de negocio aisladas: asignación (roles, almacén, estado del pedido, idempotencia), cálculo de reserva de stock, validación de SKUs escaneados, generación de guía. En la app: widgets y lógica de estado (BLoC/Provider). | pytest (servicios Python) / JUnit-Jest según stack; `flutter test` para PickApp; Jasmine/Jest para Angular | Pedidos sin stock que avanzan (regla "sólo READY_FOR_ASSIGNMENT"), asignación por rol no autorizado, cálculos erróneos. Feedback en segundos. |
| **Integration Tests** | Un servicio con sus dependencias **reales o emuladas**: API ↔ Cloud SQL (transacciones, bloqueos de fila), API → Pub/Sub (mensaje publicado y consumido), Cloud Function ↔ Firestore. | pytest + Testcontainers (PostgreSQL), **emulador de Pub/Sub y de Firestore** (gcloud emulators), TestClient | **Asignaciones duplicadas** (concurrencia contra BD real con `SELECT … FOR UPDATE`/constraint UNIQUE), mensajes perdidos o duplicados en Pub/Sub (idempotencia del consumidor), dashboards desactualizados (Firestore no actualizado tras el evento). |
| **Contract Tests** | El **formato acordado** entre productor y consumidor: PickApp/Angular ↔ orders-api (OpenAPI), orders-api → Pub/Sub (esquema del evento), orders-api ↔ e-commerce externo. | **Pact** (consumer-driven) + Pact Broker; JSON Schema / Pub/Sub Schemas para eventos | Cambios de API que rompen la app mobile ya instalada en los dispositivos, eventos con campos renombrados que inventory-service no entiende. |
| **End-to-End Tests** | Flujos críticos completos en un ambiente integrado (staging): pedido → reserva → asignación → escaneo → guía → notificación; dashboard en tiempo real. | Playwright (Centro de Control), Appium (PickApp), pytest + API para preparar datos y verificar backend | Integración real entre los 5 microservicios, **errores intermitentes al escanear**, dashboard que no refleja el estado (verificación con polling sobre la UI). |
| **UAT** | Que la solución sirve al trabajo real: supervisores y operadores ejecutan escenarios de negocio en staging con dispositivos y **scanners físicos** reales. | Guiones de UAT en TestRail/Xray, sesiones exploratorias, checklist de aceptación | Usabilidad en almacén (guantes, luz, velocidad de escaneo), reglas de negocio mal interpretadas, hardware real (impresoras, scanners). |

### ¿Qué se ejecuta en cada etapa del pipeline?

| Etapa | Pruebas | Tiempo objetivo | Justificación (tiempo / costo) |
|---|---|---|---|
| **Pull Request** | Lint, SAST (Bandit/Semgrep), SCA (pip-audit/Dependabot), **unit**, **contract** (verificación del proveedor contra los pacts), integración ligera con emuladores, widget tests de Flutter; coverage gate sobre código nuevo | **≤ 10 min** | Se ejecuta decenas de veces al día: debe ser rápido y barato (runners estándar, sin ambientes). Corregir aquí cuesta minutos. |
| **Merge a main** | Todo lo anterior + integración completa (Testcontainers + emuladores), despliegue a **dev/staging**, **API + seguridad + UI web** (smoke y regresión crítica), k6 smoke, DAST baseline (ZAP) | **≤ 25 min** | Valida la integración real una vez por cambio aceptado. Requiere un ambiente efímero o compartido (costo moderado). |
| **Release Candidate** | Regresión E2E completa web + **mobile en matriz de dispositivos**, DAST completo, **pruebas de rendimiento** (carga +40%, spike), contratos con e-commerce, **UAT** con usuarios | **2–4 h** + UAT (1–2 días) | Es la última barrera antes del cliente. Lo más costoso (granja de dispositivos, ambientes tipo producción, horas de personas) se concentra aquí, sólo una vez por release. |
| **Producción** | Smoke post-deploy, **canary** con análisis automático de métricas, **monitoreo sintético** (journeys cada 5 min), alertas SLO | **5–15 min** por despliegue + continuo | Detecta lo que sólo ocurre con datos y tráfico reales. Costo bajo y continuo; reduce MTTR. |

**Costo relativo** (estimado): unit ≈ 1x · integración ≈ 5x · contrato ≈ 2x · API ≈ 5x · E2E web ≈ 20x · E2E mobile ≈ 40x (dispositivos, mantenimiento de locators) · UAT ≈ 100x (horas de usuarios). Por eso la distribución objetivo es ~70% unit, ~20% integración/contrato/API y ~10% E2E.

---

## 1.2 Factibilidad de automatización de PickApp (Flutter)

Premisas técnicas: (1) Flutter dibuja su propia UI; la automatización necesita **Semantics identifiers** (o el driver de Flutter); (2) el **scanner físico** funciona en modo *keyboard wedge* o por *intent* (Zebra DataWedge), y ambos se pueden **simular** en un emulador, pero la óptica real no; (3) las impresoras requieren hardware.

| # | Módulo | ¿Automatizable? | Complejidad | Limitaciones técnicas | Prioridad |
|---|---|---|---|---|---|
| 1 | Pedidos Asignados | **Sí** | Baja | Requiere datos de prueba sembrados por API y sincronización con Firestore (esperas por condición, no `sleep`). | **Alta** (P1): puerta de entrada al flujo crítico |
| 2 | Preparación de Pedido | **Parcial** | Alta | El escaneo se simula (inyección de texto + ENTER o broadcast de intent); **no** se puede automatizar la óptica (códigos dañados, reflejos, distancia) ni la ergonomía. Es donde ocurren los "errores intermitentes al escanear": la lógica sí se automatiza. | **Alta** (P1): flujo de mayor valor y mayor tasa de defectos |
| 3 | Despacho | **Parcial** | Media | La generación de guía se valida por API/UI; la **impresión** física de la etiqueta no (se valida con impresora virtual/mock del SDK). | **Alta** (P1) |
| 4 | Gestión de Usuarios | **Sí** | Baja | Formularios CRUD estándar; mejor cubrir la mayor parte **por API** y dejar 1–2 casos de UI. | Media (P2) |
| 5 | Gestión de Insumos | **Sí** | Baja | CRUD; bajo riesgo de negocio. | Baja (P3) |
| 6 | Dashboards | **Parcial** | Media | Los datos se validan por API; la parte visual (gráficos dibujados en canvas) se valida con aserciones sobre valores/semantics o *golden tests* de Flutter, no con Appium. | Media (P2) |
| 7 | Alertas y Notificaciones | **Parcial** | Alta | Las push (FCM) dependen del SO y de servicios externos: se valida la generación del evento por API y la recepción en emulador con FCM de prueba; la presentación nativa varía por dispositivo. | Media (P2) |
| 8 | Login / Autenticación | **Sí** | Baja | Si usa SSO corporativo con MFA, se usan usuarios de prueba sin MFA o *token injection* en ambientes de prueba. | **Alta** (P1): bloquea todo lo demás |
| 9 | Configuración de Impresoras | **No** (E2E) / Parcial (lógica) | Alta | Bluetooth/Wi-Fi con hardware real; el emulador no tiene Bluetooth. Se automatiza sólo la lógica con un *mock* del SDK de la impresora; el resto es manual en dispositivo físico. | Baja (P3): cambia poco, se prueba manualmente por release |

**Justificación.** Se prioriza por **riesgo × frecuencia de uso × estabilidad**: los módulos 1, 2, 3 y 8 forman el flujo de ingresos diario y concentran los defectos reportados. Que la app esté en Flutter no impide automatizar, pero **exige acordar con desarrollo** que cada widget relevante tenga `Semantics(identifier: …)` (equivalente al `data-testid` web), y complementar con `integration_test` de Flutter para lógica de UI. El hardware (scanner, impresora) se aísla detrás de interfaces que se pueden simular en pruebas y se valida físicamente en un conjunto pequeño de pruebas manuales por release.

---

## 1.3 Métricas de calidad

| Métrica | Fórmula | Meta / umbral | Frecuencia |
|---|---|---|---|
| **Defect Leakage** | defectos encontrados en producción ÷ (defectos en pre-producción + en producción) × 100 | **< 5%** (alerta si > 10%) | Por release y tendencia mensual |
| **Test Coverage** | (a) Código: líneas/ramas ejecutadas ÷ totales × 100. (b) Requisitos: requisitos con ≥1 prueba ÷ requisitos totales × 100 | Código **≥ 80%** (≥ 90% en código nuevo); regresión automatizada ≥ 70% de flujos críticos | Cada PR (código); quincenal (requisitos) |
| **Change Failure Rate** (DORA) | despliegues que causan incidente, rollback o hotfix ÷ despliegues totales × 100 | **< 15%** (élite < 5%) | Semanal, tendencia mensual |
| **MTTR** (DORA) | Σ (hora de restauración − hora de detección) ÷ número de incidentes | **< 1 hora** para P1; < 4 h para P2 | Por incidente; reporte mensual |
| **Tasa de flakiness** | ejecuciones con resultado distinto sin cambio de código ÷ ejecuciones totales × 100 (por test y por suite) | **< 2%** por suite; test con > 5% va a cuarentena | Diaria (job nocturno) |
| **Pass rate del pipeline / tiempo de feedback** | ejecuciones de PR en verde ÷ totales; mediana de duración del pipeline de PR | ≥ 90% verdes; **≤ 10 min** en PR | Semanal |
| **Densidad de defectos por módulo** (adicional) | defectos ÷ KLOC o ÷ puntos de historia, por módulo | Tendencia decreciente; foco en el top 3 | Por sprint |
| **Disponibilidad / SLO de la API** (adicional) | requests exitosos (no 5xx) ÷ totales; p95 de latencia | 99,9% mensual; p95 < 500 ms en `/orders/assign` | Continuo (Cloud Monitoring) |
