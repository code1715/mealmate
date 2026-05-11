import enum
import uuid
from datetime import datetime

from pydantic import BaseModel


class UserRole(str, enum.Enum):
    customer = "customer"
    courier = "courier"
    restaurant = "restaurant"


class User(BaseModel):
    """Domain model representing an authenticated user."""

    id: uuid.UUID
    email: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}
