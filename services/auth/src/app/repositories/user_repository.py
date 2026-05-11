"""User Repository — Data access layer for Postgres.

All database interactions go through this module.
No business logic lives here — only CRUD operations.
"""

from app.models.domain import UserRole
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    """Manages user persistence in Postgres."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> dict | None:
        # Will be implemented with SQLAlchemy queries in issue #15
        raise NotImplementedError

    async def create(self, email: str, hashed_password: str, role: UserRole) -> dict:
        # Will be implemented with SQLAlchemy queries in issue #15
        raise NotImplementedError
