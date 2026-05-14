import uuid

from app.domain.models import Courier, CourierStatus, MatchResult
from app.repositories.neo4j_repo import Neo4jRepository


class MatchingService:
    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

    def match(self, order_id: uuid.UUID, restaurant_id: uuid.UUID) -> MatchResult:
        raise NotImplementedError

    def update_courier_status(
        self, courier_id: uuid.UUID, status: CourierStatus
    ) -> Courier | None:
        return self._repo.update_courier_status(courier_id, status)
