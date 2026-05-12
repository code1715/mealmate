import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.domain import OrderStatus

# --- Request schemas ---


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    name: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)


class OrderCreate(BaseModel):
    restaurant_id: uuid.UUID
    items: list[OrderItemCreate] = Field(min_length=1)


class StatusUpdate(BaseModel):
    status: OrderStatus


# --- Response schemas ---


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    unit_price: float


class OrderResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    restaurant_id: uuid.UUID
    courier_id: uuid.UUID | None = None
    status: OrderStatus
    total_price: float
    items: list[OrderItemResponse]
    created_at: datetime | None = None
    updated_at: datetime | None = None
