import json

from app.domain.models import OrderStatusEvent
from app.repository.notification_repository import NotificationRepository


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


def test_save_appends_json_line(tmp_path):
    log_file = tmp_path / "notifications.log"
    repo = NotificationRepository(log_path=str(log_file))
    repo.save(_make_event())
    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["order_id"] == "order-1"
    assert data["new_status"] == "PREPARING"


def test_save_appends_multiple_events(tmp_path):
    log_file = tmp_path / "notifications.log"
    repo = NotificationRepository(log_path=str(log_file))
    repo.save(_make_event(order_id="order-1"))
    repo.save(_make_event(order_id="order-2"))
    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["order_id"] == "order-1"
    assert json.loads(lines[1])["order_id"] == "order-2"


def test_save_creates_parent_directory(tmp_path):
    log_file = tmp_path / "nested" / "dir" / "notifications.log"
    repo = NotificationRepository(log_path=str(log_file))
    repo.save(_make_event())
    assert log_file.exists()


def test_save_json_includes_all_fields(tmp_path):
    log_file = tmp_path / "notifications.log"
    repo = NotificationRepository(log_path=str(log_file))
    event = _make_event(courier_id="courier-1", new_status="DELIVERED")
    repo.save(event)
    data = json.loads(log_file.read_text())
    assert data["courier_id"] == "courier-1"
    assert data["customer_id"] == "customer-1"
    assert data["restaurant_id"] == "restaurant-1"
    assert data["timestamp"] == "2025-01-15T14:35:00Z"
