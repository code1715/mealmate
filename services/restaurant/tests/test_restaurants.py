import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.exceptions import WriteUnavailableError
from app.models.domain import MenuItem, Restaurant


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
                response = await client.get("/api/v1/restaurants")
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
                response = await client.get("/api/v1/restaurants")
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
                    "/api/v1/restaurants",
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
                    "/api/v1/restaurants",
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
                    "/api/v1/restaurants",
                    json={"name": "Bad", "address": "1 St", "cuisine": "Any", "rating": 10.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_restaurant_returns_200(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.get_restaurant = AsyncMock(return_value=sample_restaurant)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/64b8f1c2e4b0a1234567890a")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "64b8f1c2e4b0a1234567890a"
    assert data["name"] == "Burger Palace"
    assert data["cuisine"] == "American"
    assert data["rating"] == 4.5
    assert data["is_active"] is True
    assert "_id" not in data


@pytest.mark.anyio
async def test_get_restaurant_menu_returns_200(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service

    sample_items = [
        MenuItem(
            id="64b8f1c2e4b0a1234567890b",
            restaurant_id="64b8f1c2e4b0a1234567890a",
            name="Cheeseburger",
            description="Classic beef patty",
            price=9.99,
            is_available=True,
        ),
        MenuItem(
            id="64b8f1c2e4b0a1234567890c",
            restaurant_id="64b8f1c2e4b0a1234567890a",
            name="Fries",
            description="Crispy fries",
            price=3.99,
            is_available=True,
        ),
    ]

    mock_restaurant_service = AsyncMock()
    mock_restaurant_service.get_restaurant = AsyncMock(return_value=sample_restaurant)
    mock_menu_service = AsyncMock()
    mock_menu_service.get_menu = AsyncMock(return_value=sample_items)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_restaurant_service
    app.dependency_overrides[get_menu_service] = lambda: mock_menu_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert all(item["is_available"] is True for item in items)
    assert items[0]["name"] == "Cheeseburger"
    assert items[0]["price"] == 9.99
    assert "_id" not in items[0]


@pytest.mark.anyio
async def test_get_restaurant_menu_invalid_id_returns_404():
    from app.main import app
    from app.api.v1.restaurants import get_menu_service, get_restaurant_service

    mock_restaurant_service = AsyncMock()
    mock_restaurant_service.get_restaurant = AsyncMock(return_value=None)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_restaurant_service
    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/restaurants/not-a-valid-objectid/menu")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Restaurant not found"


# --- POST /{restaurant_id}/menu ---

def _auth_override(role: str = "restaurant"):
    async def _dep():
        return {"user_id": "some-user", "role": role}
    return _dep


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_missing_auth():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service

    app.dependency_overrides[get_restaurant_service] = lambda: AsyncMock()
    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu",
                    json={"name": "Burger", "description": "Tasty", "price": 5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_invalid_token():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service
    from app.dependencies.auth import require_restaurant_role

    async def mock_auth_invalid():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    app.dependency_overrides[get_restaurant_service] = lambda: AsyncMock()
    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    app.dependency_overrides[require_restaurant_role] = mock_auth_invalid
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu",
                    headers={"Authorization": "Bearer bad-token"},
                    json={"name": "Burger", "description": "Tasty", "price": 5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_wrong_role():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service
    from app.dependencies.auth import require_restaurant_role

    async def mock_auth_wrong_role():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    app.dependency_overrides[get_restaurant_service] = lambda: AsyncMock()
    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    app.dependency_overrides[require_restaurant_role] = mock_auth_wrong_role
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu",
                    headers={"Authorization": "Bearer customer-token"},
                    json={"name": "Burger", "description": "Tasty", "price": 5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_returns_201(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service
    from app.dependencies.auth import require_restaurant_role

    sample_item = MenuItem(
        id="64b8f1c2e4b0a1234567890b",
        restaurant_id="64b8f1c2e4b0a1234567890a",
        name="Cheeseburger",
        description="Classic beef patty",
        price=9.99,
        is_available=True,
    )

    mock_restaurant_service = AsyncMock()
    mock_restaurant_service.get_restaurant = AsyncMock(return_value=sample_restaurant)
    mock_menu_service = AsyncMock()
    mock_menu_service.add_item = AsyncMock(return_value=sample_item)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_restaurant_service
    app.dependency_overrides[get_menu_service] = lambda: mock_menu_service
    app.dependency_overrides[require_restaurant_role] = _auth_override("restaurant")
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu",
                    headers={"Authorization": "Bearer valid-token"},
                    json={"name": "Cheeseburger", "description": "Classic beef patty", "price": 9.99},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Cheeseburger"
    assert data["price"] == 9.99
    assert data["restaurant_id"] == "64b8f1c2e4b0a1234567890a"
    assert "_id" not in data


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_not_found():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service
    from app.dependencies.auth import require_restaurant_role

    mock_restaurant_service = AsyncMock()
    mock_restaurant_service.get_restaurant = AsyncMock(return_value=None)

    app.dependency_overrides[get_restaurant_service] = lambda: mock_restaurant_service
    app.dependency_overrides[get_menu_service] = lambda: AsyncMock()
    app.dependency_overrides[require_restaurant_role] = _auth_override("restaurant")
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/000000000000000000000000/menu",
                    headers={"Authorization": "Bearer valid-token"},
                    json={"name": "Burger", "description": "Tasty", "price": 5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Restaurant not found"


# --- 503 on write unavailable ---

@pytest.mark.anyio
async def test_create_restaurant_returns_503_on_write_failure():
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service

    mock_service = AsyncMock()
    mock_service.create_restaurant = AsyncMock(side_effect=WriteUnavailableError("not primary"))

    app.dependency_overrides[get_restaurant_service] = lambda: mock_service
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants",
                    json={"name": "Burger Palace", "address": "10 Main St", "cuisine": "American", "rating": 4.5},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


@pytest.mark.anyio
async def test_add_menu_item_to_restaurant_returns_503_on_write_failure(sample_restaurant):
    from app.main import app
    from app.api.v1.restaurants import get_restaurant_service, get_menu_service
    from app.dependencies.auth import require_restaurant_role

    mock_restaurant_service = AsyncMock()
    mock_restaurant_service.get_restaurant = AsyncMock(return_value=sample_restaurant)
    mock_menu_service = AsyncMock()
    mock_menu_service.add_item = AsyncMock(side_effect=WriteUnavailableError("not primary"))

    app.dependency_overrides[get_restaurant_service] = lambda: mock_restaurant_service
    app.dependency_overrides[get_menu_service] = lambda: mock_menu_service
    app.dependency_overrides[require_restaurant_role] = _auth_override("restaurant")
    try:
        with patch("app.db.mongo.connect", new_callable=AsyncMock), \
             patch("app.db.mongo.disconnect", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/restaurants/64b8f1c2e4b0a1234567890a/menu",
                    headers={"Authorization": "Bearer valid-token"},
                    json={"name": "Burger", "description": "Tasty", "price": 5.0},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
