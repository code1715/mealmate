from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import User, UserRole
from app.models.user import User as UserORM


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> User | None:
        stmt = select(UserORM).where(UserORM.email == email)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return User(
            id=row.id,
            email=row.email,
            role=row.role,
            hashed_password=row.hashed_password,
            created_at=row.created_at,
        )

    async def create(self, email: str, hashed_password: str, role: UserRole) -> User:
        row = UserORM(email=email, hashed_password=hashed_password, role=role)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return User(
            id=row.id,
            email=row.email,
            role=row.role,
            hashed_password=row.hashed_password,
            created_at=row.created_at,
        )
