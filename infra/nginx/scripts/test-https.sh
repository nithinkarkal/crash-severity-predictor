#!/usr/bin/env bash
# ASP Nginx validation script - HTTPS routing, auth, rate limiting.
# Usage: bash infra/nginx/scripts/test-https.sh
set -euo pipefail

BASE_URL="${BASE_URL:-https://asp.local:8081}"
API="${BASE_URL}/api/v1"
DATA_USER="${DATA_USER:-datascientest}"
DATA_PASS="${DATA_PASS:-user123}"

pass() { echo "  [PASS] $*"; }
fail() { echo "  [FAIL] $*"; exit 1; }

code() { curl -sk -o /tmp/asp_test_body -w "%{http_code}" "$@"; }
last_body() { cat /tmp/asp_test_body; }

echo "== 1. Health (via Nginx, no auth) =="
C=$(code "$API/health")
[ "$C" = "200" ] && pass "health -> $C" || fail "health -> $C (body: $(last_body))"

echo "== 2. Login (get token) =="
C=$(code -X POST "$API/login" -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=${DATA_USER}&password=${DATA_PASS}")
[ "$C" = "200" ] && pass "login -> $C" || fail "login -> $C (body: $(last_body))"
TOKEN=$(python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" </tmp/asp_test_body) || fail "could not parse access_token"

echo "== 3. Predict (Bearer token) =="
C=$(code -X POST "$API/predict" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"place":1,"catu":1,"sexe":1,"secu1":1,"year_acc":2023,"victim_age":30,"nb_victim":1,"catv":2,"obsm":0,"motor":1,"nb_vehicles":1,"catr":1,"circ":1,"surf":1,"situ":1,"vma":50,"jour":1,"mois":1,"lum":1,"dep":75,"com":101,"agg":1,"int":1,"atm":0,"col":1,"lat":48.85,"long":2.35,"hour":14}')
[ "$C" = "200" ] && pass "predict -> $C" || fail "predict -> $C (body: $(last_body))"

echo "== 4. Rate limiting (login zone: 1 r/10s, burst 1) =="
declare -a CODES
for i in 1 2 3; do
  CODES+=("$(code -X POST "$API/login" -H "Content-Type: application/x-www-form-urlencoded" \
    --data "username=ratecheck&password=wrong")")
done
echo "  codes: ${CODES[*]}"
[ "${CODES[0]}" != "429" ] && pass "first attempt not rate-limited (${CODES[0]})" || fail "first attempt unexpectedly 429"
[ "${CODES[1]}" = "429" ] && pass "second attempt -> 429" || fail "second attempt -> ${CODES[1]} (expected 429)"

echo "== 5. HTTP -> HTTPS redirect (info only) =="
# Host publishes 8081->443 only; port 80 is internal, so 301 is not reachable
# from the host. Inside the container it would be:
#   docker exec asp-nginx wget -q -S -O- http://127.0.0.1/api/v1/health
C=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://asp.local:8081/api/v1/health" || echo "unreachable")
echo "  http 8081 -> $C (expected: unreachable; 301 only visible inside asp-network)"

echo "ALL CHECKS PASSED"
