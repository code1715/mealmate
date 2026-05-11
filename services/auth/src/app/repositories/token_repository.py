"""Token Repository — Data access layer for Redis.

All Redis interactions for JWT token management go through this module.
"""

from redis.asyncio import Redis


class TokenRepository:
    """Manages JWT token persistence in Redis."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def store(self, jti: str, user_id: str, ttl: int) -> None:
        """Store a token in Redis with TTL."""
        await self.redis.set(name=f"token:{jti}", value=user_id, ex=ttl)

    async def exists(self, jti: str) -> bool:
        """Check if a token exists in Redis."""
        return await self.redis.exists(f"token:{jti}") > 0

    async def delete(self, jti: str) -> None:
        """Delete a token from Redis (logout)."""
        await self.redis.delete(f"token:{jti}")
