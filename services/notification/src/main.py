import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.consumer.kafka_consumer import NotificationKafkaConsumer
from app.repository.notification_repository import NotificationRepository
from app.service.notification_service import NotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_consumer: NotificationKafkaConsumer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer
    repo = NotificationRepository()
    service = NotificationService(repo=repo)
    _consumer = NotificationKafkaConsumer(
        service=service,
        brokers=settings.kafka_brokers,
        topic=settings.kafka_topic,
        group_id=settings.kafka_group_id,
    )
    thread = threading.Thread(
        target=_consumer.start, daemon=True, name="kafka-consumer"
    )
    thread.start()
    logger.info("Notification service started")
    yield
    if _consumer:
        _consumer.stop()
    thread.join(timeout=5)
    logger.info("Notification service stopped")


app = FastAPI(title="notification-service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
