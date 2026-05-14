from dataclasses import dataclass


@dataclass
class Restaurant:
    id: str
    name: str
    address: str
    cuisine: str
    rating: float
    is_active: bool


@dataclass
class MenuItem:
    id: str
    restaurant_id: str
    name: str
    description: str
    price: float
    is_available: bool
