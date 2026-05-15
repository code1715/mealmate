# Failover Test — Order Service Instance Loss with Redis Session Persistence

Covers issue #56. Verifies that stopping one Order Service instance does not interrupt service and that JWT tokens remain valid across instances (shared Redis).

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

Two Order Service instances (`order-service-1` and `order-service-2`) sit behind the Nginx upstream `order_backend`. Nginx distributes requests round-robin with automatic failover:

```
nginx upstream order_backend {
    server order-service-1:8000 max_fails=1 fail_timeout=5s;
    server order-service-2:8000 max_fails=1 fail_timeout=5s;
}
```

Both instances share the same Postgres database and the same Redis instance. JWT tokens are validated against Redis (JTI lookup), so a token issued before the failover remains valid on the surviving instance.

Every order service response includes an `X-Instance-ID` header showing which instance handled the request.

---

## Step 0 — Set base URL

```bash
BASE_URL=http://localhost
```

---

## Step 1 — Confirm both instances are running

```bash
docker compose ps | grep order-service
```

**Expected:** two lines, both showing `Up` or `(healthy)`:

```
order-service-1   ...   Up (healthy)
order-service-2   ...   Up (healthy)
```

---

## Step 2 — Register a user and login

```bash
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "failover@test.com", "password": "pass123", "role": "customer"}'

TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "failover@test.com", "password": "pass123"}' \
  | jq -r '.access_token')
echo "TOKEN=$TOKEN"
```

**Expected:** register returns HTTP 201; login returns HTTP 200 with `access_token`. The JWT's JTI is stored in Redis.

---

## Step 3 — Send two requests and note which instance handles each

The `-v` flag prints response headers so you can see `X-Instance-ID`.

```bash
curl -si "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN" | grep -E "HTTP/|X-Instance-ID"

curl -si "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN" | grep -E "HTTP/|X-Instance-ID"
```

**Expected:** both return HTTP 200. After enough requests, both `order-service-1` and `order-service-2` appear in the `X-Instance-ID` header, confirming round-robin distribution.

If you want to force traffic to a specific instance first, repeat the request until you see each instance at least once.

---

## Step 4 — Kill one instance

Stop whichever instance handled step 3 (or stop `order-service-1` to be deterministic):

```bash
docker stop order-service-1
```

Verify it is gone:

```bash
docker compose ps | grep order-service
# order-service-1   ...   Exit
# order-service-2   ...   Up (healthy)
```

---

## Step 5 — Repeat the request immediately

Use the **same token** obtained before the failure:

```bash
curl -si "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN" | grep -E "HTTP/|X-Instance-ID"
```

**Expected:** HTTP 200, `X-Instance-ID: order-service-2`. The surviving instance handles the request without requiring re-login.

Nginx's `proxy_next_upstream` directive retries on error/timeout, so the client sees no failure even if the dead instance is hit first.

---

## Step 6 — Verify session data is intact

```bash
curl -s "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** HTTP 200 with the same orders list as before the failure. No re-login required. Redis (shared between both instances) still holds the JTI, so the surviving instance validates the token successfully.

---

## Step 7 — Bring the stopped instance back up

```bash
docker compose start order-service-1
```

Wait for it to become healthy:

```bash
docker compose ps | grep order-service-1
# order-service-1   ...   Up (healthy)
```

Traffic will resume distributing across both instances.

---

## Acceptance Checklist

- [ ] Step 1: both `order-service-1` and `order-service-2` show as healthy
- [ ] Step 3: requests return 200; `X-Instance-ID` confirms traffic reaches both instances
- [ ] Step 4: `docker stop order-service-1` stops the container cleanly
- [ ] Step 5: next request returns 200 on the surviving instance — no re-login needed
- [ ] Step 6: response body matches pre-failure state
- [ ] Step 7: restarted instance rejoins the pool