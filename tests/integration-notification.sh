#!/usr/bin/env bash
# =============================================================================
# MealMate — Integration Test: Notification Service End-to-End
# =============================================================================
# Verifies: order status changes produce Kafka events that are received and
# persisted by the notification service within 2 seconds.
#
# Prerequisites: docker compose up -d (all services healthy)
# Usage:         bash tests/integration-notification.sh
# =============================================================================
set -euo pipefail

GATEWAY="http://localhost"
SUFFIX="$$"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS=0; FAIL=0

pass() { echo -e "  ${GREEN}✓ PASS${NC}: $1"; ((PASS++)) || true; }
fail() { echo -e "  ${RED}✗ FAIL${NC}: $1"; ((FAIL++)) || true; }
info() { echo -e "  ${CYAN}→${NC}  $1"; }
log()  { echo ""; echo -e "${CYAN}── $1 ──${NC}"; }

_B=$(mktemp)
_C=$(mktemp)
trap 'rm -f "$_B" "$_C"' EXIT

http() {
    local method="$1" url="$2" data="${3:-}" token="${4:-}"
    local args=(-s -o "$_B" -w "%{http_code}")
    [[ -n "$data"  ]] && args+=(-d "$data" -H "Content-Type: application/json")
    [[ -n "$token" ]] && args+=(-H "Authorization: Bearer $token")
    [[ "$method" != "GET" ]] && args+=(-X "$method")
    curl "${args[@]}" "$url" > "$_C" 2>/dev/null || echo "000" > "$_C"
}
get()   { http GET   "$1" ""   "${2:-}"; }
post()  { http POST  "$1" "$2" "${3:-}"; }
patch() { http PATCH "$1" "$2" "${3:-}"; }
rc()    { cat "$_C"; }
field() {
    python3 -c "
import json, sys
try:
    d = json.load(open('$_B'))
    print(d['$1'])
except KeyError:
    print('ERROR: key [$1] not in response: ' + open('$_B').read(), file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print('ERROR: ' + str(e), file=sys.stderr)
    sys.exit(1)
"
}

wait_for_event() {
    local order_id="$1" new_status="$2" label="$3"
    local i=0
    while [[ $i -lt 10 ]]; do
        local LOG
        LOG=$(docker compose exec -T notification cat /app/logs/notifications.log 2>/dev/null || echo "")
        if echo "$LOG" | ORDER_ID="$order_id" NEW_STATUS="$new_status" python3 -c "
import os, sys, json
order_id = os.environ['ORDER_ID']
new_status = os.environ['NEW_STATUS']
for line in sys.stdin.read().splitlines():
    try:
        e = json.loads(line)
        if e.get('order_id') == order_id and e.get('new_status') == new_status:
            sys.exit(0)
    except Exception:
        pass
sys.exit(1)" 2>/dev/null; then
            pass "$label"
            return 0
        fi
        sleep 0.2
        ((i++)) || true
    done
    fail "$label — not found in log within 10 attempts"
    return 1
}

# ── 1. Register users ──────────────────────────────────────────────────────
log "1. Register customer and restaurant"

post "$GATEWAY/api/auth/register" \
    "{\"email\":\"customer-$SUFFIX@test.com\",\"password\":\"secret123\",\"role\":\"customer\"}"
[[ $(rc) == "201" ]] || { fail "Register customer (HTTP $(rc))"; cat "$_B"; exit 1; }
CUSTOMER_ID=$(field "id")
info "Customer ID: $CUSTOMER_ID"

post "$GATEWAY/api/auth/register" \
    "{\"email\":\"restaurant-$SUFFIX@test.com\",\"password\":\"secret123\",\"role\":\"restaurant\"}"
[[ $(rc) == "201" ]] || { fail "Register restaurant (HTTP $(rc))"; cat "$_B"; exit 1; }
RESTAURANT_ID=$(field "id")
info "Restaurant ID: $RESTAURANT_ID"

# ── 2. Login ───────────────────────────────────────────────────────────────
log "2. Login"

post "$GATEWAY/api/auth/login" \
    "{\"email\":\"customer-$SUFFIX@test.com\",\"password\":\"secret123\"}"
[[ $(rc) == "200" ]] || { fail "Login customer (HTTP $(rc))"; exit 1; }
CUSTOMER_TOKEN=$(field "access_token")

post "$GATEWAY/api/auth/login" \
    "{\"email\":\"restaurant-$SUFFIX@test.com\",\"password\":\"secret123\"}"
[[ $(rc) == "200" ]] || { fail "Login restaurant (HTTP $(rc))"; exit 1; }
RESTAURANT_TOKEN=$(field "access_token")

# ── 3. Create order ────────────────────────────────────────────────────────
log "3. Create order"

post "$GATEWAY/api/orders" \
    "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000001\",\"quantity\":1,\"unit_price\":10.00}]}" \
    "$CUSTOMER_TOKEN"
[[ $(rc) == "201" ]] || { fail "Create order (HTTP $(rc))"; cat "$_B"; exit 1; }
ORDER_ID=$(field "id")
info "Order ID: $ORDER_ID"
pass "Order created (status: PLACED)"

# ── 4. PLACED → PREPARING (via Order Service API) ─────────────────────────
log "4. Transition: PLACED → PREPARING (Order Service API)"

patch "$GATEWAY/api/orders/$ORDER_ID/status" \
    "{\"status\":\"PREPARING\"}" \
    "$RESTAURANT_TOKEN"
[[ $(rc) == "200" ]] || { fail "PLACED → PREPARING (HTTP $(rc))"; cat "$_B"; exit 1; }
pass "Order Service API accepted PLACED → PREPARING"

wait_for_event "$ORDER_ID" "PREPARING" "Event PLACED→PREPARING in notifications.log within 2 s"

# ── 5. PREPARING → READY (via Order Service API) ──────────────────────────
log "5. Transition: PREPARING → READY (Order Service API)"

patch "$GATEWAY/api/orders/$ORDER_ID/status" \
    "{\"status\":\"READY\"}" \
    "$RESTAURANT_TOKEN"
[[ $(rc) == "200" ]] || { fail "PREPARING → READY (HTTP $(rc))"; cat "$_B"; exit 1; }
pass "Order Service API accepted PREPARING → READY"

wait_for_event "$ORDER_ID" "READY" "Event PREPARING→READY in notifications.log within 2 s"

# ── 6. READY → PICKED_UP (direct Kafka — routing service is a stub) ───────
log "6. Transition: READY → PICKED_UP (direct Kafka)"

KAFKA_MSG=$(python3 -c "import json; print(json.dumps({
    'order_id': '$ORDER_ID',
    'customer_id': '$CUSTOMER_ID',
    'restaurant_id': '$RESTAURANT_ID',
    'courier_id': None,
    'previous_status': 'READY',
    'new_status': 'PICKED_UP',
    'timestamp': '2025-01-15T14:35:00Z'
}))")
if echo "$KAFKA_MSG" | docker compose exec -T kafka \
    kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic order-status-changed 2>/dev/null; then
    pass "READY→PICKED_UP event produced directly to Kafka"
else
    fail "kafka-console-producer failed — is Kafka running?"
    exit 1
fi

wait_for_event "$ORDER_ID" "PICKED_UP" "Event READY→PICKED_UP in notifications.log within 2 s"

# ── 7. Verify all three events persisted in log ───────────────────────────
log "7. Verify all three events in notifications.log"

LOG=$(docker compose exec -T notification cat /app/logs/notifications.log 2>/dev/null || echo "")
EVENT_COUNT=$(echo "$LOG" | ORDER_ID="$ORDER_ID" python3 -c "
import os, sys, json
order_id = os.environ['ORDER_ID']
count = 0
for line in sys.stdin.read().splitlines():
    try:
        e = json.loads(line)
        if e.get('order_id') == order_id:
            count += 1
    except Exception:
        pass
print(count)")

[[ "$EVENT_COUNT" -ge 3 ]] \
    && pass "All 3 events found in notifications.log ($EVENT_COUNT for order $ORDER_ID)" \
    || fail "Expected 3 events in log, found $EVENT_COUNT for order $ORDER_ID"

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
[[ $FAIL -eq 0 ]]
