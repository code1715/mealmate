# Kafka Consumer Group Offset Persistence: Message Durability Test

Covers issue #59. Verifies that Kafka retains messages while the Notification Service is offline and delivers all of them in order when the consumer restarts.

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

The Notification Service subscribes to the `order-status-changed` topic using a named consumer group:

```python
Consumer({
    "bootstrap.servers": brokers,
    "group.id": "notification-group",   # named group — offsets are persisted in Kafka
    "auto.offset.reset": "earliest",    # on first start: read from beginning of topic
    "enable.auto.commit": False,        # offsets committed only after successful processing
})
```

`enable.auto.commit: False` with explicit `consumer.commit(message=msg)` after each successful message guarantees exactly-once processing (at-least-once with idempotent handling). When the consumer is offline, Kafka retains all new messages. On restart, the consumer resumes from the last committed offset — no messages are lost.

---

## Step 0 — Set base URL and create test users

```bash
BASE_URL=http://localhost

# Register restaurant auth user
RESTAURANT_REG=$(curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "kafka-restaurant@test.com", "password": "pass123", "role": "restaurant"}')
RESTAURANT_ID=$(echo $RESTAURANT_REG | jq -r '.id')

# Register customer
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "kafka-customer@test.com", "password": "pass123", "role": "customer"}' > /dev/null

# Login both
CUSTOMER_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "kafka-customer@test.com", "password": "pass123"}' | jq -r '.access_token')
RESTAURANT_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "kafka-restaurant@test.com", "password": "pass123"}' | jq -r '.access_token')

echo "RESTAURANT_ID=$RESTAURANT_ID"
```

---

## Step 1 — Confirm Notification Service is running

```bash
docker compose ps | grep notification
docker compose logs notification --tail=5
```

**Expected:** `notification` shows `Up (healthy)`. Logs show the consumer thread started.

---

## Step 2 — Let the consumer establish its baseline committed offset

If this is a freshly started stack, create and advance one order so the consumer commits its first offset. This ensures the LAG counter works correctly in the next steps:

```bash
BASELINE_ORDER=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000001\",\"name\":\"Item\",\"quantity\":1,\"unit_price\":5.00}]}" | jq -r '.id')
curl -s -X PATCH "$BASE_URL/api/orders/$BASELINE_ORDER/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"PREPARING"}' > /dev/null
sleep 3
```

Verify the consumer processed it and LAG = 0:

```bash
docker exec mealmate-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group notification-group
```

**Expected:** all partitions show `LAG 0`.

---

## Step 3 — Stop the Notification Service

```bash
docker stop mealmate-notification-1
```

---

## Step 4 — Create 3 orders and publish 3 status events while consumer is offline

```bash
# Create 3 orders
O1=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000011\",\"name\":\"Pasta\",\"quantity\":1,\"unit_price\":11.99}]}" | jq -r '.id')
O2=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000012\",\"name\":\"Salad\",\"quantity\":1,\"unit_price\":8.50}]}" | jq -r '.id')
O3=$(curl -s -X POST "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $CUSTOMER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"restaurant_id\":\"$RESTAURANT_ID\",\"items\":[{\"menu_item_id\":\"00000000-0000-0000-0000-000000000013\",\"name\":\"Soup\",\"quantity\":2,\"unit_price\":6.00}]}" | jq -r '.id')

echo "O1=$O1  O2=$O2  O3=$O3"

# Advance each order to PREPARING — each triggers a Kafka event
curl -s -X PATCH "$BASE_URL/api/orders/$O1/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"PREPARING"}' | jq -r '.status'
curl -s -X PATCH "$BASE_URL/api/orders/$O2/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"PREPARING"}' | jq -r '.status'
curl -s -X PATCH "$BASE_URL/api/orders/$O3/status" \
  -H "Authorization: Bearer $RESTAURANT_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"PREPARING"}' | jq -r '.status'
```

**Expected:** all three return `"PREPARING"`.

---

## Step 5 — Verify messages are held in Kafka (LAG ≥ 3)

```bash
sleep 2
docker exec mealmate-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group notification-group
```

**Expected:** partitions with committed offsets show `LAG 1` each (3 total). Any partition without a prior committed offset also has 1 unprocessed message — confirmed with:

```bash
docker exec mealmate-kafka-1 kafka-get-offsets \
  --bootstrap-server localhost:9092 \
  --topic order-status-changed
```

The sum of `(LOG-END-OFFSET − committed offset)` across all partitions equals 3.

Example output:
```
Consumer group 'notification-group' has no active members.

GROUP              TOPIC                PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
notification-group order-status-changed 0          -               1               -
notification-group order-status-changed 1          1               2               1
notification-group order-status-changed 2          2               3               1
```

Partition 0 shows `-` because no offset was ever committed there (auto.offset.reset=earliest will catch it on restart).

---

## Step 6 — Restart the Notification Service

```bash
docker start mealmate-notification-1
sleep 8
```

---

## Step 7 — Verify all 3 messages processed

```bash
docker compose logs notification --tail=20 | grep -E "Processing|dispatched"
```

**Expected:** all 3 order IDs appear in the logs, in the order they were processed:

```
INFO:app.service.notification_service:Processing notification for order=<O1> transition=PLACED→PREPARING
INFO:app.repository.notification_repository:Notification dispatched: order=<O1> ...
INFO:app.service.notification_service:Processing notification for order=<O2> transition=PLACED→PREPARING
INFO:app.repository.notification_repository:Notification dispatched: order=<O2> ...
INFO:app.service.notification_service:Processing notification for order=<O3> transition=PLACED→PREPARING
INFO:app.repository.notification_repository:Notification dispatched: order=<O3> ...
```

Verify LAG is back to 0:

```bash
docker exec mealmate-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group notification-group
```

**Expected:** all partitions show `LAG 0`.

---

## Acceptance Checklist

- [ ] Step 5: `kafka-consumer-groups --describe` shows LAG ≥ 1 per populated partition (3 total unprocessed)
- [ ] Step 7: all 3 order IDs appear in the notification logs after restart
- [ ] Step 7: LAG returns to 0 on all partitions
- [ ] No messages are lost (0 missing from logs) or duplicated (3 unique order IDs)
- [ ] Consumer group uses named `group.id: notification-group` — confirmed in `kafka-consumer-groups --list`