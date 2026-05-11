from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Postgres
    postgres_url: str = "postgresql+asyncpg://mealmate:mealmate@postgres:5432/mealmate"

    # Redis
    redis_url: str = "redis://redis:6379/0"
    redis_token_ttl: int = 3600  # seconds

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
