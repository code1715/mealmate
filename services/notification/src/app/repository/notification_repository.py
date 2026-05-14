import logging
import os

from app.domain.models import OrderStatusEvent

logger = logging.getLogger(__name__)


class NotificationRepository:
    def __init__(self, log_path: str) -> None:
        self._log_path = log_path

    def save(self, event: OrderStatusEvent) -> None:
        logger.info(
            "Notification dispatched: order=%s status=%s→%s customer=%s",
            event.order_id,
            event.previous_status,
            event.new_status,
            event.customer_id,
        )
        log_dir = os.path.dirname(self._log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(self._log_path, "a") as f:
            f.write(event.model_dump_json() + "\n")
