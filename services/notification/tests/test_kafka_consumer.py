import json
from unittest.mock import MagicMock, patch

from confluent_kafka import KafkaError

from app.config import Settings
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


def test_default_group_id_is_notification_group():
    assert Settings.model_fields["kafka_group_id"].default == "notification-group"


def test_process_raw_returns_true_on_success():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    result = consumer._process_raw(_sample_event_bytes())
    assert result is True


def test_process_raw_returns_false_on_invalid_json():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    result = consumer._process_raw(b"not-valid-json")
    assert result is False


def test_process_raw_returns_false_on_missing_fields():
    service = MagicMock()
    consumer = NotificationKafkaConsumer(
        service=service, brokers="localhost:9092", topic="t", group_id="g"
    )
    result = consumer._process_raw(json.dumps({"order_id": "x"}).encode())
    assert result is False


def test_non_eof_error_sleeps_before_continuing():
    with patch("app.consumer.kafka_consumer.time") as mock_time:
        with patch("app.consumer.kafka_consumer.Consumer") as MockConsumer:
            mock_kafka = MockConsumer.return_value
            service = MagicMock()
            consumer = NotificationKafkaConsumer(
                service=service, brokers="b", topic="t", group_id="g"
            )
            error_msg = MagicMock()
            error_msg.error.return_value.code.return_value = KafkaError.BROKER_NOT_AVAILABLE

            def poll_side_effect(timeout):
                consumer.stop()
                return error_msg

            mock_kafka.poll.side_effect = poll_side_effect
            consumer.start()
            mock_time.sleep.assert_called_once_with(5)


def test_eof_error_does_not_sleep():
    with patch("app.consumer.kafka_consumer.time") as mock_time:
        with patch("app.consumer.kafka_consumer.Consumer") as MockConsumer:
            mock_kafka = MockConsumer.return_value
            service = MagicMock()
            consumer = NotificationKafkaConsumer(
                service=service, brokers="b", topic="t", group_id="g"
            )
            eof_msg = MagicMock()
            eof_msg.error.return_value.code.return_value = KafkaError._PARTITION_EOF

            def poll_side_effect(timeout):
                consumer.stop()
                return eof_msg

            mock_kafka.poll.side_effect = poll_side_effect
            consumer.start()
            mock_time.sleep.assert_not_called()
