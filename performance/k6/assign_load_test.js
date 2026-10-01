// =============================================================================
// PARTE 5 - 5.2: PRUEBA DE CARGA de POST /api/v1/orders/assign con k6.
//
// Requisitos del enunciado:
//   - 50 usuarios concurrentes (VUs)
//   - 5 minutos de duración con ramp-up de 1 minuto
//   - Medir: tiempo de respuesta (p50, p95, p99), throughput y tasa de error
//
// Ejecutar (con el servicio levantado):
//   k6 run performance/k6/assign_load_test.js
//   k6 run -e BASE_URL=https://staging.logitrack.example performance/k6/assign_load_test.js
//   k6 run -e QUICK=1 performance/k6/assign_load_test.js      (versión de 1 minuto para practicar)
// =============================================================================

import { sleep } from 'k6';
// exec: información de ejecución (número de iteración global, VU actual...).
import exec from 'k6/execution';
// Métricas personalizadas: Rate = porcentaje; Trend = distribución de tiempos.
import { Rate, Trend } from 'k6/metrics';
import { assignOrder, login, seedOrders } from './lib/logitrack.js';

// QUICK=1 acorta los tiempos para practicar sin esperar 5 minutos.
const QUICK = __ENV.QUICK === '1';

// Métrica propia: % de asignaciones que NO devolvieron 201.
const assignErrors = new Rate('assign_errors');
// Métrica propia: duración sólo de las asignaciones (sin login ni setup).
const assignDuration = new Trend('assign_duration', true);

// -----------------------------------------------------------------------------
// options: configuración de la prueba (perfil de carga + criterios de aceptación)
// -----------------------------------------------------------------------------
export const options = {
  // stages = perfil de carga "rampa" de usuarios virtuales.
  stages: QUICK
    ? [{ duration: '15s', target: 50 }, { duration: '45s', target: 50 }]
    : [
        { duration: '1m', target: 50 }, // ramp-up: de 0 a 50 VUs en 1 minuto
        { duration: '4m', target: 50 }, // carga sostenida: 50 VUs hasta completar 5 minutos
      ],
  // Estadísticas que se muestran para cada métrica de tiempo: p50 = "med".
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  // thresholds = CRITERIOS DE ACEPTACIÓN. Si alguno no se cumple, k6 termina con
  // código de salida != 0 y el pipeline de CI se pone en ROJO.
  thresholds: {
    'http_req_duration{endpoint:assign}': ['p(95)<500', 'p(99)<1000'], // ms
    http_req_failed: ['rate<0.01'],     // < 1% de errores HTTP
    assign_errors: ['rate<0.01'],       // < 1% de asignaciones fallidas
    checks: ['rate>0.99'],              // > 99% de verificaciones exitosas
  },
};

// -----------------------------------------------------------------------------
// setup(): se ejecuta UNA vez antes de la carga. Lo que devuelve se pasa a cada VU.
// -----------------------------------------------------------------------------
export function setup() {
  const token = login();
  // 50 VUs * ~1 iteración/s * 300 s = ~15.000 iteraciones; creamos margen.
  const orderIds = seedOrders(QUICK ? 5000 : 20000);
  return { token, orderIds };
}

// -----------------------------------------------------------------------------
// default: lo que hace CADA usuario virtual en CADA iteración.
// -----------------------------------------------------------------------------
export default function (data) {
  // iterationInTest: contador global único -> cada iteración usa un pedido distinto.
  const n = exec.scenario.iterationInTest;
  const orderId = data.orderIds[n % data.orderIds.length];
  const res = assignOrder(data.token, orderId, n);
  // Registramos nuestras métricas propias.
  assignErrors.add(res.status !== 201);
  assignDuration.add(res.timings.duration);
  // "Think time": un supervisor no hace clic sin pausa. 1 s ≈ 50 req/s con 50 VUs.
  sleep(1);
}

// -----------------------------------------------------------------------------
// handleSummary(): se ejecuta al final; genera los REPORTES (archivos) del resultado.
// -----------------------------------------------------------------------------
export function handleSummary(data) {
  const m = data.metrics;
  const d = m['http_req_duration{endpoint:assign}'] || m.http_req_duration;
  // Texto legible con las métricas pedidas por el enunciado.
  const lines = [
    '================ RESULTADO PRUEBA DE CARGA: POST /api/v1/orders/assign ================',
    `Peticiones totales : ${m.http_reqs.values.count}`,
    `Throughput         : ${m.http_reqs.values.rate.toFixed(2)} req/s (${(m.http_reqs.values.rate * 60).toFixed(0)} req/min)`,
    `Tiempo resp. p50   : ${d.values.med.toFixed(1)} ms`,
    `Tiempo resp. p95   : ${d.values['p(95)'].toFixed(1)} ms`,
    `Tiempo resp. p99   : ${d.values['p(99)'].toFixed(1)} ms`,
    `Tiempo resp. máx   : ${d.values.max.toFixed(1)} ms`,
    `Tasa de error HTTP : ${(m.http_req_failed.values.rate * 100).toFixed(2)} %`,
    `Asignaciones != 201: ${(m.assign_errors.values.rate * 100).toFixed(2)} %`,
    `VUs máximos        : ${m.vus_max.values.max}`,
    '',
    'Umbrales (criterios de aceptación):',
  ];
  // Listamos cada threshold con su resultado.
  for (const [name, metric] of Object.entries(m)) {
    if (metric.thresholds) {
      for (const [rule, result] of Object.entries(metric.thresholds)) {
        lines.push(`  ${result.ok ? 'OK   ' : 'FALLA'} ${name}: ${rule}`);
      }
    }
  }
  const text = lines.join('\n') + '\n';
  // Cada clave es un destino: 'stdout' = consola; las rutas = archivos.
  return {
    stdout: text,
    'reports/k6/assign-load-summary.txt': text,
    'reports/k6/assign-load-summary.json': JSON.stringify(data, null, 2),
  };
}
