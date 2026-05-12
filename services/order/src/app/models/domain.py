import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    PLACED = "PLACED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# --- Valid state transitions ---
# See: docs/api-contracts.md — PATCH /api/orders/:id/status

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PLACED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {OrderStatus.PICKED_UP, OrderStatus.CANCELLED},
    OrderStatus.PICKED_UP: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


@dataclass
class OrderItem:
    id: uuid.UUID
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    unit_price: float


@dataclass
class Order:
    id: uuid.UUID
    customer_id: uuid.UUID
    restaurant_id: uuid.UUID
    status: OrderStatus
    total_price: float
    items: list[OrderItem] = field(default_factory=list)
    courier_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
