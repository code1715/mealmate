import json
import logging
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

from app.config import settings
from app.models.domain import VALID_TRANSITIONS, Order, OrderStatus
from app.models.schemas import OrderCreate

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, order_repo, kafka_producer: Producer):
        self.order_repo = order_repo
        self.kafka_producer = kafka_producer

    async def create_order(self, customer_id: uuid.UUID, payload: OrderCreate) -> Order:
        total = round(sum(item.quantity * item.unit_price for item in payload.items), 2)
        items = [item.model_dump() for item in payload.items]
        for item in items:
            item["menu_item_id"] = str(item["menu_item_id"])

        return await self.order_repo.create(
            customer_id=customer_id,
            restaurant_id=payload.restaurant_id,
            items=items,
            total_price=total,
        )

    async def get_order(self, order_id: uuid.UUID) -> Order | None:
        return await self.order_repo.find_by_id(order_id)

    async def list_orders(self, customer_id: uuid.UUID) -> list[Order]:
        return await self.order_repo.find_by_customer(customer_id)

    async def update_status(
        self, order_id: uuid.UUID, new_status: OrderStatus
    ) -> Order:
        order = await self.order_repo.find_by_id(order_id)
        if order is None:
            raise ValueError("Order not found")

        current = order.status
        if new_status not in VALID_TRANSITIONS.get(current, set()):
            allowed = ", ".join(s.value for s in VALID_TRANSITIONS.get(current, set()))
            raise ValueError(
                f"Invalid status transition: {current.value} → {new_status.value}. "
                f"Allowed: [{allowed}]"
            )

        updated = await self.order_repo.update_status(order_id, new_status)

        self._publish_status_event(
            order_id=str(order_id),
            customer_id=str(order.customer_id),
            restaurant_id=str(order.restaurant_id),
            courier_id=str(order.courier_id) if order.courier_id else None,
            previous_status=current.value,
            new_status=new_status.value,
        )

        return updated

    def _publish_status_event(
        self,
        order_id: str,
        customer_id: str,
        restaurant_id: str,
        courier_id: str | None,
        previous_status: str,
        new_status: str,
    ) -> None:
        event = {
            "order_id": order_id,
            "customer_id": customer_id,
            "restaurant_id": restaurant_id,
            "courier_id": courier_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.kafka_producer.produce(
                topic=settings.kafka_topic,
                key=order_id,
                value=json.dumps(event),
            )
            self.kafka_producer.flush(timeout=5.0)
            logger.info(
                "Published event: %s → %s for order %s",
                previous_status,
                new_status,
                order_id,
            )
        except Exception as e:
            logger.error("Failed to publish Kafka event: %s", e)
