import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.core.database as db_module
from app.api.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Raises neo4j.exceptions.ServiceUnavailable if Neo4j is unreachable — fail fast
    db_module.driver = db_module.init_driver()
    logger.info("Connected to Neo4j at %s", db_module.settings.neo4j_uri)
    yield
    if db_module.driver is not None:
        db_module.driver.close()
        logger.info("Neo4j driver closed")


app = FastAPI(title="routing-service", lifespan=lifespan)
app.include_router(router, prefix="/api/routing")


@app.get("/health")
def health():
    return {"status": "ok", "service": "routing-service"}
