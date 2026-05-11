import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.dependencies import engine
from app.models.user import Base

logger = logging.getLogger(__name__)


async def run_migrations() -> None:
    """Create all tables directly using SQLAlchemy metadata.

    For a project of this scope, using create_all is simpler than
    running Alembic from within the event loop. Alembic CLI can
    still be used manually for schema changes.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # Startup — ensure tables exist
    await run_migrations()
    yield
    # Shutdown


app = FastAPI(
    title="MealMate Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)

# Register API v1 routes
app.include_router(api_router, prefix="/api/auth")


@app.get("/health")
async def health():
    return {"status": "ok"}
