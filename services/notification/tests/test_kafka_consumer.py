import json
from unittest.mock import MagicMock

from app.consumer.kafka_consumer import NotificationKafkaConsumer
from app.domain.models import OrderStatusEvent


def _sample_event_bytes() -> bytes:
    return json.dumps({
        "order_id": "order-1",
        "customer_id": "customer-1",
        "restaurant_id": "restaurant-1",
        "courier_id": None,
        "previous_status": "PLACED",
        "new_status": "PREPARING",
        "timestamp": "2025-01-15T14:35:00Z",
    }).encode()


def test_process_raw_calls_service_with_parsed_event():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    consumer._process_raw(_sample_event_bytes())
    service.handle.assert_called_once()
    call_arg = service.handle.call_args[0][0]
    assert isinstance(call_arg, OrderStatusEvent)
    assert call_arg.order_id == "order-1"
    assert call_arg.new_status == "PREPARING"


def test_process_raw_invalid_json_does_not_crash():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    consumer._process_raw(b"not-valid-json")
    service.handle.assert_not_called()


def test_process_raw_missing_field_does_not_crash():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    consumer._process_raw(json.dumps({"order_id": "x"}).encode())
    service.handle.assert_not_called()


def test_stop_sets_running_false():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    consumer._running = True
    consumer.stop()
    assert consumer._running is False


def test_initial_running_state_is_false():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    assert consumer._running is False
