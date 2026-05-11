"""Auth route handlers — Web layer.

These handlers deal only with HTTP concerns: parsing requests,
calling the service layer, and formatting responses.
No business logic or database calls belong here.
"""

from app.dependencies import get_db, get_redis
from app.models.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ValidateResponse,
)
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> AuthService:
    user_repo = UserRepository(db)
    token_repo = TokenRepository(redis)
    return AuthService(user_repo=user_repo, token_repo=token_repo)


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: RegisterRequest, service: AuthService = Depends(get_auth_service)
):
    try:
        user = await service.register(
            email=body.email, password=body.password, role=body.role
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return user


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        token = await service.login(email=body.email, password=body.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return LoginResponse(access_token=token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    authorization: str = "",
    service: AuthService = Depends(get_auth_service),
):
    token = authorization.removeprefix("Bearer ").strip()
    if token:
        await service.logout(token)
    return MessageResponse(message="Logged out")


@router.get("/validate", response_model=ValidateResponse)
async def validate(
    authorization: str = "", service: AuthService = Depends(get_auth_service)
):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )
    try:
        data = await service.validate_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return ValidateResponse(**data)
