// =============================================================================
// Funciones compartidas por los scripts de k6 (login, datos de prueba, asignar).
//
// k6 ejecuta JavaScript, pero NO es Node.js ni un navegador: usa sus propios
// módulos ("k6/http", "k6/metrics"...). Cada usuario virtual (VU) es un bucle
// que ejecuta la función default una y otra vez.
// =============================================================================

// http: cliente HTTP de k6 (mide automáticamente tiempos de respuesta).
import http from 'k6/http';
// check: verificación que NO detiene la prueba; cuenta éxitos/fallos.
import { check, fail } from 'k6';

// URL del servicio. Se cambia con: k6 run -e BASE_URL=https://staging... script.js
export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Credenciales del supervisor de pruebas.
const USER = __ENV.K6_USER || 'supervisor1';
const PASSWORD = __ENV.K6_PASSWORD || 'Sup3rvisor!2025';

// Headers JSON reutilizables.
const JSON_HEADERS = { 'Content-Type': 'application/json' };

/**
 * Inicia sesión y devuelve el token de acceso.
 * Se llama UNA vez en setup() (no en cada iteración): medimos asignar, no login.
 */
export function login() {
  const res = http.post(`${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ username: USER, password: PASSWORD }), { headers: JSON_HEADERS });
  // Si el login falla, no tiene sentido seguir: fail() aborta la prueba.
  if (res.status !== 200) fail(`Login falló: ${res.status} ${res.body}`);
  return res.json('accessToken');
}

/**
 * Crea N pedidos listos para asignar (datos de prueba).
 * Cada iteración usará un pedido DISTINTO, como en la operación real
 * (si todas asignaran el mismo pedido, sólo mediríamos respuestas 409).
 */
export function seedOrders(count) {
  const res = http.post(`${BASE_URL}/api/v1/test-support/orders`,
    JSON.stringify({ warehouseId: 'WH-05', count }), { headers: JSON_HEADERS, timeout: '120s' });
  if (res.status !== 201) fail(`No se pudieron crear pedidos de prueba: ${res.status}`);
  return res.json('orderIds');
}

// Operadores y prioridades: se reparten de forma rotativa para variar los datos.
const OPERATORS = ['OP-312', 'OP-313', 'OP-314'];
const PRIORITIES = ['NORMAL', 'URGENT', 'EXPRESS'];

/**
 * Llama POST /api/v1/orders/assign y valida la respuesta.
 *
 * @param {string} token   token Bearer obtenido en setup().
 * @param {string} orderId pedido a asignar.
 * @param {number} n       número de iteración (para rotar operador/prioridad).
 * @returns la respuesta HTTP.
 */
export function assignOrder(token, orderId, n) {
  const payload = JSON.stringify({
    orderId,
    operatorId: OPERATORS[n % OPERATORS.length],
    warehouseId: 'WH-05',
    priority: PRIORITIES[n % PRIORITIES.length],
  });
  const res = http.post(`${BASE_URL}/api/v1/orders/assign`, payload, {
    headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` },
    // tags: etiqueta la métrica para poder filtrarla (útil con varios endpoints).
    tags: { endpoint: 'assign' },
  });
  // Verificaciones funcionales DURANTE la carga (un 201 lento es mejor que un 500 rápido).
  check(res, {
    'status es 201': (r) => r.status === 201,
    'respuesta trae assignmentId': (r) => r.status === 201 && r.json('assignmentId') !== undefined,
  });
  return res;
}
