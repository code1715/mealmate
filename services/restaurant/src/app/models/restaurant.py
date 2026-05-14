from pydantic import BaseModel


class RestaurantResponse(BaseModel):
    id: str
    name: str
    address: str
    cuisine: str
    rating: float
    is_active: bool


class RestaurantListResponse(BaseModel):
    items: list[RestaurantResponse]
    total: int
