import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.domain.models import CourierStatus, Courier, MatchResult, MatchRequest, CourierStatusUpdate


def test_courier_status_enum_values():
    assert CourierStatus.AVAILABLE == "AVAILABLE"
    assert CourierStatus.BUSY == "BUSY"
    assert CourierStatus.OFFLINE == "OFFLINE"


def test_courier_model():
    c = Courier(courier_id=uuid.uuid4(), status=CourierStatus.AVAILABLE)
    assert c.status == CourierStatus.AVAILABLE


def test_match_result_model():
    r = MatchResult(order_id=uuid.uuid4(), courier_id=uuid.uuid4(), estimated_minutes=12)
    assert r.estimated_minutes == 12


def test_courier_status_update_model():
    u = CourierStatusUpdate(status=CourierStatus.OFFLINE)
    assert u.status == CourierStatus.OFFLINE


# --- Task 2: Settings ---

from app.core.database import Settings


def test_settings_defaults():
    s = Settings()
    assert s.neo4j_uri == "bolt://neo4j:7687"
    assert s.neo4j_user == "neo4j"
    assert s.neo4j_password == "mealmate"


# --- Task 3: Repository ---

from app.repositories.neo4j_repo import Neo4jRepository


def test_repo_find_available_couriers_raises_not_implemented():
    repo = Neo4jRepository(MagicMock())
    with pytest.raises(NotImplementedError):
        repo.find_available_couriers()


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
    mock_session.run.return_value.single.return_value = {
        "c": {"courier_id": str(courier_id), "status": "AVAILABLE"}
    }

    repo = Neo4jRepository(mock_driver)
    courier = repo.update_courier_status(courier_id, CourierStatus.AVAILABLE)
    assert courier is not None
    assert courier.courier_id == courier_id
    assert courier.status == CourierStatus.AVAILABLE


# --- Task 4: Service layer ---

from app.services.matching import MatchingService


def test_matching_service_update_status_delegates_to_repo():
    mock_repo = MagicMock()
    courier_id = uuid.uuid4()
    expected = Courier(courier_id=courier_id, status=CourierStatus.AVAILABLE)
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


def test_matching_service_match_raises_not_implemented():
    svc = MatchingService(MagicMock())
    with pytest.raises(NotImplementedError):
        svc.match(uuid.uuid4(), uuid.uuid4())


# --- Task 5: HTTP routes and main app ---

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


def test_match_endpoint_not_implemented_returns_501(client):
    resp = client.post(
        "/api/routing/match",
        json={"order_id": str(uuid.uuid4()), "restaurant_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 501


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
    mock_session.run.return_value.single.return_value = {
        "c": {"courier_id": str(courier_id), "status": "AVAILABLE"}
    }

    resp = client.patch(
        f"/api/routing/couriers/{courier_id}/status",
        json={"status": "AVAILABLE"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["courier_id"] == str(courier_id)
    assert body["status"] == "AVAILABLE"
