import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.orders import router as orders_router
from app.db.models import Base
from app.dependencies import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")
    yield


app = FastAPI(title="MealMate Order Service", version="0.1.0", lifespan=lifespan)
app.include_router(orders_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "order-service"}
