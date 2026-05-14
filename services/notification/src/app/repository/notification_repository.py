import logging

from app.domain.models import OrderStatusEvent

logger = logging.getLogger(__name__)


class NotificationRepository:
    def save(self, event: OrderStatusEvent) -> None:
        logger.info(
            "Notification dispatched: order=%s status=%s→%s customer=%s",
            event.order_id,
            event.previous_status,
            event.new_status,
            event.customer_id,
        )
