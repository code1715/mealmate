import uuid
from enum import Enum

from pydantic import BaseModel


class CourierStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Courier(BaseModel):
    id: uuid.UUID
    name: str
    status: CourierStatus
    lat: float
    lng: float


class Zone(BaseModel):
    id: uuid.UUID
    name: str


class Restaurant(BaseModel):
    id: uuid.UUID
    name: str
    zone_id: uuid.UUID
    lat: float
    lng: float


class MatchRequest(BaseModel):
    order_id: uuid.UUID
    restaurant_id: uuid.UUID


class MatchResult(BaseModel):
    order_id: uuid.UUID
    courier_id: uuid.UUID
    estimated_minutes: int


class CourierStatusUpdate(BaseModel):
    status: CourierStatus
