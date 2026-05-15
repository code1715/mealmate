# Order → Kafka → Notification Integration Test

Covers issue #60. Verifies the full async event chain between Order Service and Notification Service under normal operating conditions: latency, event format correctness, schema-error handling, and dead-letter behaviour.

## Prerequisites

- Docker and Docker Compose installed
- `jq` installed (`brew install jq` on macOS)
- A clean stack with all volumes reset:

  ```bash
  docker compose down -v
  docker compose up --build -d
  ```

- Wait until all services are healthy (~60–90 s):

  ```bash
  docker compose ps
  # All containers should show "healthy" or "running (healthy)"
  ```

## Architecture note

When a restaurant advances an order from `PLACED → PREPARING`, the Order Service:

1. Updates the order status in Postgres.
2. Calls `kafka_producer.produce()` + `flush(timeout=5.0)` **within the same HTTP request handler** — the REST response is not returned until the event is flushed to Kafka.
3. Returns HTTP 200.

The Notification Service runs a background thread polling the `order-status-changed` topic every 1 second. Failed messages are retried up to 3 times; after 3 failures the raw payload is logged as a `DEAD_LETTER` and the offset is committed (to avoid infinite re-delivery).

Event payload produced by the Order Service:

```json
{
  "order_id": "<uuid>",
  "customer_id": "<uuid>",
  "restaurant_id": "<uuid>",
  "courier_id": "<uuid-or-null>",
  "previous_status": "PLACED",
  "new_status": "PREPARING",
  "timestamp": "2024-01-01T12:00:00.000000+00:00"
}
```

---

## Step 0 — Set base URL and create test users

```bash
BASE_URL=http://localhost

# Register restaurant auth user
RESTAURANT_REG=$(curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "integration-restaurant@test.com", "password": "pass123", "role": "restaurant"}')
RESTAURANT_ID=$(echo $RESTAURANT_REG | jq -r '.id')

# Register customer
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "integration-customer@test.com", "password": "pass123", "role": "customer"}' > /dev/null

# Login both
CUSTOMER_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "integration-customer@test.com", "password": "pass123"}' | jq -r '.access_token')
RESTAURANT_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "integration-restaurant@test.com", "password": "pass123"}' | jq -r '.access_token')

echo "RESTAURANT_ID=$RESTAURANT_ID"
```

---

## Step 1 — Confirm Notification Service is running

```bash
docker compose ps | grep notification
docker compose logs notification --tail=5
```

**Expected:** `notification` shows `Up (healthy)`. Logs show `Kafka consumer started`.

---

## Step 2 — Open a live log stream in a second terminal

```bash
docker compose logs -f notification 2>&1 | grep -E "Processing|dispatched|DEAD_LETTER|Failed"
```

Leave this running. All subsequent events appear here within 2 seconds of the API call.

---

## Step 3 — Place an order and advance it to PREPARING

```bash
ORDER=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"restaurant_id\": \"$RESTAURANT_ID\",
    \"items\": [{
      \"menu_item_id\": \"00000000-0000-0000-0000-000000000999\",
      \"name\": \"Classic Cheeseburger\",
      \"quantity\": 1,
      \"unit_price\": 9.99
    }]
  }")
ORDER_ID=$(echo $ORDER | jq -r '.id')
echo "ORDER_ID=$ORDER_ID"

curl -s -X PATCH "$BASE_URL/api/orders/$ORDER_ID/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "PREPARING"}' | jq -r '.status'
```

**Expected:** PATCH returns `"PREPARING"`.

---

## Step 4 — Verify the event appeared in Notification Service within 2 seconds

In the live log stream (step 2) or by tailing logs:

```bash
docker compose logs notification --tail=10
```

**Expected:** two log lines containing the order ID within 2 seconds:

```
INFO:app.service.notification_service:Processing notification for order=<ORDER_ID> transition=PLACED→PREPARING
INFO:app.repository.notification_repository:Notification dispatched: order=<ORDER_ID> status=PLACED→PREPARING customer=<CUSTOMER_ID>
```

Also verify the notification file was written:

```bash
docker exec mealmate-notification-1 cat /app/logs/notifications.log | tail -1 | jq .
```

**Expected:** JSON line containing all required fields:

```json
{
  "order_id": "<ORDER_ID>",
  "customer_id": "<CUSTOMER_ID>",
  "restaurant_id": "<RESTAURANT_ID>",
  "courier_id": null,
  "previous_status": "PLACED",
  "new_status": "PREPARING",
  "timestamp": "..."
}
```

---

## Step 5 — Verify event published within the same HTTP request (latency check)

The Order Service flushes to Kafka before returning the HTTP response. Verify the Kafka event is already in the topic log by the time the API call completes:

```bash
# Check current end offset for the topic immediately after the PATCH
docker exec mealmate-kafka-1 kafka-get-offsets \
  --bootstrap-server localhost:9092 \
  --topic order-status-changed
```

The log-end-offset across partitions should have incremented (≥ previous value + 1).

---

## Step 6 — Schema validation: inject a malformed message

Produce a message with a missing required field (`order_id`) directly to Kafka:

```bash
echo '{"customer_id":"bad","restaurant_id":"bad","previous_status":"X","new_status":"Y","timestamp":"now"}' | \
  docker exec -i mealmate-kafka-1 kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic order-status-changed
```

Wait 3 seconds, then check the notification logs:

```bash
sleep 3
docker compose logs notification --tail=15 | grep -E "Failed|DEAD_LETTER|warning|attempt"
```

**Expected:** The consumer logs a clear error (not silent) including the raw payload, then retries up to 3 times, and finally logs a `DEAD_LETTER` line:

```
ERROR:app.consumer.kafka_consumer:Failed to parse Kafka message: ... — raw=b'{"customer_id":...}'
WARNING:app.consumer.kafka_consumer:Processing failed (attempt 1/3) — partition=... offset=...
ERROR:app.consumer.kafka_consumer:Failed to parse Kafka message: ...
WARNING:app.consumer.kafka_consumer:Processing failed (attempt 2/3) — partition=... offset=...
ERROR:app.consumer.kafka_consumer:Failed to parse Kafka message: ...
ERROR:app.consumer.kafka_consumer:DEAD_LETTER: message exhausted 3 retries — partition=... offset=... raw=...
```

The consumer does not crash. The offset is committed after the dead-letter log, so the next valid message is processed normally.

---

## Step 7 — Verify normal processing resumes after the malformed message

```bash
ORDER2=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"restaurant_id\": \"$RESTAURANT_ID\",
    \"items\": [{
      \"menu_item_id\": \"00000000-0000-0000-0000-000000000998\",
      \"name\": \"Fries\",
      \"quantity\": 1,
      \"unit_price\": 3.50
    }]
  }")
ORDER2_ID=$(echo $ORDER2 | jq -r '.id')

curl -s -X PATCH "$BASE_URL/api/orders/$ORDER2_ID/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "PREPARING"}' > /dev/null

sleep 3
docker compose logs notification --tail=5
```

**Expected:** the notification for ORDER2 appears within 2 seconds. The bad message did not break the consumer.

---

## Acceptance Checklist

- [ ] Step 3: PATCH returns HTTP 200 with `"status": "PREPARING"`
- [ ] Step 4: Notification Service logs both `Processing notification` and `Notification dispatched` lines within 2 seconds
- [ ] Step 4: `/app/logs/notifications.log` entry contains `order_id`, `customer_id`, `previous_status`, `new_status`, `timestamp`
- [ ] Step 5: Kafka log-end-offset increments before HTTP response returns (synchronous flush confirmed)
- [ ] Step 6: Malformed message logs a clear error with the raw payload — consumer does NOT crash
- [ ] Step 6: Consumer retries the malformed message 3 times, then logs `DEAD_LETTER` and commits the offset
- [ ] Step 7: Normal message processed correctly after the dead-letter — consumer is healthy