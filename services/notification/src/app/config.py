from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_brokers: str = "kafka:29092"
    kafka_topic: str = "order-status-changed"
    kafka_group_id: str = "notification-service"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
