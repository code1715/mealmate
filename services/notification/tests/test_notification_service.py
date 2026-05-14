from unittest.mock import MagicMock

from app.domain.models import OrderStatusEvent
from app.service.notification_service import NotificationService


def _make_event(**kwargs) -> OrderStatusEvent:
    base = {
        "order_id": "order-1",
        "customer_id": "customer-1",
        "restaurant_id": "restaurant-1",
        "courier_id": None,
        "previous_status": "PLACED",
        "new_status": "PREPARING",
        "timestamp": "2025-01-15T14:35:00Z",
    }
    base.update(kwargs)
    return OrderStatusEvent(**base)


def test_handle_calls_repository_save():
    repo = MagicMock()
    service = NotificationService(repo=repo)
    event = _make_event()
    service.handle(event)
    repo.save.assert_called_once_with(event)


def test_handle_with_courier_assigned():
    repo = MagicMock()
    service = NotificationService(repo=repo)
    event = _make_event(
        courier_id="courier-1",
        previous_status="READY",
        new_status="PICKED_UP",
    )
    service.handle(event)
    repo.save.assert_called_once_with(event)


def test_handle_delivered_event():
    repo = MagicMock()
    service = NotificationService(repo=repo)
    event = _make_event(
        courier_id="courier-1",
        previous_status="PICKED_UP",
        new_status="DELIVERED",
    )
    service.handle(event)
    repo.save.assert_called_once_with(event)
