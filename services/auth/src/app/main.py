from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # Startup
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
