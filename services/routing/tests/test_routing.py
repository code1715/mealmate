import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.domain.models import (
    CourierStatus,
    Courier,
    Zone,
    Restaurant,
    MatchResult,
    MatchRequest,
    CourierStatusUpdate,
)


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------

def test_courier_status_enum_values():
    assert CourierStatus.AVAILABLE == "AVAILABLE"
    assert CourierStatus.BUSY == "BUSY"
    assert CourierStatus.OFFLINE == "OFFLINE"


def test_courier_model_full():
    cid = uuid.uuid4()
    c = Courier(
        id=cid,
        name="Ivan Petrenko",
        status=CourierStatus.AVAILABLE,
        lat=50.45,
        lng=30.52,
    )
    assert c.id == cid
    assert c.name == "Ivan Petrenko"
    assert c.status == CourierStatus.AVAILABLE
    assert c.lat == 50.45
    assert c.lng == 30.52


def test_zone_model():
    zid = uuid.uuid4()
    z = Zone(id=zid, name="Podil")
    assert z.id == zid
    assert z.name == "Podil"


def test_restaurant_model():
    rid = uuid.uuid4()
    zid = uuid.uuid4()
    r = Restaurant(
        id=rid,
        name="Chicken Kyiv",
        zone_id=zid,
        lat=50.46,
        lng=30.53,
    )
    assert r.id == rid
    assert r.zone_id == zid
    assert r.lat == 50.46
    assert r.lng == 30.53


def test_match_result_model():
    r = MatchResult(order_id=uuid.uuid4(), courier_id=uuid.uuid4(), estimated_minutes=12)
    assert r.estimated_minutes == 12


def test_courier_status_update_model():
    u = CourierStatusUpdate(status=CourierStatus.OFFLINE)
    assert u.status == CourierStatus.OFFLINE


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

from app.core.database import Settings


def test_settings_defaults():
    s = Settings()
    assert s.neo4j_uri == "bolt://neo4j:7687"
    assert s.neo4j_user == "neo4j"
    assert s.neo4j_password == "mealmate"


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

from app.repositories.neo4j_repo import Neo4jRepository


def _courier_node(courier_id: uuid.UUID) -> dict:
    return {
        "c": {
            "id": str(courier_id),
            "name": "Ivan Petrenko",
            "status": "AVAILABLE",
            "lat": 50.45,
            "lng": 30.52,
        }
    }


def _restaurant_node(restaurant_id: uuid.UUID, zone_id: uuid.UUID) -> dict:
    return {
        "r": {
            "id": str(restaurant_id),
            "name": "Burger Palace",
            "zone_id": str(zone_id),
            "lat": 50.462,
            "lng": 30.519,
        }
    }


def test_repo_get_restaurant_not_found():
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = None

    repo = Neo4jRepository(mock_driver)
    assert repo.get_restaurant(uuid.uuid4()) is None


def test_repo_get_restaurant_found():
    restaurant_id = uuid.uuid4()
    zone_id = uuid.uuid4()
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = _restaurant_node(restaurant_id, zone_id)

    repo = Neo4jRepository(mock_driver)
    restaurant = repo.get_restaurant(restaurant_id)
    assert restaurant is not None
    assert restaurant.id == restaurant_id
    assert restaurant.zone_id == zone_id
    assert restaurant.lat == 50.462
    assert restaurant.lng == 30.519


def test_repo_find_available_couriers_in_zone_returns_list():
    courier_id = uuid.uuid4()
    zone_id = uuid.uuid4()
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = [_courier_node(courier_id)]

    repo = Neo4jRepository(mock_driver)
    couriers = repo.find_available_couriers_in_zone(zone_id)
    assert len(couriers) == 1
    assert couriers[0].id == courier_id
    assert couriers[0].status == CourierStatus.AVAILABLE


def test_repo_find_available_couriers_in_zone_empty():
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = []

    repo = Neo4jRepository(mock_driver)
    assert repo.find_available_couriers_in_zone(uuid.uuid4()) == []


def test_repo_find_all_available_couriers():
    courier_id = uuid.uuid4()
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = [_courier_node(courier_id)]

    repo = Neo4jRepository(mock_driver)
    couriers = repo.find_all_available_couriers()
    assert len(couriers) == 1
    assert couriers[0].id == courier_id


def test_repo_update_courier_status_not_found():
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = None

    repo = Neo4jRepository(mock_driver)
    result = repo.update_courier_status(uuid.uuid4(), CourierStatus.AVAILABLE)
    assert result is None


def test_repo_update_courier_status_found():
    courier_id = uuid.uuid4()
    mock_driver = MagicMock()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = _courier_node(courier_id)

    repo = Neo4jRepository(mock_driver)
    courier = repo.update_courier_status(courier_id, CourierStatus.AVAILABLE)
    assert courier is not None
    assert courier.id == courier_id
    assert courier.name == "Ivan Petrenko"
    assert courier.status == CourierStatus.AVAILABLE
    assert courier.lat == 50.45
    assert courier.lng == 30.52


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

from app.services.matching import MatchingService


def _make_restaurant(zone_id: uuid.UUID | None = None) -> Restaurant:
    return Restaurant(
        id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        name="Burger Palace",
        zone_id=zone_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
        lat=50.462,
        lng=30.519,
    )


def _make_courier(courier_id: uuid.UUID | None = None) -> Courier:
    return Courier(
        id=courier_id or uuid.uuid4(),
        name="Ivan Petrenko",
        status=CourierStatus.AVAILABLE,
        lat=50.464,
        lng=30.520,
    )


def test_matching_service_match_returns_nearest_in_zone():
    mock_repo = MagicMock()
    restaurant = _make_restaurant()
    courier = _make_courier()
    mock_repo.get_restaurant.return_value = restaurant
    mock_repo.find_available_couriers_in_zone.return_value = [courier]

    order_id = uuid.uuid4()
    result = MatchingService(mock_repo).match(order_id, restaurant.id)

    assert result.order_id == order_id
    assert result.courier_id == courier.id
    assert result.estimated_minutes >= 1
    mock_repo.find_all_available_couriers.assert_not_called()


def test_matching_service_match_falls_back_to_all_zones():
    mock_repo = MagicMock()
    restaurant = _make_restaurant()
    courier = _make_courier()
    mock_repo.get_restaurant.return_value = restaurant
    mock_repo.find_available_couriers_in_zone.return_value = []
    mock_repo.find_all_available_couriers.return_value = [courier]

    result = MatchingService(mock_repo).match(uuid.uuid4(), restaurant.id)
    assert result.courier_id == courier.id


def test_matching_service_match_raises_restaurant_not_found():
    mock_repo = MagicMock()
    mock_repo.get_restaurant.return_value = None

    with pytest.raises(ValueError, match="Restaurant not found"):
        MatchingService(mock_repo).match(uuid.uuid4(), uuid.uuid4())


def test_matching_service_match_raises_no_couriers_available():
    mock_repo = MagicMock()
    mock_repo.get_restaurant.return_value = _make_restaurant()
    mock_repo.find_available_couriers_in_zone.return_value = []
    mock_repo.find_all_available_couriers.return_value = []

    with pytest.raises(ValueError, match="No couriers available"):
        MatchingService(mock_repo).match(uuid.uuid4(), uuid.uuid4())


def test_matching_service_match_picks_nearest_of_two_couriers():
    mock_repo = MagicMock()
    restaurant = _make_restaurant()
    # near courier — ~0.25 km away
    near = Courier(id=uuid.uuid4(), name="Near", status=CourierStatus.AVAILABLE, lat=50.464, lng=30.520)
    # far courier — ~5 km away
    far = Courier(id=uuid.uuid4(), name="Far", status=CourierStatus.AVAILABLE, lat=50.510, lng=30.560)
    mock_repo.get_restaurant.return_value = restaurant
    mock_repo.find_available_couriers_in_zone.return_value = [near, far]

    result = MatchingService(mock_repo).match(uuid.uuid4(), restaurant.id)
    assert result.courier_id == near.id


def test_matching_service_update_status_delegates_to_repo():
    mock_repo = MagicMock()
    courier_id = uuid.uuid4()
    expected = _make_courier(courier_id)
    mock_repo.update_courier_status.return_value = expected

    svc = MatchingService(mock_repo)
    result = svc.update_courier_status(courier_id, CourierStatus.AVAILABLE)

    mock_repo.update_courier_status.assert_called_once_with(courier_id, CourierStatus.AVAILABLE)
    assert result == expected


def test_matching_service_update_status_not_found():
    mock_repo = MagicMock()
    mock_repo.update_courier_status.return_value = None

    svc = MatchingService(mock_repo)
    assert svc.update_courier_status(uuid.uuid4(), CourierStatus.OFFLINE) is None


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_driver


@pytest.fixture
def mock_driver():
    return MagicMock()


@pytest.fixture
def client(mock_driver):
    with patch("app.core.database.init_driver", return_value=mock_driver):
        app.dependency_overrides[get_driver] = lambda: mock_driver
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def test_health_returns_ok_with_service_name(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "routing-service"}


def test_match_endpoint_returns_200(client):
    order_id = uuid.uuid4()
    restaurant_id = uuid.uuid4()
    courier_id = uuid.uuid4()
    expected = MatchResult(order_id=order_id, courier_id=courier_id, estimated_minutes=5)

    with patch.object(MatchingService, "match", return_value=expected):
        resp = client.post(
            "/api/routing/match",
            json={"order_id": str(order_id), "restaurant_id": str(restaurant_id)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == str(order_id)
    assert body["courier_id"] == str(courier_id)
    assert body["estimated_minutes"] == 5


def test_match_endpoint_returns_404_when_no_couriers(client):
    with patch.object(MatchingService, "match", side_effect=ValueError("No couriers available")):
        resp = client.post(
            "/api/routing/match",
            json={"order_id": str(uuid.uuid4()), "restaurant_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "No couriers available"


def test_match_endpoint_returns_404_when_restaurant_not_found(client):
    with patch.object(MatchingService, "match", side_effect=ValueError("Restaurant not found")):
        resp = client.post(
            "/api/routing/match",
            json={"order_id": str(uuid.uuid4()), "restaurant_id": str(uuid.uuid4())},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Restaurant not found"


def test_update_courier_status_not_found(client, mock_driver):
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = None

    courier_id = uuid.uuid4()
    resp = client.patch(
        f"/api/routing/couriers/{courier_id}/status",
        json={"status": "AVAILABLE"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Courier not found"


def test_update_courier_status_success(client, mock_driver):
    courier_id = uuid.uuid4()
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value.single.return_value = _courier_node(courier_id)

    resp = client.patch(
        f"/api/routing/couriers/{courier_id}/status",
        json={"status": "AVAILABLE"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(courier_id)
    assert body["name"] == "Ivan Petrenko"
    assert body["status"] == "AVAILABLE"
    assert body["lat"] == 50.45
    assert body["lng"] == 30.52
