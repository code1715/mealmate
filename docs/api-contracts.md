# API Contracts

Single source of truth for all cross-service HTTP and event interfaces.
All services are reachable through the Nginx gateway on port 80.

**Auth:** All protected endpoints require `Authorization: Bearer <token>`.  
**Roles:** `customer` | `courier` | `restaurant`  
**Dates:** ISO 8601 UTC — `2025-01-15T14:32:00Z`

---

## Auth Service (`/api/auth`)

### POST /api/auth/register

**Auth required:** No

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secret123",
  "role": "customer"
}
```

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "role": "customer"
}
```

**Response 409:** `{ "detail": "Email already registered" }`  
**Response 422:** `{ "detail": [...] }` — validation error (invalid email, password < 6 chars)

---

### POST /api/auth/login

**Auth required:** No

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Response 401:** `{ "detail": "Invalid credentials" }`

---

### POST /api/auth/logout

**Auth required:** Yes

**Request:** no body  
**Header:** `Authorization: Bearer <token>`

**Response 200:** `{ "message": "Logged out" }`

---

### GET /api/auth/validate

**Auth required:** Yes  
**Used by:** all other services to verify incoming tokens

**Header:** `Authorization: Bearer <token>`

**Response 200:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "customer"
}
```

**Response 401:** `{ "detail": "Missing token" }` | `{ "detail": "Invalid or expired token" }` | `{ "detail": "Token has been invalidated" }`

---

## Order Service (`/api/orders`)

### POST /api/orders

**Auth required:** Yes — role `customer`

**Request:**
```json
{
  "restaurant_id": "550e8400-e29b-41d4-a716-446655440001",
  "items": [
    { "menu_item_id": "item-uuid", "quantity": 2 }
  ]
}
```

**Response 201:**
```json
{
  "id": "order-uuid",
  "customer_id": "user-uuid",
  "restaurant_id": "restaurant-uuid",
  "items": [
    { "menu_item_id": "item-uuid", "name": "Margherita", "quantity": 2, "unit_price": 9.99 }
  ],
  "status": "PLACED",
  "total_price": 19.98,
  "created_at": "2025-01-15T14:32:00Z"
}
```

**Response 401:** `{ "detail": "Unauthorized" }`  
**Response 422:** `{ "detail": [...] }` — empty items, unknown restaurant

---

### GET /api/orders/:id

**Auth required:** Yes — owner customer, assigned courier, or restaurant

**Response 200:**
```json
{
  "id": "order-uuid",
  "customer_id": "user-uuid",
  "restaurant_id": "restaurant-uuid",
  "courier_id": "courier-uuid",
  "items": [
    { "menu_item_id": "item-uuid", "name": "Margherita", "quantity": 2, "unit_price": 9.99 }
  ],
  "status": "PREPARING",
  "total_price": 19.98,
  "created_at": "2025-01-15T14:32:00Z",
  "updated_at": "2025-01-15T14:35:00Z"
}
```

**Response 403:** `{ "detail": "Forbidden" }`  
**Response 404:** `{ "detail": "Order not found" }`

---

### PATCH /api/orders/:id/status

**Auth required:** Yes — role `restaurant` or `courier`

**Request:**
```json
{
  "status": "PREPARING"
}
```

**Valid status transitions:**

| Actor | From | To |
|---|---|---|
| restaurant | `PLACED` | `PREPARING` |
| restaurant | `PREPARING` | `READY` |
| courier | `READY` | `PICKED_UP` |
| courier | `PICKED_UP` | `DELIVERED` |
| restaurant / customer | any | `CANCELLED` |

**Response 200:**
```json
{
  "id": "order-uuid",
  "status": "PREPARING",
  "updated_at": "2025-01-15T14:35:00Z"
}
```

**Response 400:** `{ "detail": "Invalid status transition" }`  
**Response 403:** `{ "detail": "Forbidden" }`  
**Response 404:** `{ "detail": "Order not found" }`

---

### GET /api/orders?customer_id=

**Auth required:** Yes — role `customer` (own orders only) or `restaurant`

**Query params:** `customer_id` (uuid)

**Response 200:**
```json
[
  {
    "id": "order-uuid",
    "restaurant_id": "restaurant-uuid",
    "status": "DELIVERED",
    "total_price": 19.98,
    "created_at": "2025-01-15T14:32:00Z"
  }
]
```

**Response 403:** `{ "detail": "Forbidden" }`

---

## Restaurant Service (`/api/restaurants`)

### GET /api/restaurants

**Auth required:** No

**Query params (all optional):** `cuisine` (string), `is_open` (bool)

**Response 200:**
```json
[
  {
    "id": "restaurant-uuid",
    "name": "Pizza Roma",
    "address": "vul. Khreshchatyk 1, Kyiv",
    "cuisine": "Italian",
    "is_open": true
  }
]
```

---

### GET /api/restaurants/:id/menu

**Auth required:** No

**Response 200:**
```json
{
  "restaurant_id": "restaurant-uuid",
  "items": [
    {
      "id": "item-uuid",
      "name": "Margherita",
      "description": "Tomato, mozzarella, basil",
      "price": 9.99,
      "category": "Pizza",
      "is_available": true
    }
  ]
}
```

**Response 404:** `{ "detail": "Restaurant not found" }`

---

### POST /api/restaurants/:id/menu

**Auth required:** Yes — role `restaurant` (own restaurant only)

**Request:**
```json
{
  "name": "Pepperoni",
  "description": "Tomato, mozzarella, pepperoni",
  "price": 11.99,
  "category": "Pizza",
  "is_available": true
}
```

**Response 201:**
```json
{
  "id": "item-uuid",
  "name": "Pepperoni",
  "description": "Tomato, mozzarella, pepperoni",
  "price": 11.99,
  "category": "Pizza",
  "is_available": true
}
```

**Response 403:** `{ "detail": "Forbidden" }`  
**Response 404:** `{ "detail": "Restaurant not found" }`

---

## Routing Service (`/api/routing`)

### POST /api/routing/match

**Auth required:** Yes — internal service call (role `restaurant` or system)  
**Purpose:** Find the nearest available courier to a restaurant and assign them to the order.

**Request:**
```json
{
  "order_id": "order-uuid",
  "restaurant_id": "restaurant-uuid"
}
```

**Response 200:**
```json
{
  "order_id": "order-uuid",
  "courier_id": "courier-uuid",
  "estimated_minutes": 12
}
```

**Response 404:** `{ "detail": "No couriers available" }`

---

### PATCH /api/routing/couriers/:id/status

**Auth required:** Yes — role `courier` (own status only)

**Request:**
```json
{
  "status": "AVAILABLE"
}
```

**Valid values:** `AVAILABLE` | `BUSY` | `OFFLINE`

**Response 200:**
```json
{
  "courier_id": "courier-uuid",
  "status": "AVAILABLE"
}
```

**Response 403:** `{ "detail": "Forbidden" }`  
**Response 404:** `{ "detail": "Courier not found" }`

---

## Notification Service — Kafka Events

The Notification Service has no HTTP endpoints. It consumes events from Kafka and dispatches push notifications to the relevant user.

### Topic: `order-status-changed`

Published by: Order Service  
Consumed by: Notification Service

**Message:**
```json
{
  "order_id": "order-uuid",
  "customer_id": "user-uuid",
  "restaurant_id": "restaurant-uuid",
  "courier_id": "courier-uuid",
  "previous_status": "PLACED",
  "new_status": "PREPARING",
  "timestamp": "2025-01-15T14:35:00Z"
}
```

| Field | Type | Notes |
|---|---|---|
| `order_id` | uuid string | partition key |
| `customer_id` | uuid string | recipient of the notification |
| `restaurant_id` | uuid string | present in all events |
| `courier_id` | uuid string \| null | null until a courier is assigned |
| `previous_status` | string | see status transitions table above |
| `new_status` | string | see status transitions table above |
| `timestamp` | ISO 8601 UTC | when the status change occurred |
