from app.api.v1.auth import router as auth_router
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(auth_router)
