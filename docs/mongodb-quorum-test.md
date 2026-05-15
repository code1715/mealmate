# MongoDB Replica Set: Read-Only Mode on Quorum Loss

Covers issue #58. Demonstrates that when fewer than 2 of 3 MongoDB nodes are available, the replica set stops accepting writes while reads continue to succeed via the surviving secondary.

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

The Restaurant Catalog Service connects to all three MongoDB nodes via a replica set URI with `readPreference=secondaryPreferred`:

```
mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&readPreference=secondaryPreferred
```

`secondaryPreferred` routes reads to secondary nodes when available, falling back to the primary only if no secondary is reachable. This allows reads to continue on a surviving secondary even when quorum is lost and no primary can be elected.

Write operations are always directed to the primary. When quorum is lost (no primary can be elected), writes fail with `NotWritablePrimary` — the service catches this and returns HTTP 503 with `{"detail": "Database write unavailable"}`.

---

## Step 0 — Set base URL

```bash
BASE_URL=http://localhost
```

---

## Step 1 — Confirm replica set is healthy

```bash
docker exec mealmate-mongo1-1 mongosh --quiet --eval "rs.status().members.map(m => m.stateStr)"
```

**Expected:** one `PRIMARY`, two `SECONDARY`:

```json
[ "PRIMARY", "SECONDARY", "SECONDARY" ]
```

---

## Step 2 — Verify writes work normally

```bash
curl -s -X POST "$BASE_URL/api/restaurants" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Restaurant", "address": "Kyiv", "cuisine": "Ukrainian", "rating": 4.0}'
```

**Expected:** HTTP 201, restaurant object with `"id"`.

---

## Step 3 — Stop the primary node

```bash
docker stop mealmate-mongo1-1
```

Wait ~10–15 seconds for re-election:

```bash
sleep 12
```

---

## Step 4 — Verify a new primary is elected

```bash
docker exec mealmate-mongo2-1 mongosh --quiet --eval "rs.status().members.map(m => m.stateStr)"
```

**Expected:** one `PRIMARY` among the remaining two nodes:

```json
[ "(not reachable/healthy)", "PRIMARY", "SECONDARY" ]
```

---

## Step 5 — Reads still work after primary loss

```bash
curl -s "$BASE_URL/api/restaurants" | jq '{total: .total}'
```

**Expected:** HTTP 200, data intact. The service reads from the new primary (or a secondary) without manual intervention.

---

## Step 6 — Stop a second node (quorum lost)

Only `mongo3` remains — it was a secondary and cannot elect itself as primary without quorum.

```bash
docker stop mealmate-mongo2-1
sleep 5
```

---

## Step 7 — Writes are rejected (read-only mode)

```bash
curl -s -w "\nHTTP %{http_code}" -X POST "$BASE_URL/api/restaurants" \
  -H "Content-Type: application/json" \
  -d '{"name": "Another Restaurant", "address": "Kyiv", "cuisine": "French", "rating": 4.5}'
```

**Expected:** HTTP 503

```json
{"detail": "Database write unavailable"}
```

MongoDB raises `NotWritablePrimary`; the repository catches `PyMongoError` and raises `WriteUnavailableError`, which the FastAPI exception handler maps to 503. The service does not crash.

---

## Step 8 — Reads still succeed (secondaryPreferred)

```bash
curl -s "$BASE_URL/api/restaurants" | jq '{total: .total}'
```

**Expected:** HTTP 200, same data as before. `readPreference=secondaryPreferred` routes the read to the surviving `mongo3` secondary even though no primary is available.

---

## Restore the cluster

```bash
docker start mealmate-mongo1-1 mealmate-mongo2-1
sleep 15
docker exec mealmate-mongo1-1 mongosh --quiet --eval "rs.status().members.map(m => m.stateStr)"
# Expected: [ "PRIMARY", "SECONDARY", "SECONDARY" ]  (or in any order)
```

---

## Acceptance Checklist

- [ ] Step 1: one PRIMARY, two SECONDARY
- [ ] Step 2: write returns 201
- [ ] Step 4: new primary elected automatically after `mongo1` is stopped
- [ ] Step 5: reads succeed immediately after re-election
- [ ] Step 7: write returns 503 `{"detail": "Database write unavailable"}` — service does not crash
- [ ] Step 8: reads succeed on the surviving secondary