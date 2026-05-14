import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.models.domain import Restaurant


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_restaurant():
    return Restaurant(
        id="64b8f1c2e4b0a1234567890a",
        name="Burger Palace",
        address="10 Main St",
        cuisine="American",
        rating=4.5,
        is_active=True,
    )


@pytest.mark.anyio
async def test_list_restaurants_returns_empty():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.list_restaurants = AsyncMock(return_value=[])

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.anyio
async def test_get_restaurant_not_found():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.get_restaurant = AsyncMock(return_value=None)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/000000000000000000000000")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Restaurant not found"


@pytest.mark.anyio
async def test_list_restaurants_returns_data(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.list_restaurants = AsyncMock(return_value=[sample_restaurant])

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Burger Palace"
    assert data["items"][0]["cuisine"] == "American"
    assert data["items"][0]["rating"] == 4.5


@pytest.mark.anyio
async def test_create_restaurant_returns_201(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.create_restaurant = AsyncMock(return_value=sample_restaurant)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/",
                    json={"name": "Burger Palace", "address": "10 Main St", "cuisine": "American", "rating": 4.5},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Burger Palace"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.anyio
async def test_create_restaurant_rejects_missing_fields():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    app.dependency_overrides[get_restaurant_service] = lambda: AsyncMock()
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/",
                    json={"name": "Incomplete"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_restaurant_rejects_invalid_rating():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    app.dependency_overrides[get_restaurant_service] = lambda: AsyncMock()
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/",
                    json={"name": "Bad", "address": "1 St", "cuisine": "Any", "rating": 10.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
