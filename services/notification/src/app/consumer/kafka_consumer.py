import json
import logging

from confluent_kafka import Consumer, KafkaError, KafkaException

from app.domain.models import OrderStatusEvent
from app.service.notification_service import NotificationService

logger = logging.getLogger(__name__)


class NotificationKafkaConsumer:
    def __init__(self, service: NotificationService, brokers: str, topic: str, group_id: str):
        self._service = service
        self._brokers = brokers
        self._topic = topic
        self._group_id = group_id
        self._running = False

    def start(self) -> None:
        try:
            consumer = Consumer({
                "bootstrap.servers": self._brokers,
                "group.id": self._group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            })
        except KafkaException as e:
            logger.error("Kafka consumer init failed: %s", e)
            return

        consumer.subscribe([self._topic])
        self._running = True
        logger.info(
            "Kafka consumer started — topic=%s group=%s brokers=%s",
            self._topic,
            self._group_id,
            self._brokers,
        )

        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error: %s", msg.error())
                    continue
                if self._process_raw(msg.value()):
                    consumer.commit(message=msg)
        finally:
            consumer.close()
            logger.info("Kafka consumer closed")

    def stop(self) -> None:
        self._running = False

    def _process_raw(self, value: bytes) -> bool:
        try:
            data = json.loads(value)
            event = OrderStatusEvent(**data)
        except Exception as e:
            logger.error("Failed to parse Kafka message: %s — raw=%s", e, value[:200])
            return False
        self._service.handle(event)
        return True
