#!/usr/bin/env bash
# =============================================================================
# MealMate — Message Durability Test (Issue #51)
# =============================================================================
# Proves Kafka retains messages while the notification consumer is offline and
# delivers them once it reconnects — verifying Kafka's at-least-once guarantee
# over a basic in-memory queue.
#
# Prerequisites: docker compose up -d (all services healthy)
# Usage:         bash tests/message-durability-test.sh
# Evidence:      Output is tee'd to docs/test-evidence/message-durability-test.txt
# =============================================================================
set -euo pipefail

GATEWAY="http://localhost"
SUFFIX="$$"
EVIDENCE_DIR="$(cd "$(dirname "$0")/.." && pwd)/docs/test-evidence"
EVIDENCE_FILE="$EVIDENCE_DIR/message-durability-test.txt"
CONSUMER_GROUP="notification-group"

mkdir -p "$EVIDENCE_DIR"
# Tee all output to the evidence file
exec > >(tee "$EVIDENCE_FILE") 2>&1

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

wait_for_lag_zero() {
    local max_attempts=30
    local i=0
    info "Waiting for consumer group $CONSUMER_GROUP to reach LAG=0 ..."
    while [[ $i -lt $max_attempts ]]; do
        local output
        output=$(docker compose exec -T kafka \
            kafka-consumer-groups \
            --bootstrap-server localhost:9092 \
            --group "$CONSUMER_GROUP" \
            --describe 2>/dev/null || echo "")
        # Check if all data rows (non-header) have LAG = 0
        if echo "$output" | python3 -c "
import sys
lines = [l for l in sys.stdin.read().splitlines() if l.strip() and not l.startswith('GROUP')]
if not lines:
    sys.exit(1)  # no consumer yet, keep waiting
for line in lines:
    parts = line.split()
    # LAG is the 6th column (index 5), but only in data rows with enough fields
    if len(parts) >= 6:
        lag = parts[5]
        if lag != '0':
            sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
            pass "Consumer group LAG=0 (all messages consumed)"
            echo ""
            info "kafka-consumer-groups --describe output:"
            echo "$output"
            return 0
        fi
        sleep 1
        ((i++)) || true
    done
    fail "Consumer group did not reach LAG=0 within ${max_attempts}s"
    info "Final kafka-consumer-groups output:"
    docker compose exec -T kafka \
        kafka-consumer-groups \
        --bootstrap-server localhost:9092 \
        --group "$CONSUMER_GROUP" \
        --describe 2>/dev/null || true
    return 1
}

verify_event_order() {
    local order_id="$1"
    local LOG
    LOG=$(docker compose exec -T notification cat /app/logs/notifications.log 2>/dev/null || echo "")
    python3 -c "
import os, sys, json
order_id = '$order_id'
events = []
for line in '''$LOG'''.splitlines():
    try:
        e = json.loads(line)
        if e.get('order_id') == order_id:
            events.append(e.get('new_status'))
    except Exception:
        pass

expected = ['PREPARING', 'READY', 'PICKED_UP']
if events == expected:
    print('  Events in correct order: ' + ' → '.join(events))
    sys.exit(0)
else:
    print('  Expected order: ' + str(expected), file=sys.stderr)
    print('  Actual order:   ' + str(events), file=sys.stderr)
    sys.exit(1)
" 2>/dev/null
}

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "  MealMate — Message Durability Test"
echo -e "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"

# ── 1. Setup: register users ───────────────────────────────────────────────
log "1. Register customer and restaurant"

post "$GATEWAY/api/auth/register" \
    "{\"email\":\"dur-customer-$SUFFIX@test.com\",\"password\":\"secret123\",\"role\":\"customer\"}"
[[ $(rc) == "201" ]] || { fail "Register customer (HTTP $(rc))"; cat "$_B"; exit 1; }
CUSTOMER_ID=$(field "id")
info "Customer ID: $CUSTOMER_ID"

post "$GATEWAY/api/auth/register" \
    "{\"email\":\"dur-restaurant-$SUFFIX@test.com\",\"password\":\"secret123\",\"role\":\"restaurant\"}"
[[ $(rc) == "201" ]] || { fail "Register restaurant (HTTP $(rc))"; cat "$_B"; exit 1; }
RESTAURANT_ID=$(field "id")
info "Restaurant ID: $RESTAURANT_ID"

# ── 2. Login ───────────────────────────────────────────────────────────────
log "2. Login"

post "$GATEWAY/api/auth/login" \
    "{\"email\":\"dur-customer-$SUFFIX@test.com\",\"password\":\"secret123\"}"
[[ $(rc) == "200" ]] || { fail "Login customer (HTTP $(rc))"; exit 1; }
CUSTOMER_TOKEN=$(field "access_token")

post "$GATEWAY/api/auth/login" \
    "{\"email\":\"dur-restaurant-$SUFFIX@test.com\",\"password\":\"secret123\"}"
[[ $(rc) == "200" ]] || { fail "Login restaurant (HTTP $(rc))"; exit 1; }
RESTAURANT_TOKEN=$(field "access_token")
pass "Both users authenticated"

# ── 3. Create order ────────────────────────────────────────────────────────
log "3. Create order"

post "$GATEWAY/api/orders" \
    "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000001\",\"quantity\":1,\"unit_price\":10.00}]}" \
    "$CUSTOMER_TOKEN"
[[ $(rc) == "201" ]] || { fail "Create order (HTTP $(rc))"; cat "$_B"; exit 1; }
ORDER_ID=$(field "id")
info "Order ID: $ORDER_ID"
pass "Order created (status: PLACED)"

# ── 4. Stop notification consumer ─────────────────────────────────────────
log "4. Stop notification consumer"

docker compose stop notification
pass "Notification container stopped"
info "Kafka will retain messages until consumer reconnects"

# ── 5. Produce 3 events while consumer is offline ─────────────────────────
log "5. Produce 3 events while notification consumer is offline"

# Event 1: PLACED → PREPARING via Order Service API
patch "$GATEWAY/api/orders/$ORDER_ID/status" \
    "{\"status\":\"PREPARING\"}" \
    "$RESTAURANT_TOKEN"
[[ $(rc) == "200" ]] || { fail "PLACED → PREPARING (HTTP $(rc))"; cat "$_B"; docker compose start notification; exit 1; }
pass "Event 1 produced: PLACED → PREPARING (Order Service API)"

# Event 2: PREPARING → READY via Order Service API
patch "$GATEWAY/api/orders/$ORDER_ID/status" \
    "{\"status\":\"READY\"}" \
    "$RESTAURANT_TOKEN"
[[ $(rc) == "200" ]] || { fail "PREPARING → READY (HTTP $(rc))"; cat "$_B"; docker compose start notification; exit 1; }
pass "Event 2 produced: PREPARING → READY (Order Service API)"

# Event 3: READY → PICKED_UP direct to Kafka (routing service is a stub)
KAFKA_MSG=$(ORDER_ID="$ORDER_ID" CUSTOMER_ID="$CUSTOMER_ID" RESTAURANT_ID="$RESTAURANT_ID" python3 -c "
import os, json
print(json.dumps({
    'order_id': os.environ['ORDER_ID'],
    'customer_id': os.environ['CUSTOMER_ID'],
    'restaurant_id': os.environ['RESTAURANT_ID'],
    'courier_id': None,
    'previous_status': 'READY',
    'new_status': 'PICKED_UP',
    'timestamp': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")',
}))
")
if echo "$KAFKA_MSG" | docker compose exec -T kafka \
    kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic order-status-changed 2>/dev/null; then
    pass "Event 3 produced: READY → PICKED_UP (direct Kafka)"
else
    fail "kafka-console-producer failed"
    docker compose start notification
    exit 1
fi

info "All 3 events are queued in Kafka. Consumer is still offline."

# ── 6. Restart notification consumer ──────────────────────────────────────
log "6. Restart notification consumer"

docker compose start notification

# Wait for the container to be healthy
info "Waiting for notification service to become healthy ..."
healthy=false
for i in $(seq 1 30); do
    STATUS=$(docker compose ps notification --format '{{.Health}}' 2>/dev/null || echo "")
    if [[ "$STATUS" == "healthy" ]]; then
        healthy=true
        break
    fi
    sleep 2
done

if $healthy; then
    pass "Notification service is healthy and consuming"
else
    fail "Notification service did not become healthy within 60s"
    exit 1
fi

# ── 7. Wait for LAG = 0 ────────────────────────────────────────────────────
log "7. Verify consumer group catches up (LAG = 0)"

wait_for_lag_zero

# ── 8. Verify all 3 events in notifications.log in correct order ──────────
log "8. Verify events in notifications.log"

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
    || fail "Expected 3 events, found $EVENT_COUNT for order $ORDER_ID"

# Verify ordering
EVENTS_ORDERED=$(echo "$LOG" | ORDER_ID="$ORDER_ID" python3 -c "
import os, sys, json
order_id = os.environ['ORDER_ID']
events = []
for line in sys.stdin.read().splitlines():
    try:
        e = json.loads(line)
        if e.get('order_id') == order_id:
            events.append(e.get('new_status'))
    except Exception:
        pass
expected = ['PREPARING', 'READY', 'PICKED_UP']
if events[:3] == expected:
    print('correct: ' + ' → '.join(events[:3]))
    sys.exit(0)
else:
    print('wrong order — expected: ' + str(expected) + ' got: ' + str(events), file=sys.stderr)
    sys.exit(1)
")
if [[ $? -eq 0 ]]; then
    pass "Events processed in correct order: $EVENTS_ORDERED"
else
    fail "Events not in correct order"
fi

# Print log entries for this order
info "notifications.log entries for order $ORDER_ID:"
echo "$LOG" | ORDER_ID="$ORDER_ID" python3 -c "
import os, sys, json
order_id = os.environ['ORDER_ID']
for line in sys.stdin.read().splitlines():
    try:
        e = json.loads(line)
        if e.get('order_id') == order_id:
            print('  ' + line)
    except Exception:
        pass
"

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Evidence saved to: $EVIDENCE_FILE"
[[ $FAIL -eq 0 ]]
