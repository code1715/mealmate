# Food Delivery Platform — Use Cases / Product Backlog

This document defines the functional requirements of the system in a structured, testable format.

---

## Table of Contents

| ID    | Title                                              | Actor      | Service              |
|-------|----------------------------------------------------|------------|----------------------|
| UC-01 | Customer registers an account                      | Customer   | Auth Service         |
| UC-02 | User logs in and receives JWT token                | Any        | Auth Service         |
| UC-03 | User logs out and token is invalidated             | Any        | Auth Service         |
| UC-04 | Customer browses list of restaurants               | Customer   | Restaurant Service   |
| UC-05 | Customer views menu of a specific restaurant       | Customer   | Restaurant Service   |
| UC-06 | Customer places an order                           | Customer   | Order Service        |
| UC-07 | Customer views order status                        | Customer   | Order Service        |
| UC-08 | Restaurant confirms an order                       | Restaurant | Order Service        |
| UC-09 | Restaurant rejects an order                        | Restaurant | Order Service        |
| UC-10 | Restaurant adds a menu item                        | Restaurant | Restaurant Service   |
| UC-11 | System assigns nearest available courier           | System     | Routing Service      |
| UC-12 | Courier marks delivery as picked up                | Courier    | Order Service        |
| UC-13 | Courier marks delivery as completed                | Courier    | Order Service        |
| UC-14 | System publishes status change event to Kafka      | System     | Order Service        |
| UC-15 | Notification worker consumes and logs Kafka event  | System     | Notification Service |

---

## UC-01: Customer registers an account

**Actor:** Customer
**Precondition:** The user does not have an existing account. The Auth Service and PostgreSQL are running.
**Endpoint:** `POST /api/auth/register`

**Flow:**
1. User sends `POST /api/auth/register` with body `{ name, email, password, role: "customer" }`
2. System validates input: email is non-empty and matches email format, password is at least 8 characters, role is one of `customer | restaurant | courier`
3. System checks PostgreSQL for an existing user with the same email
4. System hashes the password using bcrypt and stores the user record in PostgreSQL
5. System returns `201 Created` with `{ user_id, email, role }`

**Postcondition:** A user record exists in PostgreSQL with a hashed password. The user can now log in.

**Exceptions:**
- Email already registered → `409 Conflict` with message `"Email already in use"`
- Missing or invalid fields → `422 Unprocessable Entity` with field-level error details
- Database unavailable → `503 Service Unavailable`

---

## UC-02: User logs in and receives JWT token

**Actor:** Customer, Restaurant, or Courier
**Precondition:** The user has a registered account. Redis and PostgreSQL are running.
**Endpoint:** `POST /api/auth/login`

**Flow:**
1. User sends `POST /api/auth/login` with body `{ email, password }`
2. System looks up the user by email in PostgreSQL
3. System verifies the submitted password against the stored bcrypt hash
4. System generates a signed JWT containing `{ user_id, role, exp }`
5. System stores the token in Redis with key `session:{user_id}` and a TTL of 24 hours
6. System returns `200 OK` with `{ token, role, user_id }`

**Postcondition:** A valid JWT exists in Redis. The user can make authenticated requests to all services by including the token in the `Authorization: Bearer <token>` header.

**Exceptions:**
- Email not found → `401 Unauthorized` with message `"Invalid credentials"` (do not reveal which field is wrong)
- Password mismatch → `401 Unauthorized` with message `"Invalid credentials"`
- Redis unavailable → `503 Service Unavailable` (token cannot be stored; do not issue a token)

---

## UC-03: User logs out and token is invalidated

**Actor:** Customer, Restaurant, or Courier
**Precondition:** The user is logged in and holds a valid JWT. Redis is running.
**Endpoint:** `POST /api/auth/logout`

**Flow:**
1. User sends `POST /api/auth/logout` with header `Authorization: Bearer <token>`
2. Auth Service validates the token signature and extracts `user_id`
3. System deletes the key `session:{user_id}` from Redis
4. System returns `200 OK` with message `"Logged out successfully"`

**Postcondition:** The token no longer exists in Redis. Any subsequent request using the same token is rejected with `401 Unauthorized`, even if the token signature is still mathematically valid and not yet expired.

**Exceptions:**
- Token missing or malformed → `401 Unauthorized`
- Token already invalidated (key not in Redis) → `200 OK` (idempotent — logging out twice is not an error)
- Redis unavailable → `503 Service Unavailable`

---

## UC-04: Customer browses list of restaurants

**Actor:** Customer
**Precondition:** The user is authenticated. At least one restaurant exists in MongoDB. Restaurant Service is running.
**Endpoint:** `GET /api/restaurants`

**Flow:**
1. User sends `GET /api/restaurants` with header `Authorization: Bearer <token>`
2. API Gateway forwards the request to Restaurant Service
3. Restaurant Service validates the token by calling Auth Service `GET /api/auth/validate`
4. Restaurant Service queries MongoDB for all restaurant documents
5. System returns `200 OK` with an array of `{ restaurant_id, name, address, cuisine_type, is_open }`

**Postcondition:** The customer sees a list of available restaurants and can choose one to browse.

**Exceptions:**
- Token invalid or missing → `401 Unauthorized`
- MongoDB primary unavailable but replica readable → `200 OK` served from secondary (read-only fallback)
- MongoDB fully unavailable → `503 Service Unavailable`

---

## UC-05: Customer views menu of a specific restaurant

**Actor:** Customer
**Precondition:** The user is authenticated. The restaurant with the given ID exists in MongoDB.
**Endpoint:** `GET /api/restaurants/{restaurant_id}/menu`

**Flow:**
1. User sends `GET /api/restaurants/{restaurant_id}/menu` with `Authorization: Bearer <token>`
2. Restaurant Service validates the token via Auth Service
3. System queries MongoDB for all menu items with matching `restaurant_id`
4. System returns `200 OK` with an array of `{ item_id, name, description, price, is_available }`

**Postcondition:** The customer sees the full menu and can select items to add to an order.

**Exceptions:**
- Token invalid or missing → `401 Unauthorized`
- Restaurant ID not found → `404 Not Found`
- MongoDB quorum lost → writes rejected, but `GET` still returns `200 OK` from secondary replica

---

## UC-06: Customer places an order

**Actor:** Customer
**Precondition:** The user is authenticated with role `customer`. The restaurant and all requested menu items exist. Order Service and PostgreSQL are running.
**Endpoint:** `POST /api/orders`

**Flow:**
1. User sends `POST /api/orders` with header `Authorization: Bearer <token>` and body:
   ```json
   {
     "restaurant_id": "abc-123",
     "items": [
       { "item_id": "item-1", "quantity": 2 },
       { "item_id": "item-2", "quantity": 1 }
     ]
   }
   ```
2. Order Service validates the token and confirms role is `customer`
3. Order Service calls Restaurant Service to verify all `item_id` values exist and are available
4. System calculates total price from item data
5. System creates an order record in PostgreSQL with status `PENDING`
6. System returns `201 Created` with `{ order_id, status: "PENDING", total_price, created_at }`

**Postcondition:** An order record exists in PostgreSQL. The restaurant can now see and act on the order.

**Exceptions:**
- Token invalid or role is not `customer` → `401 Unauthorized` or `403 Forbidden`
- `restaurant_id` does not exist → `404 Not Found`
- One or more `item_id` values do not exist or are unavailable → `422 Unprocessable Entity`
- Order body is empty or malformed → `422 Unprocessable Entity`

---

## UC-07: Customer views order status

**Actor:** Customer
**Precondition:** The user is authenticated and the order belongs to them.
**Endpoint:** `GET /api/orders/{order_id}`

**Flow:**
1. User sends `GET /api/orders/{order_id}` with `Authorization: Bearer <token>`
2. Order Service validates the token and extracts `user_id`
3. System queries PostgreSQL for the order by `order_id`
4. System verifies that `order.customer_id` matches the authenticated `user_id`
5. System returns `200 OK` with `{ order_id, status, items, total_price, created_at, updated_at }`

**Postcondition:** The customer sees the current status of their order.

**Exceptions:**
- Token invalid → `401 Unauthorized`
- Order not found → `404 Not Found`
- Order belongs to a different customer → `403 Forbidden` (do not reveal the order exists)

---

## UC-08: Restaurant confirms an order

**Actor:** Restaurant
**Precondition:** The user is authenticated with role `restaurant`. An order with status `PENDING` exists for this restaurant.
**Endpoint:** `PATCH /api/orders/{order_id}/status`

**Flow:**
1. Restaurant sends `PATCH /api/orders/{order_id}/status` with body `{ "status": "CONFIRMED" }` and `Authorization: Bearer <token>`
2. Order Service validates the token and confirms role is `restaurant`
3. System fetches the order and verifies `order.restaurant_id` matches the authenticated restaurant
4. System verifies current status is `PENDING` (only valid transition to `CONFIRMED`)
5. System updates the order status to `CONFIRMED` in PostgreSQL
6. System publishes event `order_status_changed` to Kafka (triggers UC-14)
7. System returns `200 OK` with updated order

**Postcondition:** Order status is `CONFIRMED`. Kafka event is published. Routing Service may be triggered to assign a courier (UC-11).

**Exceptions:**
- Token invalid or role is not `restaurant` → `401 Unauthorized` or `403 Forbidden`
- Order belongs to a different restaurant → `403 Forbidden`
- Order is not in `PENDING` status → `409 Conflict` with message `"Invalid status transition"`

---

## UC-09: Restaurant rejects an order

**Actor:** Restaurant
**Precondition:** The user is authenticated with role `restaurant`. An order with status `PENDING` exists for this restaurant.
**Endpoint:** `PATCH /api/orders/{order_id}/status`

**Flow:**
1. Restaurant sends `PATCH /api/orders/{order_id}/status` with body `{ "status": "REJECTED", "reason": "Out of ingredients" }` and `Authorization: Bearer <token>`
2. Order Service validates the token and confirms role is `restaurant`
3. System verifies `order.restaurant_id` matches the authenticated restaurant
4. System verifies current status is `PENDING`
5. System updates order status to `REJECTED` with the provided reason
6. System publishes `order_status_changed` event to Kafka
7. System returns `200 OK` with updated order

**Postcondition:** Order status is `REJECTED`. The customer will see the rejection when they next query UC-07. Kafka event is published.

**Exceptions:**
- Token invalid or role is not `restaurant` → `401 Unauthorized` or `403 Forbidden`
- Order is not in `PENDING` status → `409 Conflict`
- Rejection reason missing → `422 Unprocessable Entity`

---

## UC-10: Restaurant adds a menu item

**Actor:** Restaurant
**Precondition:** The user is authenticated with role `restaurant`. Restaurant Service and MongoDB are running and accepting writes.
**Endpoint:** `POST /api/restaurants/{restaurant_id}/menu`

**Flow:**
1. Restaurant sends `POST /api/restaurants/{restaurant_id}/menu` with `Authorization: Bearer <token>` and body:
   ```json
   {
     "name": "Margherita Pizza",
     "description": "Tomato, mozzarella, basil",
     "price": 12.50,
     "is_available": true
   }
   ```
2. Restaurant Service validates the token and confirms role is `restaurant`
3. System verifies the authenticated restaurant owns `restaurant_id`
4. System inserts the menu item document into MongoDB
5. System returns `201 Created` with `{ item_id, name, price, is_available }`

**Postcondition:** The new item is visible to customers browsing the menu (UC-05).

**Exceptions:**
- Token invalid or role is not `restaurant` → `401 Unauthorized` or `403 Forbidden`
- `restaurant_id` does not belong to the authenticated user → `403 Forbidden`
- Required fields missing or price is negative → `422 Unprocessable Entity`
- MongoDB in read-only mode (quorum lost) → `503 Service Unavailable` with message `"Database is currently read-only"`

---

## UC-11: System assigns nearest available courier

**Actor:** System (triggered internally after UC-08)
**Precondition:** An order has been confirmed (status = `CONFIRMED`). At least one courier with status `AVAILABLE` exists in Neo4j. Routing Service is running.
**Endpoint:** `POST /api/routing/match` (called internally by Order Service)

**Flow:**
1. Order Service calls `POST /api/routing/match` with body `{ "restaurant_id": "abc-123", "order_id": "ord-456" }`
2. Routing Service queries Neo4j to find all `Courier` nodes with status `AVAILABLE`
3. System traverses the graph to find the courier with the shortest path to the restaurant zone
4. System updates the selected courier node status to `BUSY` in Neo4j
5. System returns `200 OK` with `{ courier_id, estimated_pickup_minutes }`
6. Order Service updates the order record with `courier_id` and transitions status to `PREPARING`

**Postcondition:** A courier is assigned to the order. The courier can see their assignment.

**Exceptions:**
- No available couriers → `503 Service Unavailable` with message `"No couriers available"`. Order remains `CONFIRMED` and system retries after a delay.
- `restaurant_id` not found in Neo4j → `404 Not Found`
- Neo4j unavailable → `503 Service Unavailable`

---

## UC-12: Courier marks delivery as picked up

**Actor:** Courier
**Precondition:** The user is authenticated with role `courier`. The order status is `READY_FOR_PICKUP` and the order is assigned to this courier.
**Endpoint:** `PATCH /api/orders/{order_id}/status`

**Flow:**
1. Courier sends `PATCH /api/orders/{order_id}/status` with body `{ "status": "IN_DELIVERY" }` and `Authorization: Bearer <token>`
2. Order Service validates the token and confirms role is `courier`
3. System verifies `order.courier_id` matches the authenticated courier
4. System verifies current status is `READY_FOR_PICKUP`
5. System updates order status to `IN_DELIVERY`
6. System publishes `order_status_changed` event to Kafka
7. System returns `200 OK` with updated order

**Postcondition:** Order status is `IN_DELIVERY`. The customer sees the order is on its way.

**Exceptions:**
- Token invalid or role is not `courier` → `401 Unauthorized` or `403 Forbidden`
- Order is not assigned to this courier → `403 Forbidden`
- Status is not `READY_FOR_PICKUP` → `409 Conflict` with message `"Invalid status transition"`

---

## UC-13: Courier marks delivery as completed

**Actor:** Courier
**Precondition:** The user is authenticated with role `courier`. Order status is `IN_DELIVERY` and assigned to this courier.
**Endpoint:** `PATCH /api/orders/{order_id}/status`

**Flow:**
1. Courier sends `PATCH /api/orders/{order_id}/status` with body `{ "status": "DELIVERED" }` and `Authorization: Bearer <token>`
2. Order Service validates the token and confirms role is `courier`
3. System verifies `order.courier_id` matches the authenticated courier
4. System verifies current status is `IN_DELIVERY`
5. System updates order status to `DELIVERED`
6. System publishes `order_status_changed` event to Kafka
7. Routing Service is notified (internally) to set courier status back to `AVAILABLE` in Neo4j
8. System returns `200 OK` with updated order

**Postcondition:** Order is closed. Courier is available for new assignments. Customer sees final status `DELIVERED`.

**Exceptions:**
- Token invalid or role is not `courier` → `401 Unauthorized` or `403 Forbidden`
- Order not assigned to this courier → `403 Forbidden`
- Status is not `IN_DELIVERY` → `409 Conflict`

---

## UC-14: System publishes status change event to Kafka

**Actor:** System (triggered by UC-08, UC-09, UC-12, UC-13, and any other status transition)
**Precondition:** An order status has changed. Kafka broker is running and the topic `order-status-changed` exists.
**Endpoint:** Internal — no external API call. Triggered within the Order Service status update handler.

**Flow:**
1. Order Service completes a status update in PostgreSQL
2. Within the same request handler, Order Service constructs an event payload:
   ```json
   {
     "event_type": "order_status_changed",
     "order_id": "ord-456",
     "customer_id": "usr-123",
     "restaurant_id": "rst-789",
     "old_status": "PENDING",
     "new_status": "CONFIRMED",
     "timestamp": "2025-05-11T14:32:00Z"
   }
   ```
3. System publishes the event to Kafka topic `order-status-changed` using `confluent-kafka` Python producer
4. Producer calls `.flush()` to confirm delivery before returning the HTTP response

**Postcondition:** The event is durably written to Kafka. It will be delivered to the Notification Service consumer regardless of whether the consumer is currently running.

**Exceptions:**
- Kafka broker unavailable → log the error, return `500 Internal Server Error`. The status change in PostgreSQL is NOT rolled back — the order state is updated, but the event is lost.
- Event serialisation failure → log the raw payload and raise an internal alert (log to stderr)

---

## UC-15: Notification worker consumes and logs Kafka event

**Actor:** System (Notification Service, running as a background worker)
**Precondition:** Kafka broker is running. Topic `order-status-changed` exists. At least one message is available in the topic.
**Endpoint:** Internal — no HTTP endpoint. The worker polls Kafka in a continuous loop.

**Flow:**
1. Notification Service starts and subscribes to `order-status-changed` with consumer group `notification-group`
2. Worker polls Kafka for new messages with a timeout of 1 second per poll cycle
3. On receiving a message, worker deserialises the JSON payload
4. Worker logs the event to stdout:
   ```
   [NOTIFICATION] Order ord-456 status changed: PENDING → CONFIRMED
                  Customer: usr-123 | Restaurant: rst-789 | At: 2025-05-11T14:32:00Z
   ```
5. Worker commits the offset to Kafka (marking the message as processed)
6. Worker returns to polling

**Postcondition:** The event is logged. Kafka offset is committed, so the message will not be redelivered to this consumer group.

**Exceptions:**
- Malformed or missing fields in the payload → log a warning with the raw message content, skip offset commit, and continue polling (do not crash the worker)
- Kafka broker temporarily unavailable → worker retries connection with exponential backoff (max 30 seconds between retries), logs each retry attempt
- Worker crashed while processing → because offset was not committed, the message will be redelivered on restart (at-least-once delivery guarantee)

---

## Order Status Transition Diagram

```
PENDING
  ├── CONFIRMED  (by Restaurant — UC-08)  →  triggers UC-11 (courier assignment)
  └── REJECTED   (by Restaurant — UC-09)  →  terminal state

CONFIRMED
  └── PREPARING  (by System after courier assigned — UC-11)

PREPARING
  └── READY_FOR_PICKUP  (by Restaurant when food is ready)

READY_FOR_PICKUP
  └── IN_DELIVERY  (by Courier — UC-12)

IN_DELIVERY
  └── DELIVERED  (by Courier — UC-13)  →  terminal state
```

Every transition publishes an event to Kafka (UC-14) and is consumed by the Notification Service (UC-15).