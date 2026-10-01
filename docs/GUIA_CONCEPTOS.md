# Guía de conceptos (explicados desde cero)

Cada término tiene: **qué es**, una **analogía** con la logística de LogiTrack y
**dónde lo ves en este proyecto**. Están agrupados por tema y en el orden en que conviene leerlos.

---

## 1. La arquitectura de LogiTrack

### App mobile (Flutter)
**Qué es:** Flutter es un framework de Google para crear apps móviles (Android e iOS) con
**un solo código**, escrito en el lenguaje Dart. PickApp, la app que usan los operadores del
almacén, está hecha en Flutter.
**Detalle importante para pruebas:** Flutter no usa los botones nativos de Android; *dibuja*
toda la pantalla él mismo. Por eso las herramientas de automatización no "ven" los elementos
salvo que el desarrollador les ponga etiquetas de accesibilidad (`Semantics`).
**En el proyecto:** `mobile-app/lib/main.dart` (app demo) y `framework/mobile/locators.py`.

### Microservicio (orders-api, inventory-service, shipping-service...)
**Qué es:** en lugar de un solo programa gigante, el backend se divide en programas pequeños,
cada uno con una responsabilidad. `orders-api` gestiona pedidos; **`inventory-service`**
gestiona el **stock** (reserva productos cuando entra un pedido); `shipping-service` genera
guías; `notifications-service` envía avisos; `auth-service` valida usuarios.
**Analogía:** áreas de un almacén: recepción, bodega, despacho, atención al cliente.
**En el proyecto:** `sut/` simula `orders-api`.

### Google Cloud Platform (GCP)
La "nube" de Google: en lugar de comprar servidores, se alquilan servicios.

| Servicio | Qué es | Analogía |
|---|---|---|
| **Cloud Run** | Ejecuta contenedores (aplicaciones empaquetadas con Docker) y **escala solo**: si llegan más peticiones crea más copias (instancias); si no hay tráfico, las apaga. | Una agencia de personal temporal: más operarios en hora pico, menos en la noche. |
| **Cloud SQL** | Base de datos relacional administrada (aquí PostgreSQL): tablas con filas y columnas. | El archivo maestro de pedidos e inventario. |
| **Pub/Sub** | Sistema de **mensajería asíncrona**: un servicio *publica* un mensaje en un *topic* y los servicios *suscritos* lo reciben cuando pueden. El que publica no espera respuesta. | Un tablero de avisos: recepción pega "llegó el pedido X" y bodega y despacho lo leen. |
| **Firestore** | Base de datos NoSQL (documentos JSON) con actualizaciones **en tiempo real**. | La pizarra en vivo que muestra qué está haciendo cada operador. |
| **Cloud Functions** | Pequeñas funciones que se ejecutan solas cuando ocurre un evento (llega un mensaje, cambia un documento). | Un sensor que enciende una luz cuando se abre una puerta. |
| **Cloud Build** | Servicio de GCP que construye y despliega el código (compila, crea la imagen Docker y la publica en Cloud Run). | La línea de empaque que deja el producto listo para enviar. |
| **Cloud Logging** | Guarda y permite buscar los **logs** (mensajes que escriben las aplicaciones). | El libro de registro de cada turno. |
| **Cloud Monitoring** | Gráficos y **alertas** sobre métricas: CPU, latencia, errores, instancias. | El tablero de indicadores de la gerencia, con alarmas. |
| **Cloud Trace** | Muestra el **recorrido de una petición** entre servicios y cuánto tardó cada tramo. | El rastreo de un paquete: en qué estación se demoró. |
| **Error Reporting** | Agrupa automáticamente los errores (excepciones) iguales y cuenta cuántas veces ocurren. | Un resumen de "quejas" agrupadas por tipo. |

**En el proyecto:** `sut/events.py` simula Pub/Sub; `sut/main.py` escribe logs en el formato
JSON que entiende Cloud Logging (`severity`, `httpRequest`, `trace`).

---

## 2. Cómo llega el código a producción

### Repositorio, rama, Pull Request (PR)
- **Repositorio:** la carpeta del proyecto con todo su historial (en GitHub).
- **Rama (branch):** una copia paralela donde un desarrollador trabaja sin afectar a los demás.
  `main` es la rama principal, la "oficial".
- **Pull Request:** la *solicitud* para unir tu rama a `main`. Ahí otros revisan el código y
  se ejecutan las pruebas automáticas.

### Las 4 etapas: PR → Merge a main → Release Candidate → Producción
| Etapa | Qué significa | Qué pruebas corren (resumen) |
|---|---|---|
| **Pull Request** | Alguien propone un cambio | Rápidas: lint, unitarias, SAST, contrato (minutos) |
| **Merge a main** | El cambio fue aprobado y se unió | Integración, API, UI, seguridad, smoke de rendimiento |
| **Release Candidate (RC)** | Una versión "candidata" a salir, desplegada en un ambiente igual a producción (staging) | E2E completos, mobile en varios dispositivos, regresión, DAST, rendimiento, UAT |
| **Producción** | La versión que usan los operadores reales | Smoke tests, monitoreo sintético, canary |

### CI/CD
- **CI (Integración Continua):** cada cambio se compila y se prueba automáticamente.
- **CD (Entrega/Despliegue Continuo):** si todo pasa, se despliega automáticamente.
- **Pipeline:** la "cadena de montaje" de pasos automáticos (compilar → probar → desplegar).

### GitHub Actions y workflow
**GitHub Actions** es el sistema de CI/CD integrado en GitHub. Un **workflow** es un archivo
`.yml` que dice **cuándo** (en cada PR, cada noche...) y **qué** ejecutar. Un workflow tiene
**jobs** (grupos de pasos que corren en una máquina) y cada job tiene **steps** (comandos).
**En el proyecto:** `.github/workflows/ci.yml`, `mobile.yml`, `performance.yml`.

### Quality Gates (compuertas de calidad) y condición de paso/bloqueo
**Qué es:** una regla automática que decide si el código **puede avanzar** a la siguiente
etapa o **se bloquea**. Ejemplos: "0 tests críticos fallidos", "cobertura ≥ 80%",
"0 vulnerabilidades altas", "p95 < 500 ms".
**Analogía:** el control de calidad al final de la línea: si el paquete no pasa, no sale.
**En el proyecto:** `tools/quality_gate.py`, `--cov-fail-under=80`, los `thresholds` de k6
y las reglas `FAIL` de ZAP.

### Branch protection rules (reglas de protección de rama)
Configuración de GitHub que **impide** hacer cambios directos en `main`: obliga a usar PR,
exige aprobaciones de otros y que las pruebas pasen. Nadie puede "saltarse" el proceso.

### Required checks (verificaciones obligatorias)
Los jobs del pipeline que GitHub exige en **verde** para habilitar el botón "Merge".
Si uno falla, el PR no se puede unir.

### Coverage gate (compuerta de cobertura)
Bloquea si el porcentaje de código ejecutado por las pruebas baja de un mínimo (aquí 80%).

### Canary deployment (despliegue canario)
Desplegar la versión nueva **sólo a una parte del tráfico** (ej. 5%), vigilar métricas y,
si todo va bien, subir gradualmente (25% → 50% → 100%). Cloud Run lo permite dividiendo el
tráfico entre revisiones.
**Analogía:** el canario que los mineros llevaban: si se enfermaba, salían antes de que el
problema afectara a todos.

### Rollback automático
Volver **automáticamente** a la versión anterior si las métricas del canario empeoran
(ej. errores 5xx > 1% o p95 > 800 ms durante 5 minutos).

### Feature flags
Interruptores en el código para **activar o desactivar una funcionalidad sin desplegar**.
Permiten encender algo sólo para un almacén piloto y apagarlo al instante si falla.

---

## 3. Tipos y niveles de prueba

### La pirámide de pruebas
```
          /\        E2E / UI      -> pocas, lentas, costosas, prueban el flujo completo
         /  \       Contrato / API
        /    \      Integración
       /______\     Unitarias     -> muchas, rápidas (milisegundos), baratas
```
Mientras más arriba, más lenta, costosa y frágil es la prueba; por eso hay menos.

| Nivel | Qué valida | En el proyecto |
|---|---|---|
| **Unit Tests** | Una función o clase aislada (sin red ni base de datos) | `tests/unit/` |
| **Integration Tests** | Que varias piezas funcionen **juntas** (API + base de datos + Pub/Sub) | `tests/integration/` |
| **Contract Tests** | Que el **formato** acordado entre dos sistemas no se rompa | `tests/contract/` + `contracts/` |
| **API Tests** | El comportamiento del servicio a través de HTTP | `tests/api/` |
| **End-to-End (E2E)** | El flujo completo como lo vive un usuario, de punta a punta | `tests/ui/`, `tests/mobile/` |
| **UAT** (User Acceptance Testing) | Usuarios reales (supervisores, operadores) confirman que **sirve para su trabajo** | Manual, en staging |
| **Smoke Tests** | Pocas pruebas rápidas para confirmar que "está vivo" tras desplegar | `pytest -m smoke` |
| **Regresión** | Que lo que ya funcionaba **siga funcionando** tras un cambio | `pytest -m regression` |

### Tipos de prueba de rendimiento (k6)
| Tipo | Pregunta que responde |
|---|---|
| **Carga** | ¿Soporta el tráfico esperado (pico +40%) de forma estable? |
| **Estrés** | ¿Dónde se rompe si seguimos subiendo? ¿Se recupera? |
| **Resistencia (Soak)** | ¿Aguanta horas sin degradarse (fugas de memoria, conexiones)? |
| **Picos (Spike)** | ¿Qué pasa si el tráfico se multiplica de golpe (apertura de almacenes)? |

Términos de k6: **VU** (usuario virtual = un "robot" que hace peticiones en bucle),
**ramp-up** (subida gradual de usuarios), **throughput** (peticiones por segundo),
**p95** (el 95% de las peticiones tardó menos que este valor; mide la experiencia de "casi todos"),
**threshold** (criterio de aceptación que, si no se cumple, hace fallar la prueba).

---

## 4. Seguridad

### Security scans (escaneos de seguridad)
Herramientas automáticas que buscan vulnerabilidades. Hay tres familias:

| Tipo | Qué hace | Cuándo | Herramienta en el proyecto |
|---|---|---|---|
| **SAST** (Static Application Security Testing) | Lee el **código fuente** sin ejecutarlo, buscando patrones peligrosos (contraseñas en el código, SQL armado con texto...) | En cada PR (rápido) | **Bandit**, **Semgrep**, reglas `S` de Ruff |
| **SCA** (Software Composition Analysis) | Revisa si las **librerías** que usas tienen vulnerabilidades conocidas (CVE) | En cada PR | **pip-audit** |
| **DAST** (Dynamic Application Security Testing) | **Ataca la aplicación en ejecución** desde afuera, como un hacker | Al desplegar en un ambiente (main/RC) | **OWASP ZAP** |

### ¿Burp Suite o OWASP ZAP? (mi recomendación)
- **Burp Suite** es la herramienta más usada por los *pentesters* (expertos en seguridad) para
  pruebas **manuales**: intercepta el tráfico entre el navegador/app y la API, permite modificar
  peticiones a mano y repetirlas. La edición *Community* es gratuita pero **no tiene escáner
  automático**; la *Professional* (de pago) sí, y la versión *Enterprise* se integra con CI/CD.
- **OWASP ZAP** es **gratuito, open source** y está pensado para **automatizarse**: tiene imágenes
  Docker oficiales y modos "baseline" y "API scan" que se ejecutan en GitHub Actions.

**Recomendación para empezar:** usa **ZAP en el pipeline** (automático, sin costo) + las
**pruebas de seguridad en pytest** (`tests/security/`) para reglas propias del negocio.
Aprende **Burp Suite Community** después para explorar manualmente (es excelente para
entender cómo se ve una petición y cómo se manipula). Ambas herramientas comparten los
mismos conceptos: proxy, interceptar, repetir, escanear.

### Ataques que se prueban (OWASP)
- **SQL injection:** meter código SQL en un campo para que la base de datos lo ejecute (`' OR '1'='1`).
- **NoSQL injection:** igual, pero con operadores de bases NoSQL (`{"$ne": null}`).
- **Command injection:** meter comandos del sistema operativo (`; ls`).
- **XSS (Cross-Site Scripting):** meter JavaScript que se ejecute en el navegador de otra persona.
- **Escalamiento de privilegios:** un usuario hace algo que su rol no permite (vertical) o
  accede a datos de otro almacén (horizontal).
- **CORS:** regla del navegador que define qué sitios web pueden llamar a tu API.
- **CSP (Content-Security-Policy):** header que le dice al navegador de dónde puede cargar scripts.
- **Rate limiting:** límite de peticiones por minuto para evitar abuso.

---

## 5. Métricas de calidad

| Métrica | Qué mide | Fórmula simple |
|---|---|---|
| **Defect Leakage** (fuga de defectos) | Qué porcentaje de los defectos **se escaparon** a producción | defectos en producción / total de defectos × 100 |
| **Test Coverage** (cobertura) | Qué porcentaje del código (o de los requisitos) ejecutan las pruebas | líneas ejecutadas / líneas totales × 100 |
| **Change Failure Rate** (tasa de fallo de cambios) | Qué porcentaje de despliegues **causaron un problema** en producción | despliegues con incidente / despliegues totales × 100 |
| **MTTR** (Mean Time To Restore) | Cuánto se tarda en promedio en **recuperar** el servicio tras una falla | suma de tiempos de recuperación / número de incidentes |

Las respuestas de la Parte 1.3 amplían esto con metas y frecuencias.

---

## 6. Tests flaky (inestables)

| Concepto | Qué es |
|---|---|
| **Test flaky** | Una prueba que **a veces pasa y a veces falla** sin que cambie el código. Ej.: falla 3 de cada 10 veces. Causas típicas: esperas fijas (`sleep`), datos compartidos entre pruebas, orden de ejecución, red lenta. |
| **Race condition** (condición de carrera) | Un error del **sistema** (no del test) que depende de qué operación llega primero. Ej.: dos supervisores asignan el mismo pedido al mismo tiempo y ambos "ganan". |
| **Retry policy** (política de reintentos) | Volver a ejecutar automáticamente un test que falló (ej. 1 reintento). Útil contra fallos transitorios, pero **peligroso** si oculta bugs reales: el reintento siempre debe quedar registrado. |
| **Quarantine** (cuarentena) | Mover un test flaky a una suite aparte que **se ejecuta pero no bloquea** el pipeline, con un ticket y un responsable para arreglarlo. |
| **Reportería de flakiness** | Medir cuántas veces falla cada test en varias ejecuciones para detectar los inestables con datos. |

**En el proyecto:** `tests/quarantine/test_flaky_demo.py`, marker `quarantine`, job
`quarantine` en `ci.yml`, `tools/flaky_report.py`, opción `--reruns 1`.

---

## 7. Patrones de automatización usados

| Patrón | Qué es | En el proyecto |
|---|---|---|
| **Page Object Model** | Una clase por pantalla web con sus elementos y acciones; las pruebas no conocen selectores | `framework/ui/pages/` |
| **Screen Object** | Lo mismo para pantallas móviles | `framework/mobile/screens/` |
| **API Object** | Una clase con un método por operación de la API | `framework/api/logitrack_api.py` |
| **Test Data Builder** | Función que crea datos válidos por defecto; cada prueba cambia sólo lo necesario | `framework/api/payloads.py` |
| **Fixture** | Preparación reutilizable que pytest inyecta en las pruebas | `tests/conftest.py` |
| **AAA** | Arrange (preparar) – Act (ejecutar) – Assert (verificar) | todas las pruebas |
| **Locator `data-testid`** | Atributo exclusivo para pruebas: no cambia aunque cambie el diseño | `sut/web/login.html` |

---

## 8. Stakeholder no técnico
Persona interesada en el proyecto pero sin formación técnica (ej. Gerente de Operaciones).
Con ellos se habla de **impacto en el negocio** (pedidos perdidos, horas de trabajo, costo),
no de herramientas. La Parte 7.2 tiene un ejemplo de respuesta.
