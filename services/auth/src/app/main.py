import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.dependencies import engine
from app.models.user import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")
    yield


app = FastAPI(title="MealMate Auth Service", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/auth")


@app.get("/health")
async def health():
    return {"status": "ok"}
