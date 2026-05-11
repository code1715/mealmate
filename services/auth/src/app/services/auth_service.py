import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.domain import UserRole
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, user_repo, token_repo):
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def register(self, email: str, password: str, role: UserRole):
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ValueError("Email already registered")
        hashed = pwd_context.hash(password)
        return await self.user_repo.create(email=email, hashed_password=hashed, role=role)

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repo.find_by_email(email)
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user.id),
            "role": user.role.value,
            "jti": jti,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        await self.token_repo.store(jti=jti, user_id=str(user.id), ttl=settings.jwt_expire_minutes * 60)
        return token

    async def logout(self, token: str) -> None:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            jti = payload.get("jti")
            if jti:
                await self.token_repo.delete(jti)
        except JWTError:
            pass  # already-expired or malformed token — logout is a no-op

    async def validate_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except JWTError:
            raise ValueError("Invalid or expired token")

        jti = payload.get("jti")
        if not await self.token_repo.exists(jti):
            raise ValueError("Token has been invalidated")

        return {"user_id": payload["sub"], "role": payload["role"]}
