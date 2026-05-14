from pydantic import BaseModel, Field


class MenuItemCreate(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)


class MenuItemResponse(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price: float
    is_available: bool
