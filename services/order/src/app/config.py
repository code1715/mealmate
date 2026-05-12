from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Order Service settings loaded from environment variables."""

    # Postgres
    postgres_url: str = (
        "postgresql+asyncpg://mealmate:mealmate@postgres-orders:5432/orders"
    )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Kafka
    kafka_brokers: str = "kafka:29092"
    kafka_topic: str = "order-status-changed"

    # Auth Service (for token validation)
    auth_service_url: str = "http://auth:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
