"""Order Service — integration tests.

All external dependencies (Postgres, Redis, Kafka, Auth Service) are mocked
so the tests run without Docker.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies import CurrentUser
from app.models.domain import Order, OrderItem, OrderStatus
from app.services.order_service import OrderService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CUSTOMER_ID = uuid.uuid4()
RESTAURANT_ID = uuid.uuid4()
COURIER_ID = uuid.uuid4()
OTHER_CUSTOMER_ID = uuid.uuid4()


def _make_order(
    *,
    order_id=None,
    customer_id=None,
    restaurant_id=None,
    courier_id=None,
    status=OrderStatus.PLACED,
    total_price=19.98,
) -> Order:
    return Order(
        id=order_id or uuid.uuid4(),
        customer_id=customer_id or CUSTOMER_ID,
        restaurant_id=restaurant_id or RESTAURANT_ID,
        courier_id=courier_id,
        status=status,
        total_price=total_price,
        items=[
            OrderItem(
                id=uuid.uuid4(),
                menu_item_id=uuid.uuid4(),
                name="Margherita",
                quantity=2,
                unit_price=9.99,
            )
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Provide an httpx AsyncClient with the FastAPI app and mocked deps."""

    # We patch at the import level so route handlers receive our mocks.
    with (
        patch("app.dependencies.engine") as _,
        patch("app.dependencies.redis_client"),
        patch("app.dependencies.async_session_factory"),
        patch("app.api.orders.get_kafka_producer") as mock_kafka,
    ):
        mock_producer = MagicMock()
        mock_kafka.return_value = mock_producer

        # Import app AFTER patches are in place so lifespan doesn't hit real DB
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Stash the mock producer for test assertions
            c._kafka_producer = mock_producer  # type: ignore[attr-defined]
            yield c


def _auth_header(user_id: uuid.UUID, role: str) -> dict:
    """Build an Authorization header and mock the get_current_user dependency."""
    return {"Authorization": f"Bearer faketoken"}


# We override FastAPI dependencies rather than mocking httpx calls to Auth Service.
from app.dependencies import get_current_user
from app.main import app as _app


def _override_auth(user_id: uuid.UUID, role: str):
    """Override get_current_user to return a specific CurrentUser."""
    _app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=user_id, role=role
    )


def _clear_auth_override():
    _app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests — POST /orders (create)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_order_as_customer(client):
    """Customer can create an order → 201."""
    _override_auth(CUSTOMER_ID, "customer")

    order = _make_order(customer_id=CUSTOMER_ID)

    with patch(
        "app.services.order_service.OrderService.create_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.post(
            "/api/orders",
            json={
                "restaurant_id": str(RESTAURANT_ID),
                "items": [
                    {
                        "menu_item_id": str(uuid.uuid4()),
                        "name": "Margherita",
                        "quantity": 2,
                        "unit_price": 9.99,
                    }
                ],
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PLACED"
    assert body["customer_id"] == str(CUSTOMER_ID)
    assert body["restaurant_id"] == str(RESTAURANT_ID)
    assert "courier_id" in body
    assert "updated_at" in body

    _clear_auth_override()


@pytest.mark.asyncio
async def test_create_order_as_restaurant_forbidden(client):
    """Restaurant role cannot create orders → 403."""
    _override_auth(RESTAURANT_ID, "restaurant")

    resp = await client.post(
        "/api/orders",
        json={
            "restaurant_id": str(RESTAURANT_ID),
            "items": [
                {
                    "menu_item_id": str(uuid.uuid4()),
                    "name": "Margherita",
                    "quantity": 2,
                    "unit_price": 9.99,
                }
            ],
        },
    )

    assert resp.status_code == 403
    assert "customer" in resp.json()["detail"].lower()

    _clear_auth_override()


@pytest.mark.asyncio
async def test_create_order_as_courier_forbidden(client):
    """Courier role cannot create orders → 403."""
    _override_auth(COURIER_ID, "courier")

    resp = await client.post(
        "/api/orders",
        json={
            "restaurant_id": str(RESTAURANT_ID),
            "items": [
                {
                    "menu_item_id": str(uuid.uuid4()),
                    "name": "Margherita",
                    "quantity": 2,
                    "unit_price": 9.99,
                }
            ],
        },
    )

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_create_order_no_auth(client):
    """No auth header → 401 (or 422 if header missing)."""
    resp = await client.post(
        "/api/orders",
        json={
            "restaurant_id": str(RESTAURANT_ID),
            "items": [
                {
                    "menu_item_id": str(uuid.uuid4()),
                    "name": "Margherita",
                    "quantity": 2,
                    "unit_price": 9.99,
                }
            ],
        },
    )
    assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Tests — GET /orders/{order_id} (get single)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_order_owner_customer(client):
    """Customer who owns the order can retrieve it → 200."""
    _override_auth(CUSTOMER_ID, "customer")
    order = _make_order(customer_id=CUSTOMER_ID)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 200
    assert resp.json()["id"] == str(order.id)
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_wrong_customer_403(client):
    """Customer who does NOT own the order gets 403."""
    _override_auth(OTHER_CUSTOMER_ID, "customer")
    order = _make_order(customer_id=CUSTOMER_ID)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_assigned_courier(client):
    """Assigned courier can retrieve the order → 200."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(customer_id=CUSTOMER_ID, courier_id=COURIER_ID)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 200
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_unassigned_courier_403(client):
    """Unassigned courier gets 403."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(customer_id=CUSTOMER_ID, courier_id=uuid.uuid4())

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_owner_restaurant(client):
    """Restaurant that owns the order can retrieve it → 200."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 200
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_wrong_restaurant_403(client):
    """Different restaurant gets 403."""
    _override_auth(uuid.uuid4(), "restaurant")
    order = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.get(f"/api/orders/{order.id}")

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_get_order_not_found(client):
    """Non-existent order → 404."""
    _override_auth(CUSTOMER_ID, "customer")
    fake_id = uuid.uuid4()

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await client.get(f"/api/orders/{fake_id}")

    assert resp.status_code == 404
    _clear_auth_override()


# ---------------------------------------------------------------------------
# Tests — GET /orders (list)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_orders_customer(client):
    """Customer sees only their own orders."""
    _override_auth(CUSTOMER_ID, "customer")
    order = _make_order(customer_id=CUSTOMER_ID)

    with patch(
        "app.services.order_service.OrderService.list_orders",
        new_callable=AsyncMock,
        return_value=[order],
    ):
        resp = await client.get("/api/orders")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    _clear_auth_override()


@pytest.mark.asyncio
async def test_list_orders_restaurant_with_customer_id(client):
    """Restaurant can list orders for a specific customer_id."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(customer_id=CUSTOMER_ID)

    with patch(
        "app.services.order_service.OrderService.list_orders",
        new_callable=AsyncMock,
        return_value=[order],
    ):
        resp = await client.get("/api/orders", params={"customer_id": str(CUSTOMER_ID)})

    assert resp.status_code == 200
    _clear_auth_override()


@pytest.mark.asyncio
async def test_list_orders_restaurant_missing_customer_id(client):
    """Restaurant without customer_id query param → 400."""
    _override_auth(RESTAURANT_ID, "restaurant")

    resp = await client.get("/api/orders")

    assert resp.status_code == 400
    _clear_auth_override()


@pytest.mark.asyncio
async def test_list_orders_courier_forbidden(client):
    """Courier cannot list orders → 403."""
    _override_auth(COURIER_ID, "courier")

    resp = await client.get("/api/orders")

    assert resp.status_code == 403
    _clear_auth_override()


# ---------------------------------------------------------------------------
# Tests — PATCH /orders/{order_id}/status (status transitions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_transition_placed_to_preparing(client):
    """Restaurant: PLACED → PREPARING → 200."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(
        customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID, status=OrderStatus.PLACED
    )
    updated = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PREPARING,
    )

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "PREPARING"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "PREPARING"
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_transition_preparing_to_ready(client):
    """Restaurant: PREPARING → READY → 200."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PREPARING,
    )
    updated = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.READY,
    )

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "READY"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_transition_ready_to_picked_up(client):
    """Assigned courier: READY → PICKED_UP → 200."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        courier_id=COURIER_ID,
        status=OrderStatus.READY,
    )
    updated = _make_order(
        customer_id=CUSTOMER_ID,
        courier_id=COURIER_ID,
        status=OrderStatus.PICKED_UP,
    )

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "PICKED_UP"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "PICKED_UP"
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_transition_picked_up_to_delivered(client):
    """Assigned courier: PICKED_UP → DELIVERED → 200."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        courier_id=COURIER_ID,
        status=OrderStatus.PICKED_UP,
    )
    updated = _make_order(
        customer_id=CUSTOMER_ID,
        courier_id=COURIER_ID,
        status=OrderStatus.DELIVERED,
    )

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "DELIVERED"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "DELIVERED"
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_cancel_by_customer(client):
    """Customer can cancel their own order."""
    _override_auth(CUSTOMER_ID, "customer")
    order = _make_order(customer_id=CUSTOMER_ID, status=OrderStatus.PLACED)
    updated = _make_order(customer_id=CUSTOMER_ID, status=OrderStatus.CANCELLED)

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "CANCELLED"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_cancel_by_restaurant(client):
    """Restaurant can cancel their own order."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PREPARING,
    )
    updated = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.CANCELLED,
    )

    with (
        patch(
            "app.services.order_service.OrderService.get_order",
            new_callable=AsyncMock,
            return_value=order,
        ),
        patch(
            "app.services.order_service.OrderService.update_status",
            new_callable=AsyncMock,
            return_value=updated,
        ),
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "CANCELLED"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"
    _clear_auth_override()


# ---------------------------------------------------------------------------
# Tests — Invalid transitions / RBAC denials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_invalid_transition_409(client):
    """Invalid transition (PLACED → DELIVERED) → 409."""
    _override_auth(RESTAURANT_ID, "restaurant")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PLACED,
    )

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "DELIVERED"},
        )

    assert resp.status_code == 409
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_wrong_restaurant_403(client):
    """Restaurant trying to transition another restaurant's order → 403."""
    _override_auth(uuid.uuid4(), "restaurant")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PLACED,
    )

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "PREPARING"},
        )

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_unassigned_courier_403(client):
    """Courier not assigned to order → 403 on PICKED_UP."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(
        customer_id=CUSTOMER_ID,
        courier_id=uuid.uuid4(),  # different courier
        status=OrderStatus.READY,
    )

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "PICKED_UP"},
        )

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_cancel_by_courier_403(client):
    """Courier cannot cancel an order → 403."""
    _override_auth(COURIER_ID, "courier")
    order = _make_order(customer_id=CUSTOMER_ID, status=OrderStatus.PLACED)

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=order,
    ):
        resp = await client.patch(
            f"/api/orders/{order.id}/status",
            json={"status": "CANCELLED"},
        )

    assert resp.status_code == 403
    _clear_auth_override()


@pytest.mark.asyncio
async def test_status_order_not_found(client):
    """PATCH status for non-existent order → 404."""
    _override_auth(RESTAURANT_ID, "restaurant")
    fake_id = uuid.uuid4()

    with patch(
        "app.services.order_service.OrderService.get_order",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await client.patch(
            f"/api/orders/{fake_id}/status",
            json={"status": "PREPARING"},
        )

    assert resp.status_code == 404
    _clear_auth_override()


# ---------------------------------------------------------------------------
# Tests — Kafka event payload shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kafka_event_contains_required_fields():
    """Verify the Kafka event published on status change includes all required fields."""
    mock_producer = MagicMock()
    svc = OrderService(order_repo=AsyncMock(), kafka_producer=mock_producer)

    order = _make_order(
        customer_id=CUSTOMER_ID,
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.PLACED,
    )

    # Patch repo methods used by update_status
    with (
        patch.object(
            svc.order_repo, "find_by_id", new_callable=AsyncMock, return_value=order
        ),
        patch.object(
            svc.order_repo,
            "update_status",
            new_callable=AsyncMock,
            return_value=_make_order(
                customer_id=CUSTOMER_ID,
                restaurant_id=RESTAURANT_ID,
                status=OrderStatus.PREPARING,
            ),
        ),
    ):
        await svc.update_status(order.id, OrderStatus.PREPARING)

    # Verify produce was called
    mock_producer.produce.assert_called_once()
    call_kwargs = mock_producer.produce.call_args[1]

    import json

    event = json.loads(call_kwargs["value"])

    # API contract required fields
    assert "order_id" in event
    assert "customer_id" in event
    assert "restaurant_id" in event
    assert "courier_id" in event
    assert "previous_status" in event
    assert "new_status" in event
    assert "timestamp" in event

    assert event["previous_status"] == "PLACED"
    assert event["new_status"] == "PREPARING"
    assert event["restaurant_id"] == str(RESTAURANT_ID)
    assert event["courier_id"] is None
    assert call_kwargs["topic"] == "order-status-changed"
    assert call_kwargs["key"] == str(order.id)


# ---------------------------------------------------------------------------
# Tests — Domain model: VALID_TRANSITIONS
# ---------------------------------------------------------------------------

from app.models.domain import VALID_TRANSITIONS


def test_valid_transitions_placed():
    assert VALID_TRANSITIONS[OrderStatus.PLACED] == {
        OrderStatus.PREPARING,
        OrderStatus.CANCELLED,
    }


def test_valid_transitions_preparing():
    assert VALID_TRANSITIONS[OrderStatus.PREPARING] == {
        OrderStatus.READY,
        OrderStatus.CANCELLED,
    }


def test_valid_transitions_ready():
    assert VALID_TRANSITIONS[OrderStatus.READY] == {
        OrderStatus.PICKED_UP,
        OrderStatus.CANCELLED,
    }


def test_valid_transitions_picked_up():
    assert VALID_TRANSITIONS[OrderStatus.PICKED_UP] == {
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    }


def test_valid_transitions_delivered():
    assert VALID_TRANSITIONS[OrderStatus.DELIVERED] == set()


def test_valid_transitions_cancelled():
    assert VALID_TRANSITIONS[OrderStatus.CANCELLED] == set()


# ---------------------------------------------------------------------------
# Tests — Health endpoint with instance identification (#29)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_includes_instance(client):
    """Health endpoint returns instance identifier for load-balancer debugging."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "order-service"
    assert "instance" in body


# ---------------------------------------------------------------------------
# Tests — Config settings
# ---------------------------------------------------------------------------


from app.config import settings


def test_config_has_service_instance():
    """Settings include a service_instance field."""
    assert hasattr(settings, "service_instance")
    assert isinstance(settings.service_instance, str)
    assert len(settings.service_instance) > 0


def test_config_postgres_url_matches_docker_compose():
    """Default postgres_url points to the docker-compose postgres-orders service."""
    assert "postgres-orders" in settings.postgres_url
    assert "/orders" in settings.postgres_url


def test_config_redis_url_uses_db_0():
    """Default redis_url uses DB 0, matching docker-compose."""
    assert settings.redis_url.endswith("/0")


def test_config_kafka_topic_is_correct():
    """Kafka topic matches api-contracts.md."""
    assert settings.kafka_topic == "order-status-changed"


def test_config_routing_service_url_default():
    """Default routing_service_url points to the routing container."""
    assert "routing" in settings.routing_service_url


# ---------------------------------------------------------------------------
# Tests — RoutingClient
# ---------------------------------------------------------------------------

import pytest
import httpx

from app.services.routing_client import RoutingClient


@pytest.mark.asyncio
async def test_routing_client_returns_courier_id_on_200():
    """RoutingClient.assign_courier returns uuid on 200 response."""
    order_id = uuid.uuid4()
    restaurant_id = uuid.uuid4()
    courier_id = uuid.uuid4()

    async def handler(request):
        return httpx.Response(
            200,
            json={
                "order_id": str(order_id),
                "courier_id": str(courier_id),
                "estimated_minutes": 5,
            },
        )

    transport = httpx.MockTransport(handler)
    client = RoutingClient(base_url="http://routing:8000")
    # Patch AsyncClient to use mock transport
    with patch("app.services.routing_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                post=AsyncMock(
                    return_value=MagicMock(
                        status_code=200,
                        json=lambda: {
                            "order_id": str(order_id),
                            "courier_id": str(courier_id),
                            "estimated_minutes": 5,
                        },
                    )
                )
            )
        )
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await client.assign_courier(order_id, restaurant_id)

    assert result == courier_id


@pytest.mark.asyncio
async def test_routing_client_returns_none_on_404():
    """RoutingClient.assign_courier returns None when no couriers available."""
    with patch("app.services.routing_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                post=AsyncMock(
                    return_value=MagicMock(
                        status_code=404,
                        json=lambda: {"detail": "No couriers available"},
                    )
                )
            )
        )
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client = RoutingClient(base_url="http://routing:8000")
        result = await client.assign_courier(uuid.uuid4(), uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_routing_client_returns_none_on_exception():
    """RoutingClient.assign_courier swallows exceptions and returns None."""
    with patch("app.services.routing_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client = RoutingClient(base_url="http://routing:8000")
        result = await client.assign_courier(uuid.uuid4(), uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# Tests — OrderService: courier assignment on PREPARING transition
# ---------------------------------------------------------------------------


def _make_order_service(routing_client=None) -> OrderService:
    """Helper: create an OrderService with pre-configured AsyncMock repo and Kafka."""
    repo = AsyncMock()
    return OrderService(
        order_repo=repo,
        kafka_producer=MagicMock(),
        routing_client=routing_client,
    )


@pytest.mark.asyncio
async def test_update_status_to_preparing_assigns_courier():
    """When transitioning to PREPARING, courier_id is fetched and saved."""
    courier_id = uuid.uuid4()
    mock_routing = AsyncMock(spec=RoutingClient)
    mock_routing.assign_courier = AsyncMock(return_value=courier_id)

    order = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID, status=OrderStatus.PLACED)
    updated = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID, status=OrderStatus.PREPARING)

    svc = _make_order_service(routing_client=mock_routing)
    svc.order_repo.find_by_id = AsyncMock(return_value=order)
    svc.order_repo.update_status = AsyncMock(return_value=updated)
    svc.order_repo.update_courier = AsyncMock()

    result = await svc.update_status(order.id, OrderStatus.PREPARING)

    mock_routing.assign_courier.assert_called_once_with(
        order_id=order.id, restaurant_id=RESTAURANT_ID
    )
    svc.order_repo.update_courier.assert_called_once_with(order.id, courier_id)
    assert result.courier_id == courier_id


@pytest.mark.asyncio
async def test_update_status_to_preparing_no_courier_available():
    """When routing returns None (no couriers), order still transitions — courier_id stays null."""
    mock_routing = AsyncMock(spec=RoutingClient)
    mock_routing.assign_courier = AsyncMock(return_value=None)

    order = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID, status=OrderStatus.PLACED)
    updated = _make_order(customer_id=CUSTOMER_ID, restaurant_id=RESTAURANT_ID, status=OrderStatus.PREPARING)

    svc = _make_order_service(routing_client=mock_routing)
    svc.order_repo.find_by_id = AsyncMock(return_value=order)
    svc.order_repo.update_status = AsyncMock(return_value=updated)
    svc.order_repo.update_courier = AsyncMock()

    result = await svc.update_status(order.id, OrderStatus.PREPARING)

    svc.order_repo.update_courier.assert_not_called()
    assert result.courier_id is None


@pytest.mark.asyncio
async def test_update_status_no_routing_client_skips_assignment():
    """Without a routing client, status transition works but no courier is assigned."""
    order = _make_order(status=OrderStatus.PLACED)
    updated = _make_order(status=OrderStatus.PREPARING)

    svc = _make_order_service(routing_client=None)
    svc.order_repo.find_by_id = AsyncMock(return_value=order)
    svc.order_repo.update_status = AsyncMock(return_value=updated)

    result = await svc.update_status(order.id, OrderStatus.PREPARING)

    assert result.status == OrderStatus.PREPARING
    assert result.courier_id is None


@pytest.mark.asyncio
async def test_routing_not_called_for_non_preparing_transitions():
    """Routing client is NOT called for transitions other than PLACED → PREPARING."""
    mock_routing = AsyncMock(spec=RoutingClient)
    mock_routing.assign_courier = AsyncMock()

    order = _make_order(status=OrderStatus.PREPARING)
    updated = _make_order(status=OrderStatus.READY)

    svc = _make_order_service(routing_client=mock_routing)
    svc.order_repo.find_by_id = AsyncMock(return_value=order)
    svc.order_repo.update_status = AsyncMock(return_value=updated)

    await svc.update_status(order.id, OrderStatus.READY)

    mock_routing.assign_courier.assert_not_called()
