import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.models.domain import MenuItem


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_item():
    return MenuItem(
        id="64b8f1c2e4b0a1234567890b",
        restaurant_id="64b8f1c2e4b0a1234567890a",
        name="Cheeseburger",
        description="Classic beef patty with cheese",
        price=9.99,
        is_available=True,
    )


@pytest.mark.anyio
async def test_add_menu_item_returns_201(sample_item):
    from app.main import app
    from app.api.v1.menu_items import get_menu_service

    mock_service = AsyncMock()
    mock_service.add_item = AsyncMock(return_value=sample_item)

    app.dependency_overrides[get_menu_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/menu-items/",
                    params={"restaurant_id": "64b8f1c2e4b0a1234567890a"},
                    json={"name": "Cheeseburger", "description": "Classic beef patty with cheese", "price": 9.99},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Cheeseburger"
    assert data["price"] == 9.99
    assert data["restaurant_id"] == "64b8f1c2e4b0a1234567890a"


@pytest.mark.anyio
async def test_add_menu_item_rejects_negative_price():
    from app.main import app
    from app.api.v1.menu_items import get_menu_service

    mock_service = AsyncMock()

    app.dependency_overrides[get_menu_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/menu-items/",
                    params={"restaurant_id": "64b8f1c2e4b0a1234567890a"},
                    json={"name": "Bad item", "description": "Should fail", "price": -5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


# --- PATCH /{item_id}/availability ---

@pytest.mark.anyio
async def test_set_availability_returns_updated_item(sample_item):
    from app.main import app
    from app.api.v1.menu_items import get_menu_service
    from app.dependencies.auth import require_restaurant_role

    unavailable = MenuItem(
        id=sample_item.id,
        restaurant_id=sample_item.restaurant_id,
        name=sample_item.name,
        description=sample_item.description,
        price=sample_item.price,
        is_available=False,
    )

    mock_service = AsyncMock()
    mock_service.set_item_availability = AsyncMock(return_value=unavailable)

    async def mock_auth():
        return {"user_id": "u1", "role": "restaurant"}

    app.dependency_overrides[get_menu_service] = lambda: mock_service
    app.dependency_overrides[require_restaurant_role] = mock_auth
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/menu-items/{sample_item.id}/availability",
                    json={"is_available": False},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["is_available"] is False
    assert data["id"] == sample_item.id


@pytest.mark.anyio
async def test_set_availability_not_found():
    from app.main import app
    from app.api.v1.menu_items import get_menu_service
    from app.dependencies.auth import require_restaurant_role

    mock_service = AsyncMock()
    mock_service.set_item_availability = AsyncMock(return_value=None)

    async def mock_auth():
        return {"user_id": "u1", "role": "restaurant"}

    app.dependency_overrides[get_menu_service] = lambda: mock_service
    app.dependency_overrides[require_restaurant_role] = mock_auth
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/menu-items/000000000000000000000000/availability",
                    json={"is_available": False},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Menu item not found"


@pytest.mark.anyio
async def test_set_availability_requires_restaurant_role():
    from app.main import app
    from app.api.v1.menu_items import get_menu_service
    from app.dependencies.auth import require_restaurant_role

    async def mock_auth_forbidden():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    app.dependency_overrides[require_restaurant_role] = mock_auth_forbidden
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.patch(
                    "/api/v1/menu-items/64b8f1c2e4b0a1234567890b/availability",
                    headers={"Authorization": "Bearer customer-token"},
                    json={"is_available": False},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
