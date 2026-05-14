"""Auth Service — unit tests.

All external dependencies (Postgres, Redis) are mocked.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.models.domain import User, UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_USER = User(
    id=uuid.uuid4(),
    email="user@example.com",
    role=UserRole.customer,
    hashed_password="$2b$12$fakehashedpassword",
    created_at=datetime.now(timezone.utc),
)


def _make_user(**overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "email": "user@example.com",
        "role": UserRole.customer,
        "hashed_password": "$2b$12$fakehashedpassword",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return User(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Provide an httpx AsyncClient with mocked Postgres and Redis."""

    with (
        patch("app.dependencies.engine"),
        patch("app.dependencies.redis_client"),
        patch("app.dependencies.async_session_factory"),
    ):
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture
async def client_with_registered(client):
    """Client with a pre-registered user. Mocks AuthService.register to succeed."""
    user = _make_user()

    with patch(
        "app.services.auth_service.AuthService.register",
        new_callable=AsyncMock,
        return_value=user,
    ):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": user.email,
                "password": "secret123",
                "role": user.role.value,
            },
        )
    assert resp.status_code == 201

    # Now mock find_by_email to return this user for login attempts
    with patch(
        "app.services.auth_service.AuthService.login",
        new_callable=AsyncMock,
        return_value="fake-jwt-token",
    ):
        yield client, user


# ---------------------------------------------------------------------------
# Tests — POST /register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client):
    """Register with valid data → 201."""
    user = _make_user()

    with patch(
        "app.services.auth_service.AuthService.register",
        new_callable=AsyncMock,
        return_value=user,
    ):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "user@example.com",
                "password": "secret123",
                "role": "customer",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "customer"
    assert "id" in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Register with existing email → 409."""
    with patch(
        "app.services.auth_service.AuthService.register",
        new_callable=AsyncMock,
        side_effect=ValueError("Email already registered"),
    ):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "user@example.com",
                "password": "secret123",
                "role": "customer",
            },
        )

    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """Register with invalid email → 422."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "secret123", "role": "customer"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client):
    """Register with password < 6 chars → 422."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "short", "role": "customer"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_role(client):
    """Register with invalid role → 422."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123", "role": "admin"},
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — POST /login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client):
    """Login with correct credentials → 200 + token."""
    with patch(
        "app.services.auth_service.AuthService.login",
        new_callable=AsyncMock,
        return_value="fake-jwt-token",
    ):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "secret123"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Login with wrong password → 401."""
    with patch(
        "app.services.auth_service.AuthService.login",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid credentials"),
    ):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )

    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """Login with unregistered email → 401."""
    with patch(
        "app.services.auth_service.AuthService.login",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid credentials"),
    ):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "secret123"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields(client):
    """Login with empty body → 422."""
    resp = await client.post("/api/auth/login", json={})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — POST /logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_success(client):
    """Logout with valid token → 200."""
    with patch("app.services.auth_service.AuthService.logout", new_callable=AsyncMock):
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out"


@pytest.mark.asyncio
async def test_logout_no_token(client):
    """Logout without token → still 200 (logout is idempotent)."""
    resp = await client.post("/api/auth/logout")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(client):
    """Validate a valid token → 200 with user_id and role."""
    user = _make_user()

    with patch(
        "app.services.auth_service.AuthService.validate_token",
        new_callable=AsyncMock,
        return_value={"user_id": str(user.id), "role": user.role.value},
    ):
        resp = await client.get(
            "/api/auth/validate",
            headers={"Authorization": f"Bearer fake-jwt-token"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == str(user.id)
    assert body["role"] == "customer"


@pytest.mark.asyncio
async def test_validate_missing_token(client):
    """Validate without token → 401."""
    resp = await client.get("/api/auth/validate")

    assert resp.status_code == 401
    assert "Missing token" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_validate_expired_token(client):
    """Validate an expired JWT → 401."""
    with patch(
        "app.services.auth_service.AuthService.validate_token",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid or expired token"),
    ):
        resp = await client.get(
            "/api/auth/validate",
            headers={"Authorization": "Bearer expired-token"},
        )

    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validate_revoked_token(client):
    """Validate a token that was revoked via logout → 401."""
    with patch(
        "app.services.auth_service.AuthService.validate_token",
        new_callable=AsyncMock,
        side_effect=ValueError("Token has been invalidated"),
    ):
        resp = await client.get(
            "/api/auth/validate",
            headers={"Authorization": "Bearer revoked-token"},
        )

    assert resp.status_code == 401
    assert "invalidated" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Tests — /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    """Health endpoint returns ok."""
    resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
