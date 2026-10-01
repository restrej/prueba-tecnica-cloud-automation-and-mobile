#!/usr/bin/env bash
# =============================================================================
# DAST con OWASP ZAP (Dynamic Application Security Testing).
#
# ¿Qué hace? ZAP ATACA la API en ejecución (como lo haría un atacante): lee el
# contrato OpenAPI (/openapi.json), genera peticiones a cada endpoint y les
# inyecta payloads de SQLi, XSS, path traversal, etc. Luego revisa las respuestas.
#
# ZAP es gratuito y automatizable (ideal para CI/CD). Burp Suite Professional es
# su equivalente comercial, más usado para pentesting MANUAL (ver docs).
#
# Requisitos: Docker y el servicio corriendo (por defecto en http://localhost:8000).
# Uso:        bash security/zap/run_zap_scan.sh [BASE_URL]
# Resultado:  reports/security/zap-report.html (abrir en el navegador)
# =============================================================================

# -e: salir si un comando falla | -u: error si se usa una variable no definida
# -o pipefail: un fallo dentro de un "pipe" también cuenta como fallo.
set -euo pipefail

# URL de la API a escanear (primer argumento o valor por defecto).
BASE_URL="${1:-http://localhost:8000}"
# Carpeta donde ZAP dejará los reportes (se monta dentro del contenedor como /zap/wrk).
REPORT_DIR="$(pwd)/reports/security"
mkdir -p "$REPORT_DIR"
# ZAP corre como usuario "zap" (uid 1000) dentro del contenedor: necesita poder escribir.
chmod 777 "$REPORT_DIR"
# Copiamos la configuración de reglas a la carpeta montada.
cp "$(dirname "$0")/zap-rules.tsv" "$REPORT_DIR/zap-rules.tsv"

echo ">> Obteniendo token de un supervisor para escanear endpoints autenticados..."
TOKEN=$(curl -sf -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"supervisor1","password":"Sup3rvisor!2025"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["accessToken"])')

echo ">> Ejecutando ZAP API Scan contra $BASE_URL/openapi.json ..."
# --network host: el contenedor ve "localhost" igual que nuestra máquina.
# ZAP_AUTH_HEADER_VALUE: ZAP agrega "Authorization: Bearer <token>" a cada petición.
# -t: objetivo | -f: formato del contrato | -c: archivo de reglas
# -r / -J: reportes HTML y JSON | -I: no fallar por alertas WARN (sólo por FAIL)
set +e
docker run --rm --network host \
  -v "$REPORT_DIR:/zap/wrk:rw" \
  -e ZAP_AUTH_HEADER_VALUE="Bearer $TOKEN" \
  zaproxy/zap-stable zap-api-scan.py \
    -t "$BASE_URL/openapi.json" -f openapi \
    -c zap-rules.tsv \
    -r zap-report.html -J zap-report.json \
    -I
EXIT_CODE=$?
set -e

# Códigos de salida de ZAP: 0 = sin problemas | 1 = hay reglas en FAIL | 2 = sólo WARN | 3 = error.
echo ">> ZAP terminó con código $EXIT_CODE. Reporte: $REPORT_DIR/zap-report.html"
exit $EXIT_CODE
