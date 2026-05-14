import logging

from app.domain.models import OrderStatusEvent
from app.repository.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def handle(self, event: OrderStatusEvent) -> None:
        logger.info(
            "Processing notification for order=%s transition=%s→%s",
            event.order_id,
            event.previous_status,
            event.new_status,
        )
        self.repo.save(event)
