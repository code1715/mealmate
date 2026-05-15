import uuid

from app.domain.models import Courier, CourierStatus, MatchResult
from app.repositories.neo4j_repo import Neo4jRepository
from app.utils.haversine import haversine

_COURIER_SPEED_KM_PER_MIN = 0.5  # 30 km/h


class MatchingService:
    def __init__(self, repo: Neo4jRepository):
        self._repo = repo

    def match(self, order_id: uuid.UUID, restaurant_id: uuid.UUID) -> MatchResult:
        restaurant = self._repo.get_restaurant(restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant not found")

        couriers = self._repo.find_available_couriers_in_zone(restaurant.zone_id)
        if not couriers:
            couriers = self._repo.find_all_available_couriers()
        if not couriers:
            raise ValueError("No couriers available")

        nearest = min(
            couriers,
            key=lambda c: haversine(restaurant.lat, restaurant.lng, c.lat, c.lng),
        )
        distance_km = haversine(restaurant.lat, restaurant.lng, nearest.lat, nearest.lng)
        estimated_minutes = max(1, round(distance_km / _COURIER_SPEED_KM_PER_MIN))

        return MatchResult(
            order_id=order_id,
            courier_id=nearest.id,
            estimated_minutes=estimated_minutes,
        )

    def update_courier_status(
        self, courier_id: uuid.UUID, status: CourierStatus
    ) -> Courier | None:
        return self._repo.update_courier_status(courier_id, status)
