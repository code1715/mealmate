from neo4j import GraphDatabase, Driver
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "mealmate"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Module-level singleton — assigned in lifespan, read by get_driver()
driver: Driver | None = None


def init_driver() -> Driver:
    """Create and verify the Neo4j driver. Raises ServiceUnavailable if unreachable."""
    d = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    d.verify_connectivity()
    return d


def get_driver() -> Driver:
    assert driver is not None, "Neo4j driver not initialized"
    return driver
