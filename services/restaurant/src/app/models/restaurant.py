from pydantic import BaseModel, Field


class RestaurantCreate(BaseModel):
    name: str
    address: str
    cuisine: str
    rating: float = Field(ge=0, le=5)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Burger Palace",
                    "address": "10 Main St, Kyiv",
                    "cuisine": "American",
                    "rating": 4.5,
                }
            ]
        }
    }


class RestaurantResponse(BaseModel):
    id: str
    name: str
    address: str
    cuisine: str
    rating: float
    is_active: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "64b8f1c2e4b0a1234567890a",
                    "name": "Burger Palace",
                    "address": "10 Main St, Kyiv",
                    "cuisine": "American",
                    "rating": 4.5,
                    "is_active": True,
                }
            ]
        }
    }


class RestaurantListResponse(BaseModel):
    items: list[RestaurantResponse]
    total: int
