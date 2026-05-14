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
