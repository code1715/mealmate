from pydantic import BaseModel


class OrderStatusEvent(BaseModel):
    order_id: str
    customer_id: str
    restaurant_id: str
    courier_id: str | None
    previous_status: str
    new_status: str
    timestamp: str
