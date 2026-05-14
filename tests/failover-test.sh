#!/usr/bin/env bash
# =============================================================================
# MealMate Order Service — Failover Test
# =============================================================================
# Verifies: duplicated order service survives instance failure with no data loss.
#
# Prerequisites:  docker compose up -d
# Usage:          bash tests/failover-test.sh
# =============================================================================
set -euo pipefail

# --- Config ---
GATEWAY="http://localhost"
RESTAURANT_ID="550e8400-e29b-41d4-a716-446655440001"
TEST_EMAIL="failover-${RANDOM}@test.com"

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS=0; FAIL=0

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; ((PASS++)) || true; }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; ((FAIL++)) || true; }
info() { echo -e "  ${CYAN}ℹ️${NC}  $1"; }
log()  { echo ""; echo -e "${CYAN}── $1 ──${NC}"; }

# --- HTTP helpers (fixed temp files avoid subshell variable loss) ---
_B=$(mktemp --tmpdir failover.XXXXXX)
_C=$(mktemp --tmpdir failover.XXXXXX)
trap 'rm -f "$_B" "$_C"' EXIT

http() {
    local method="$1" url="$2" data="${3:-}" token="${4:-}"
    local args=(-s -o "$_B" -w "%{http_code}")
    [[ -n "$data"  ]] && args+=(-d "$data" -H "Content-Type: application/json")
    [[ -n "$token" ]] && args+=(-H "Authorization: Bearer $token")
    [[ "$method" != "GET" ]] && args+=(-X "$method")
    curl "${args[@]}" "$url" > "$_C" 2>/dev/null || echo "000" > "$_C"
}
get()  { http GET  "$1" "" "${2:-}"; }
post() { http POST "$1" "$2" "${3:-}"; }
rc()   { cat "$_C"; }
field() { python3 -c "import json; print(json.load(open('$_B'))['$1'])"; }

# --- Docker helpers ---
cname() { docker compose ps --format '{{.Name}}' 2>/dev/null | grep -E "mealmate-${1}-[0-9]+" | head -1; }

wait_healthy() {
    local svc="$1" elapsed=0
    while [[ $elapsed -lt 60 ]]; do
        local n; n=$(cname "$svc" 2>/dev/null || true)
        [[ -z "$n" ]] && { sleep 2; ((elapsed+=2)) || true; continue; }
        local h; h=$(docker inspect --format='{{.State.Health.Status}}' "$n" 2>/dev/null || echo "?")
        [[ "$h" == "healthy" ]] && return 0
        sleep 2; ((elapsed+=2)) || true
    done; return 1
}

# --- Resolve containers ---
ORDER1=$(cname "order");   ORDER2=$(cname "order-2")
[[ -z "$ORDER1" ]] && { fail "order-1 container not found"; exit 1; }
[[ -z "$ORDER2" ]] && { fail "order-2 container not found"; exit 1; }

# Make sure both are up (recover from a previous run)
docker start "$ORDER1" 2>/dev/null || true
docker start "$ORDER2" 2>/dev/null || true
info "Waiting for both order instances..."
wait_healthy "order"; wait_healthy "order-2"

# =========================================================================
log "1. Verify both instances are healthy"
# =========================================================================
get "$GATEWAY/health/order"
[[ $(rc) == "200" ]] && pass "order backend healthy" || fail "order backend unhealthy (HTTP $(rc))"

# =========================================================================
log "2. Register, login, create order"
# =========================================================================
post "$GATEWAY/api/auth/register" \
    "{\"email\":\"$TEST_EMAIL\",\"password\":\"secret123\",\"role\":\"customer\"}"
[[ $(rc) == "201" ]] && pass "Registered user" || fail "Register failed (HTTP $(rc))"

post "$GATEWAY/api/auth/login" \
    "{\"email\":\"$TEST_EMAIL\",\"password\":\"secret123\"}"
[[ $(rc) == "200" ]] && pass "Logged in" || { fail "Login failed (HTTP $(rc))"; exit 1; }
TOKEN=$(field "access_token")

post "$GATEWAY/api/orders" \
    "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"11111111-1111-1111-1111-111111111111\",\"name\":\"Pizza\",\"quantity\":2,\"unit_price\":12.50}]}" \
    "$TOKEN"
[[ $(rc) == "201" ]] && pass "Created order" || { fail "Create order failed (HTTP $(rc))"; exit 1; }
ORDER_ID=$(field "id")
info "Order ID: $ORDER_ID"

# =========================================================================
log "3. Kill order-1"
# =========================================================================
docker stop "$ORDER1" >/dev/null 2>&1
sleep 2  # let nginx detect the failure
pass "order-1 stopped"

# =========================================================================
log "4. Verify failover — all requests succeed via order-2"
# =========================================================================

# 4a: Read the order created before the kill
get "$GATEWAY/api/orders/$ORDER_ID" "$TOKEN"
[[ $(rc) == "200" ]] && pass "Read order after kill → 200 (shared Postgres)" \
                      || fail "Read order failed (HTTP $(rc))"

# 4b: Create a new order after the kill
post "$GATEWAY/api/orders" \
    "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"22222222-2222-2222-2222-222222222222\",\"name\":\"Pasta\",\"quantity\":1,\"unit_price\":8.00}]}" \
    "$TOKEN"
[[ $(rc) == "201" ]] && pass "Created order after kill → 201 (surviving instance)" \
                      || fail "Create after kill failed (HTTP $(rc))"

# 4c: JWT still works (session preserved in shared Redis)
get "$GATEWAY/api/orders" "$TOKEN"
[[ $(rc) == "200" ]] && pass "JWT still valid after kill (shared Redis)" \
                      || fail "JWT rejected (HTTP $(rc))"

# =========================================================================
log "5. Cleanup — restart order-1"
# =========================================================================
docker start "$ORDER1" >/dev/null 2>/dev/null || true
wait_healthy "order"
pass "order-1 restarted"

# =========================================================================
# Results
# =========================================================================
echo ""
TOTAL=$((PASS + FAIL))
echo -e "  Total: ${TOTAL}   ${GREEN}Passed: ${PASS}${NC}   ${RED}Failed: ${FAIL}${NC}"
