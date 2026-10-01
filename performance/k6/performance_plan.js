// =============================================================================
// PARTE 5 - 5.1: PLAN DE PRUEBAS DE RENDIMIENTO (carga, estrés, soak y spike).
//
// Datos del negocio:
//   - Pico actual: 500 req/min (7:00-8:00 AM)            ≈ 8,3 req/s
//   - Crecimiento esperado +40%: 700 req/min             ≈ 11,7 req/s
//
// Aquí se modela la carga por TASA DE LLEGADA (req/s) con el executor
// "ramping-arrival-rate": así probamos exactamente "N peticiones por minuto",
// sin importar cuánto tarde cada respuesta (modelo "abierto", como el tráfico real).
//
// Uso:
//   k6 run -e TEST_TYPE=load   performance/k6/performance_plan.js
//   k6 run -e TEST_TYPE=stress performance/k6/performance_plan.js
//   k6 run -e TEST_TYPE=soak   performance/k6/performance_plan.js
//   k6 run -e TEST_TYPE=spike  performance/k6/performance_plan.js
//   Agregar -e QUICK=1 para una versión corta (minutos -> segundos) de práctica.
// =============================================================================

import exec from 'k6/execution';
import { assignOrder, login, seedOrders } from './lib/logitrack.js';

const TEST_TYPE = __ENV.TEST_TYPE || 'load';
const QUICK = __ENV.QUICK === '1';

// Convierte minutos a texto de duración k6. En modo QUICK, 1 minuto => 2 segundos.
const dur = (minutes) => (QUICK ? `${Math.max(2, Math.round(minutes * 2))}s` : `${minutes}m`);

// Tasas de referencia en peticiones por segundo.
const PEAK_TODAY = 9;   // ≈ 500 req/min (redondeado hacia arriba)
const PEAK_NEXT_YEAR = 12; // ≈ 700 req/min (+40%)

// Perfiles por tipo de prueba: cada uno es una lista de etapas {target: req/s, duration}.
const PROFILES = {
  // CARGA: ¿soporta el pico esperado del próximo año de forma estable?
  load: [
    { target: PEAK_NEXT_YEAR, duration: dur(5) },   // subida gradual
    { target: PEAK_NEXT_YEAR, duration: dur(30) },  // meseta de 30 min en el pico +40%
    { target: 0, duration: dur(2) },
  ],
  // ESTRÉS: subir por escalones por encima del pico hasta encontrar el punto de quiebre.
  stress: [
    { target: PEAK_NEXT_YEAR, duration: dur(5) },
    { target: PEAK_NEXT_YEAR * 2, duration: dur(5) },  // 2x
    { target: PEAK_NEXT_YEAR * 3, duration: dur(5) },  // 3x
    { target: PEAK_NEXT_YEAR * 4, duration: dur(5) },  // 4x
    { target: 0, duration: dur(5) },                   // recuperación: ¿vuelve a la normalidad?
  ],
  // RESISTENCIA (SOAK): carga normal-alta durante horas para detectar fugas de memoria,
  // conexiones a Cloud SQL que no se liberan, crecimiento de colas de Pub/Sub, etc.
  soak: [
    { target: PEAK_TODAY, duration: dur(10) },
    { target: PEAK_TODAY, duration: dur(240) },  // 4 horas
    { target: 0, duration: dur(5) },
  ],
  // PICOS (SPIKE): apertura simultánea de todos los almacenes a las 7:00.
  spike: [
    { target: 2, duration: dur(2) },                      // tráfico bajo
    { target: PEAK_NEXT_YEAR * 4, duration: QUICK ? '2s' : '10s' }, // salto brusco en 10 s
    { target: PEAK_NEXT_YEAR * 4, duration: dur(3) },     // se mantiene el pico
    { target: 2, duration: QUICK ? '2s' : '10s' },        // caída brusca
    { target: 2, duration: dur(3) },                      // ¿se recupera? (Cloud Run escala hacia abajo)
  ],
};

// Criterios de aceptación por tipo de prueba (en estrés se toleran más errores:
// el objetivo es OBSERVAR el quiebre, no "pasar").
const THRESHOLDS = {
  load: { http_req_duration: ['p(95)<500', 'p(99)<1000'], http_req_failed: ['rate<0.01'] },
  stress: { http_req_duration: ['p(95)<2000'], http_req_failed: ['rate<0.05'] },
  soak: { http_req_duration: ['p(95)<500', 'p(99)<1000'], http_req_failed: ['rate<0.01'] },
  spike: { http_req_duration: ['p(95)<1500'], http_req_failed: ['rate<0.02'] },
};

export const options = {
  scenarios: {
    [TEST_TYPE]: {
      executor: 'ramping-arrival-rate',
      startRate: 1,                 // req/s al inicio
      timeUnit: '1s',               // las "target" se expresan por segundo
      preAllocatedVUs: 50,          // VUs listos de antemano
      maxVUs: 300,                  // máximo si el servicio se pone lento
      stages: PROFILES[TEST_TYPE],
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
  thresholds: THRESHOLDS[TEST_TYPE],
};

export function setup() {
  // Cantidad de pedidos aproximada según el tipo (soak necesita muchos).
  const needed = { load: 30000, stress: 40000, soak: 50000, spike: 20000 }[TEST_TYPE];
  return { token: login(), orderIds: seedOrders(QUICK ? 3000 : needed) };
}

export default function (data) {
  const n = exec.scenario.iterationInTest;
  assignOrder(data.token, data.orderIds[n % data.orderIds.length], n);
}
