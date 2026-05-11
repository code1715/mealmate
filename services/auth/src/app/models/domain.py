import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    customer = "customer"
    courier = "courier"
    restaurant = "restaurant"


@dataclass
class User:
    id: uuid.UUID
    email: str
    role: UserRole
    hashed_password: str
    created_at: datetime
