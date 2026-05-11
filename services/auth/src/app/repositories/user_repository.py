"""User Repository — Data access layer for Postgres.

All database interactions go through this module.
No business logic lives here — only CRUD operations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    """Manages user persistence in Postgres."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> dict | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "role": user.role.value if user.role else None,
            "created_at": user.created_at,
        }

    async def create(self, email: str, hashed_password: str, role: UserRole) -> dict:
        user = User(
            email=email,
            hashed_password=hashed_password,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role.value if user.role else None,
            "created_at": user.created_at,
        }
