# E2E Happy Path Test — Full Customer Journey

Covers issue #54. Exercises every service in a realistic sequence against a live stack.

## Prerequisites

- Docker and Docker Compose installed
- `jq` installed (`brew install jq` on macOS)
- A clean stack with all volumes reset:

  ```bash
  docker compose down -v
  docker compose up --build -d
  ```

- Wait until all services are healthy (~60–90 s). MongoDB replica set init, Neo4j seed, and Kafka topic creation all run on startup:

  ```bash
  docker compose ps
  # All containers should show "healthy" or "running (healthy)"
  ```

## ID system note

MongoDB restaurant IDs are 24-character ObjectIDs (e.g., `64b8f1c2e4b0a1234567890a`), **not** UUIDs. The order service requires `restaurant_id` to be a UUID and also requires it to match the auth UUID of the restaurant user who will later update the order status. Therefore:

- The restaurant **auth user's UUID** from step 1 is used as `restaurant_id` in the order.
- The MongoDB catalog is browsed in step 2 for menu discovery only; its ObjectIDs are not used in the order payload.
- The routing API test in step 6 uses the Neo4j-seeded Burger Palace UUID `00000000-0000-0000-0000-000000000101`, which is independent of both the MongoDB catalog and the auth UUID.

---

## Step 0 — Set base URL

```bash
BASE_URL=http://localhost
```

---

## Step 1 — Auth: Register and login

### 1a. Register the restaurant auth user

```bash
RESTAURANT_REG=$(curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "restaurant@test.com", "password": "pass123", "role": "restaurant"}')
echo $RESTAURANT_REG
RESTAURANT_ID=$(echo $RESTAURANT_REG | jq -r '.id')
echo "RESTAURANT_ID=$RESTAURANT_ID"
```

**Expected:** HTTP 201

```json
{"id": "<uuid>", "email": "restaurant@test.com", "role": "restaurant"}
```

### 1b. Register the customer

```bash
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "customer@test.com", "password": "pass123", "role": "customer"}'
```

**Expected:** HTTP 201

```json
{"id": "<uuid>", "email": "customer@test.com", "role": "customer"}
```

### 1c. Login as customer — save token

```bash
TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "customer@test.com", "password": "pass123"}' \
  | jq -r '.access_token')
echo "TOKEN=$TOKEN"
```

**Expected:** HTTP 200, body contains `access_token`.

### 1d. Login as restaurant — save restaurant token

```bash
RESTAURANT_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "restaurant@test.com", "password": "pass123"}' \
  | jq -r '.access_token')
echo "RESTAURANT_TOKEN=$RESTAURANT_TOKEN"
```

**Expected:** HTTP 200

---

## Step 2 — Restaurant Catalog: Browse menu

### 2a. List restaurants

```bash
curl -s "$BASE_URL/api/restaurants" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** HTTP 200

```json
{
  "items": [
    {"id": "<24-char-objectid>", "name": "Burger Palace", "cuisine": "American", ...},
    {"id": "<24-char-objectid>", "name": "Sushi Garden", "cuisine": "Japanese", ...}
  ],
  "total": 2
}
```

### 2b. Get menu for the first restaurant

```bash
MONGO_RESTAURANT_ID=$(curl -s "$BASE_URL/api/restaurants" | jq -r '.items[0].id')
curl -s "$BASE_URL/api/restaurants/$MONGO_RESTAURANT_ID/menu" | jq .
```

**Expected:** HTTP 200, list of menu items each with `id`, `name`, `price`, `is_available`.

> The `id` values here are MongoDB ObjectID strings, not UUIDs. `$RESTAURANT_ID` from step 1 is used in the order below.

---

## Step 3 — Order: Place an order

`restaurant_id` is the restaurant auth user's UUID from step 1.  
`menu_item_id` is any valid UUID; the order service does not validate it against the catalog.

```bash
ORDER=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"restaurant_id\": \"$RESTAURANT_ID\",
    \"items\": [
      {
        \"menu_item_id\": \"00000000-0000-0000-0000-000000000999\",
        \"name\": \"Classic Cheeseburger\",
        \"quantity\": 2,
        \"unit_price\": 8.99
      }
    ]
  }")
echo $ORDER | jq .
ORDER_ID=$(echo $ORDER | jq -r '.id')
echo "ORDER_ID=$ORDER_ID"
```

**Expected:** HTTP 201

```json
{
  "id": "<order-uuid>",
  "customer_id": "<customer-uuid>",
  "restaurant_id": "<restaurant-uuid>",
  "courier_id": null,
  "status": "PLACED",
  "total_price": 17.98,
  "items": [...],
  "created_at": "..."
}
```

---

## Step 4 — Order: Check status

```bash
curl -s "$BASE_URL/api/orders/$ORDER_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{id: .id, status: .status}'
```

**Expected:** HTTP 200, `"status": "PLACED"`

---

## Step 5 — Order: Update status to PREPARING (triggers Kafka event)

Only the restaurant that owns the order can advance from `PLACED` to `PREPARING`. Use `$RESTAURANT_TOKEN`.

```bash
curl -s -X PATCH "$BASE_URL/api/orders/$ORDER_ID/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "PREPARING"}' | jq '{id: .id, status: .status}'
```

**Expected:** HTTP 200, `"status": "PREPARING"`

When the order service processes this transition it:
1. Updates the status in Postgres
2. Calls `POST /api/routing/match` internally (best-effort courier assignment)
3. Publishes an `order-status-changed` event to Kafka

The Notification Service consumes the event and appends it to its log file.

### Verify Kafka event in Notification Service logs

Wait 3 seconds for the consumer to process, then:

```bash
sleep 3
NOTIF_CONTAINER=$(docker ps --filter "name=notification" --format "{{.Names}}" | head -1)
docker exec "$NOTIF_CONTAINER" cat /app/logs/notifications.log
```

**Expected:** a JSON line containing `"new_status": "PREPARING"` and the `order_id`.

Example log line:
```json
{"order_id": "<order-uuid>", "customer_id": "<uuid>", "restaurant_id": "<uuid>", "courier_id": null, "previous_status": "PLACED", "new_status": "PREPARING", "timestamp": "..."}
```

---

## Step 6 — Routing: Courier assigned

Tests the routing API directly using the Neo4j-seeded Burger Palace restaurant UUID.

> This is a `POST` endpoint with a JSON body — not `GET` with query parameters.

```bash
curl -s -X POST "$BASE_URL/api/routing/match" \
  -H "Content-Type: application/json" \
  -d "{
    \"order_id\": \"$ORDER_ID\",
    \"restaurant_id\": \"00000000-0000-0000-0000-000000000101\"
  }" | jq .
```

**Expected:** HTTP 200

```json
{
  "order_id": "<order-uuid>",
  "courier_id": "00000000-0000-0000-0000-000000000201",
  "estimated_minutes": 1
}
```

`00000000-0000-0000-0000-000000000201` is Ivan Petrenko — seeded as `AVAILABLE` in the Podil zone, the same zone as Burger Palace.

---

## Step 7 — Auth: Logout

```bash
curl -s -X POST "$BASE_URL/api/auth/logout" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** HTTP 200, `{"message": "Logged out"}`

The JWT's `jti` claim is deleted from Redis. Any subsequent request with this token will fail validation.

---

## Step 8 — Auth: Token invalidated

Use the **same `$TOKEN`** — it must now be rejected.

```bash
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/orders/$ORDER_ID" \
  -H "Authorization: Bearer $TOKEN")
echo "Expected 401, got: $HTTP_CODE"
```

**Expected:** `401`

The order service calls `GET /api/auth/validate`. Auth looks up the `jti` in Redis — it no longer exists — returns 401. The order service propagates it.

---

## Acceptance Checklist

- [ ] Step 1: both registers return 201; both logins return 200 with JWT
- [ ] Step 2: restaurant list returns 200 with 2 restaurants; menu returns 200 with items
- [ ] Step 3: order creation returns 201 with `order_id` and `"status": "PLACED"`
- [ ] Step 4: GET order returns 200 with `"status": "PLACED"`
- [ ] Step 5: PATCH returns 200 with `"status": "PREPARING"`; notification log contains Kafka event
- [ ] Step 6: routing POST returns 200 with `courier_id`
- [ ] Step 7: logout returns 200
- [ ] Step 8: same token returns 401