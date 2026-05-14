from pydantic import BaseModel, Field


class MenuItemCreate(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Cheeseburger",
                    "description": "Classic beef patty with cheese",
                    "price": 9.99,
                }
            ]
        }
    }


class MenuItemAvailabilityUpdate(BaseModel):
    is_available: bool


class MenuItemResponse(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price: float
    is_available: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "64b8f1c2e4b0a1234567890b",
                    "restaurant_id": "64b8f1c2e4b0a1234567890a",
                    "name": "Cheeseburger",
                    "description": "Classic beef patty with cheese",
                    "price": 9.99,
                    "is_available": True,
                }
            ]
        }
    }
