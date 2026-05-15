import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette import status

from app.api.v1 import menu_items, restaurants
from app.db.mongo import connect, disconnect
from app.exceptions import WriteUnavailableError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    logger.info("MongoDB connected")
    yield
    await disconnect()
    logger.info("MongoDB disconnected")


app = FastAPI(title="MealMate Restaurant Catalog Service", version="0.1.0", lifespan=lifespan)

app.include_router(restaurants.router, prefix="/api/restaurants", tags=["restaurants"])
app.include_router(menu_items.router, prefix="/api/v1/menu-items", tags=["menu-items"])


@app.exception_handler(WriteUnavailableError)
async def write_unavailable_handler(request, exc: WriteUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database write unavailable"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
