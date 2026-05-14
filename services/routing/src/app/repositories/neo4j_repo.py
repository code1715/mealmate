import uuid

from neo4j import Driver

from app.domain.models import Courier, CourierStatus


class Neo4jRepository:
    def __init__(self, driver: Driver):
        self._driver = driver

    def find_available_couriers(self) -> list[Courier]:
        raise NotImplementedError

    def update_courier_status(
        self, courier_id: uuid.UUID, status: CourierStatus
    ) -> Courier | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (c:Courier {courier_id: $courier_id})
                SET c.status = $status
                RETURN c
                """,
                courier_id=str(courier_id),
                status=status.value,
            )
            record = result.single()
            if record is None:
                return None
            node = record["c"]
            return Courier(
                courier_id=uuid.UUID(node["courier_id"]),
                status=CourierStatus(node["status"]),
            )
