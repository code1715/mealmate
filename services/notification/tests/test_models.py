import pytest
from app.domain.models import OrderStatusEvent


def test_order_status_event_valid_payload():
    payload = {
        "order_id": "550e8400-e29b-41d4-a716-446655440000",
        "customer_id": "550e8400-e29b-41d4-a716-446655440001",
        "restaurant_id": "550e8400-e29b-41d4-a716-446655440002",
        "courier_id": None,
        "previous_status": "PLACED",
        "new_status": "PREPARING",
        "timestamp": "2025-01-15T14:35:00Z",
    }
    event = OrderStatusEvent(**payload)
    assert event.order_id == "550e8400-e29b-41d4-a716-446655440000"
    assert event.courier_id is None
    assert event.new_status == "PREPARING"


def test_order_status_event_with_courier():
    payload = {
        "order_id": "550e8400-e29b-41d4-a716-446655440000",
        "customer_id": "550e8400-e29b-41d4-a716-446655440001",
        "restaurant_id": "550e8400-e29b-41d4-a716-446655440002",
        "courier_id": "550e8400-e29b-41d4-a716-446655440003",
        "previous_status": "READY",
        "new_status": "PICKED_UP",
        "timestamp": "2025-01-15T14:40:00Z",
    }
    event = OrderStatusEvent(**payload)
    assert event.courier_id == "550e8400-e29b-41d4-a716-446655440003"
    assert event.previous_status == "READY"


def test_order_status_event_missing_required_field_raises():
    with pytest.raises(Exception):
        OrderStatusEvent(order_id="abc")  # missing all other required fields


def test_order_status_event_all_status_values():
    statuses = ["PLACED", "PREPARING", "READY", "PICKED_UP", "DELIVERED", "CANCELLED"]
    for status in statuses:
        event = OrderStatusEvent(
            order_id="o1",
            customer_id="c1",
            restaurant_id="r1",
            courier_id=None,
            previous_status="PLACED",
            new_status=status,
            timestamp="2025-01-15T14:35:00Z",
        )
        assert event.new_status == status
