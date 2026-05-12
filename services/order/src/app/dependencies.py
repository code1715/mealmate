import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# --- Database (Postgres) ---

engine = create_async_engine(settings.postgres_url, echo=False)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for a request lifecycle."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --- Redis ---

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield the Redis client."""
    yield redis_client


# --- Auth (inter-service token validation) ---


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    role: str


async def get_current_user(authorization: str = Header(default="")) -> CurrentUser:
    """Validate JWT by calling Auth Service. Returns user_id and role."""
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.auth_service_url}/api/auth/validate",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable",
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    data = resp.json()
    return CurrentUser(
        user_id=uuid.UUID(data["user_id"]),
        role=data["role"],
    )
