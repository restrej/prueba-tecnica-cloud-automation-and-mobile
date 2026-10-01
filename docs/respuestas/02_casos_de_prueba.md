# Parte 2. Diseño de casos de prueba funcionales

## 2.1 Matriz de casos de prueba: módulo Preparación de Pedido (PickApp)

Datos de referencia: operador `OP-312` activo; pedido de domicilio `ORD-2025-007841` (2 SKUs);
pedido de tienda `ORD-2025-007842` (1 SKU); máximo configurado = 50 SKUs por pedido.
Columna **Auto**: ✅ candidato a automatizar · ⚠️ parcial · ❌ manual.

| ID | Módulo | Caso de prueba | Precondiciones | Pasos | Resultado esperado | Tipo | Prioridad | Auto |
|---|---|---|---|---|---|---|---|---|
| TC-01 | Preparación | Envío a domicilio completo genera guía | Operador activo; pedido HOME con 2 SKUs asignado | 1. Login 2. Abrir pedido 3. Escanear SKU-1001 4. Escanear SKU-2002 5. Confirmar preparación | Avance 2/2; se genera número de guía; estado **"Guía Generada"**; evento publicado a shipping-service | E2E | Crítica | ✅ flujo de mayor valor, se repite en cada release |
| TC-02 | Preparación | Recogida en tienda termina en "Listo para recoger" | Pedido PICKUP con 1 SKU asignado | 1. Login 2. Abrir pedido 3. Escanear SKU 4. Confirmar 5. Marcar "Listo para recoger" | Estado **"Listo para recoger"**; no se genera guía de envío | E2E | Crítica | ✅ |
| TC-03 | Preparación | Rechazo por producto no disponible | Pedido asignado; un SKU sin stock físico | 1. Abrir pedido 2. Tocar "Rechazar" 3. Elegir motivo "Producto no disponible" 4. Confirmar | Estado **"Pendiente de resurtido"**; e-commerce notificado con el motivo; pedido sale de la lista del operador | E2E | Crítica | ✅ (verificación del e-commerce vía API/mock) |
| TC-04 | Login | Credenciales inválidas | App instalada | 1. Usuario válido + contraseña incorrecta 2. Ingresar | Mensaje "Credenciales inválidas"; no se navega; no se guarda token; intento registrado | Negativo | Alta | ✅ |
| TC-05 | Preparación | Scanner falla / lectura ilegible | Pedido abierto | 1. Escanear un código dañado (lectura vacía o parcial) | Mensaje "Código vacío, vuelve a escanear"; avance sin cambios; el campo conserva el foco | Negativo | Alta | ⚠️ la lógica sí (simulando lectura vacía); la óptica real es manual |
| TC-06 | Preparación | Producto escaneado no pertenece al pedido | Pedido abierto | 1. Escanear EAN de otro producto | Mensaje "Producto X no pertenece al pedido"; avance sin cambios; botón Confirmar deshabilitado | Negativo | Alta | ✅ |
| TC-07 | Preparación | SKU inexistente en catálogo | Pedido abierto | 1. Digitar manualmente un código que no existe | Mensaje de producto no encontrado; se registra el evento para auditoría | Negativo | Media | ✅ |
| TC-08 | Preparación | Pedido con un solo SKU | Pedido con 1 SKU | 1. Abrir 2. Escanear el único SKU 3. Confirmar | Avance 1/1; Confirmar se habilita inmediatamente; flujo finaliza correctamente | Límite | Alta | ✅ |
| TC-09 | Preparación | Pedido con el máximo de SKUs (50) | Pedido sembrado con 50 SKUs | 1. Abrir 2. Escanear los 50 3. Confirmar | La lista hace scroll correctamente; avance 50/50; rendimiento aceptable (< 1 s por escaneo); guía generada | Límite | Media | ✅ (datos sembrados por API) |
| TC-10 | Preparación | Sesión expirada durante la preparación | Token con vida corta (ambiente de pruebas) | 1. Abrir pedido 2. Escanear 1 SKU 3. Esperar expiración 4. Escanear el siguiente | Se pide re-autenticación sin perder el avance local; tras el login continúa en el mismo pedido | Límite | Alta | ✅ (token de vida corta) |
| TC-11 | Preparación | Escanear dos veces el mismo SKU | Pedido abierto con SKU ya escaneado | 1. Escanear SKU-1001 2. Escanear SKU-1001 de nuevo | Mensaje "ya fue escaneado"; el contador no se duplica | Negativo | Alta | ✅ |
| TC-12 | Preparación | Confirmar sin escanear todo | Pedido con 2 SKUs, 1 escaneado | 1. Intentar Confirmar | Botón deshabilitado; no se puede despachar incompleto | Validación de datos | Alta | ✅ |
| TC-13 | Preparación | Cantidades por SKU (qty > 1) | SKU con qty = 3 | 1. Escanear el SKU 3 veces | Avance por unidades (3/3); un 4.º escaneo se rechaza | Validación de datos | Media | ✅ |
| TC-14 | Rechazo | Rechazo sin motivo | Pedido abierto | 1. Rechazar 2. Confirmar sin elegir motivo | Validación "Selecciona un motivo"; no cambia el estado | Validación de datos | Media | ✅ |
| TC-15 | Preparación | Pérdida de red al confirmar | Pedido completo; modo avión durante la confirmación | 1. Activar modo avión 2. Confirmar 3. Restaurar red | Mensaje de reintento; sin guías duplicadas al reconectar (idempotencia) | Negativo | Alta | ⚠️ (Appium puede cambiar la conectividad del emulador) |
| TC-16 | Regresión | Lista de pedidos refleja reasignación del supervisor | Supervisor reasigna un pedido desde el Centro de Control | 1. Operador en la lista 2. Supervisor reasigna 3. Refrescar | El pedido desaparece de la lista del operador original en < 5 s (tiempo real) | Regresión | Alta | ✅ (API + mobile) |
| TC-17 | Preparación | Usabilidad del scanner físico con guantes y poca luz | Dispositivo real + scanner Zebra | 1. Escanear 10 productos en condiciones reales | Tasa de lectura ≥ 98%; sin lecturas fantasma | Funcional | Media | ❌ hardware y ergonomía reales |

**Por qué son candidatos a automatización:** se ejecutan en cada release (regresión), tienen
resultado determinista, sus datos se pueden preparar por API y cubren el flujo de ingresos.
TC-05 y TC-15 son parciales porque una parte depende de hardware o del sistema operativo;
TC-17 es manual porque valida condiciones físicas.

> **Implementado en el repositorio:** TC-01, TC-02, TC-03, TC-04 y TC-06 en
> `tests/mobile/test_pickapp_flow.py` (Appium) y `mobile-app/test/widget_test.dart` (Flutter).

## 2.2 Organización y gestión de los casos automatizables

**¿Cómo los organizaría en suites?** Con *markers* (etiquetas) combinables, no con carpetas duplicadas:

| Suite | Contenido | Cuándo corre |
|---|---|---|
| `smoke` | TC-01, TC-04 (login + flujo feliz) | Cada despliegue (≈ 3 min) |
| `critical` | TC-01, TC-02, TC-03, TC-12 | Cada PR/merge; si falla, **bloquea** |
| `regression` | Todos los ✅ | Nocturno y en cada Release Candidate |
| `scanner` | TC-05, TC-06, TC-07, TC-11, TC-13 | Cuando cambia el módulo de escaneo |
| `boundary` | TC-08, TC-09, TC-10 | Nocturno |
| `quarantine` | Tests inestables en investigación | Job no bloqueante |

**Criterios para priorizar qué automatizar primero:**
1. **Riesgo de negocio** (impacto × probabilidad): el flujo que genera ingresos y los defectos actuales.
2. **Frecuencia de ejecución**: lo que se repite en cada release devuelve antes la inversión.
3. **Estabilidad de la funcionalidad**: no automatizar pantallas que cambiarán el próximo sprint.
4. **Costo/factibilidad técnica**: primero lo determinista y con datos preparables por API.
5. **Nivel más bajo posible**: si una regla se puede probar por API, no se prueba por UI.

**¿Cómo gestionaría los casos que requieren scanner físico?**
- Separar la **lógica** del **hardware**: la app recibe el código por una interfaz (`ScannerInput`);
  en pruebas se inyecta el código (texto + ENTER como un scanner *keyboard wedge*, o un *broadcast intent*
  como DataWedge). Implementado en `framework/mobile/barcode.py`.
- Para cámara: imágenes de códigos en la *virtual scene* del emulador Android.
- Un **conjunto pequeño de pruebas manuales en dispositivo físico** por release (TC-17), con una
  matriz de scanners/dispositivos reales usados en almacén.
- Pruebas de **contrato con el hardware**: verificar los formatos (EAN-13, Code128, sufijo ENTER/TAB) que
  envía cada modelo de scanner.

**¿Cómo integraría el feedback del equipo funcional?**
- Casos en una herramienta compartida (Xray/TestRail) con **trazabilidad** caso ↔ historia ↔ test automatizado.
- **Revisión de casos en el refinamiento** (*three amigos*: negocio, desarrollo, QA) antes de automatizar,
  escritos en lenguaje de negocio (Gherkin opcional) para que el equipo funcional los valide.
- Los defectos encontrados en pruebas manuales/UAT se convierten en **nuevos casos de regresión**.
- Demo quincenal del reporte de automatización y del tablero de cobertura; el equipo funcional
  prioriza el backlog de automatización.
