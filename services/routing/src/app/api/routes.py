import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from neo4j import Driver

from app.core.database import get_driver
from app.domain.models import Courier, CourierStatusUpdate, MatchRequest, MatchResult
from app.repositories.neo4j_repo import Neo4jRepository
from app.services.matching import MatchingService

router = APIRouter()


def get_repo(driver: Driver = Depends(get_driver)) -> Neo4jRepository:
    return Neo4jRepository(driver)


def get_service(repo: Neo4jRepository = Depends(get_repo)) -> MatchingService:
    return MatchingService(repo)


@router.post("/match", response_model=MatchResult)
def match_courier(
    payload: MatchRequest,
    service: MatchingService = Depends(get_service),
) -> MatchResult:
    try:
        return service.match(payload.order_id, payload.restaurant_id)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Matching not yet implemented",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/couriers/{courier_id}/status", response_model=Courier)
def update_courier_status(
    courier_id: uuid.UUID,
    payload: CourierStatusUpdate,
    service: MatchingService = Depends(get_service),
) -> Courier:
    courier = service.update_courier_status(courier_id, payload.status)
    if courier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Courier not found"
        )
    return courier
