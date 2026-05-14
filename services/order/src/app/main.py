import logging
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI

from app.api.orders import router as orders_router
from app.config import settings
from app.db.models import Base
from app.dependencies import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Fix: pre-create enum idempotently so two instances starting simultaneously
        # don't crash on duplicate type (see also create_type=False in models.py)
        await conn.execute(
            sa.text(
                "DO $$ BEGIN "
                "CREATE TYPE orderstatus AS ENUM ("
                "'PLACED', 'PREPARING', 'READY', 'PICKED_UP', 'DELIVERED', 'CANCELLED'); "
                "EXCEPTION WHEN duplicate_object OR unique_violation THEN NULL; END $$;"
            )
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")
    yield


app = FastAPI(title="MealMate Order Service", version="0.1.0", lifespan=lifespan)
app.include_router(orders_router, prefix="/api")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "order-service",
        "instance": settings.service_instance,
    }
