import uuid

from neo4j import Driver

from app.domain.models import Courier, CourierStatus, Restaurant


class Neo4jRepository:
    def __init__(self, driver: Driver):
        self._driver = driver

    def get_restaurant(self, restaurant_id: uuid.UUID) -> Restaurant | None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (r:Restaurant {id: $restaurant_id}) RETURN r",
                restaurant_id=str(restaurant_id),
            )
            record = result.single()
            if record is None:
                return None
            node = record["r"]
            return Restaurant(
                id=uuid.UUID(node["id"]),
                name=node["name"],
                zone_id=uuid.UUID(node["zone_id"]),
                lat=node["lat"],
                lng=node["lng"],
            )

    def find_available_couriers_in_zone(self, zone_id: uuid.UUID) -> list[Courier]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (c:Courier)-[:LOCATED_IN]->(z:Zone {id: $zone_id})
                WHERE c.status = 'AVAILABLE'
                RETURN c
                """,
                zone_id=str(zone_id),
            )
            return [_record_to_courier(r) for r in result]

    def find_all_available_couriers(self) -> list[Courier]:
        with self._driver.session() as session:
            result = session.run("MATCH (c:Courier {status: 'AVAILABLE'}) RETURN c")
            return [_record_to_courier(r) for r in result]

    def update_courier_status(
        self, courier_id: uuid.UUID, status: CourierStatus
    ) -> Courier | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (c:Courier {id: $courier_id})
                SET c.status = $status
                RETURN c
                """,
                courier_id=str(courier_id),
                status=status.value,
            )
            record = result.single()
            if record is None:
                return None
            return _record_to_courier(record)


def _record_to_courier(record: dict) -> Courier:
    node = record["c"]
    return Courier(
        id=uuid.UUID(node["id"]),
        name=node["name"],
        status=CourierStatus(node["status"]),
        lat=node["lat"],
        lng=node["lng"],
    )
