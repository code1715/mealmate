# API Gateway Routing Verification

Covers issue #61. Verifies that Nginx correctly routes all requests to the appropriate upstream service, that load balancing across Order Service instances works, that unknown paths return 404, that headers pass through intact, and that individual service ports are not reachable from outside Docker.

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

All external traffic enters on port 80 (Nginx). Individual service ports (`8001`–`8005`) are **not** published in `docker-compose.yml` — services are only reachable inside the Docker network.

Nginx routing table:

| Path prefix | Upstream | Notes |
|---|---|---|
| `/api/auth/` | `auth:8000` | Rate-limited login at `/api/auth/login` |
| `/api/orders` | `order_backend` | Round-robin: `order-service-1:8000`, `order-service-2:8000` |
| `/api/restaurants` | `restaurant:8000` | |
| `/api/routing` | `routing:8000` | |
| `/health/auth` | `auth:8000/health` | Per-service health probe |
| `/health/order` | `order_backend/health` | |
| `/health/restaurant` | `restaurant:8000/health` | |
| `/health/routing` | `routing:8000/health` | |
| `/health` | gateway itself | Returns `{"status":"ok","service":"api-gateway"}` |
| all other paths | — | Returns 404 `{"detail":"Not found"}` |

Shared headers on all proxied requests:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header Authorization     $http_authorization;
```

---

## Step 0 — Set base URL

```bash
BASE_URL=http://localhost
```

---

## Step 1 — Gateway self-health

```bash
curl -s "$BASE_URL/health" | jq .
```

**Expected:** HTTP 200

```json
{"status": "ok", "service": "api-gateway"}
```

---

## Step 2 — Route all four services through the gateway

```bash
curl -s "$BASE_URL/health/auth"         | jq .status
curl -s "$BASE_URL/health/order"        | jq .status
curl -s "$BASE_URL/health/restaurant"   | jq .status
curl -s "$BASE_URL/health/routing"      | jq .status
```

**Expected:** all four return `"ok"`.

---

## Step 3 — Auth API route

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "gateway-test@test.com", "password": "pass123", "role": "customer"}'
```

**Expected:** `201` — request reached the auth service (not Nginx catch-all).

---

## Step 4 — Restaurant API route

```bash
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/restaurants"
```

**Expected:** `200` — restaurant list returned from restaurant service.

---

## Step 5 — Load balancing: both Order Service instances receive traffic

Send 10 requests and collect the `X-Instance-ID` header from each:

```bash
for i in $(seq 1 10); do
  curl -si "$BASE_URL/health/order" | grep "X-Instance-ID"
done
```

**Expected:** both `X-Instance-ID: order-service-1` and `X-Instance-ID: order-service-2` appear across the 10 responses, confirming round-robin distribution.

Alternatively, verify via Docker logs:

```bash
docker compose logs order-service-1 --tail=20 | grep "GET /health"
docker compose logs order-service-2 --tail=20 | grep "GET /health"
```

Both services should show hits.

---

## Step 6 — Unknown path returns 404 from Nginx (not a connection error)

```bash
curl -s -w "\nHTTP %{http_code}" "$BASE_URL/api/unknown/"
```

**Expected:** HTTP 404 with a JSON body from Nginx (not a timeout or TCP error):

```json
{"detail":"Not found"}
```

---

## Step 7 — Authorization header passes through to upstream

Register and login to get a token, then verify the order service receives and validates it (the order service calls auth to validate):

```bash
curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "gateway-test@test.com", "password": "pass123"}' | jq -r '.access_token' > /tmp/gw_token.txt

TOKEN=$(cat /tmp/gw_token.txt)
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/orders" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected:** `200` — the `Authorization` header was forwarded by Nginx to the order service, which validated it via the auth service. A `401` would indicate the header was stripped.

---

## Step 8 — Individual service ports are not reachable from the host

```bash
curl -s --connect-timeout 2 http://localhost:8001/health; echo "exit: $?"
curl -s --connect-timeout 2 http://localhost:8002/health; echo "exit: $?"
curl -s --connect-timeout 2 http://localhost:8003/health; echo "exit: $?"
curl -s --connect-timeout 2 http://localhost:8004/health; echo "exit: $?"
curl -s --connect-timeout 2 http://localhost:8005/health; echo "exit: $?"
```

**Expected:** all five connections fail (non-zero exit code, no response body). The ports are not published in `docker-compose.yml`, so the host cannot reach them directly.

---

## Acceptance Checklist

- [ ] Step 1: gateway `/health` returns `{"status":"ok","service":"api-gateway"}`
- [ ] Step 2: all four per-service health probes return `"ok"` through the gateway
- [ ] Step 3: `/api/auth/register` reaches auth service (201)
- [ ] Step 4: `/api/restaurants` reaches restaurant service (200)
- [ ] Step 5: both `order-service-1` and `order-service-2` appear in `X-Instance-ID` across 10 requests
- [ ] Step 6: unknown path returns 404 `{"detail":"Not found"}` from Nginx (not a connection error)
- [ ] Step 7: `Authorization` header passes through — `/api/orders` returns 200 with a valid token
- [ ] Step 8: ports 8001–8005 are unreachable from the host (connection refused or timeout)