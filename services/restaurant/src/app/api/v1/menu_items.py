from fastapi import APIRouter, Depends, HTTPException, status

from app.db.mongo import get_db
from app.dependencies.auth import require_restaurant_role
from app.models.menu_item import MenuItemAvailabilityUpdate, MenuItemCreate, MenuItemResponse
from app.repositories.menu_repo import MenuRepository
from app.services.menu_service import MenuService

router = APIRouter()


def get_menu_service() -> MenuService:
    return MenuService(MenuRepository(get_db()))


@router.post("/", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def add_menu_item(
    restaurant_id: str,
    body: MenuItemCreate,
    service: MenuService = Depends(get_menu_service),
):
    item = await service.add_item(restaurant_id, body.name, body.description, body.price)
    return MenuItemResponse(
        id=item.id, restaurant_id=item.restaurant_id, name=item.name,
        description=item.description, price=item.price, is_available=item.is_available,
    )


@router.patch("/{item_id}/availability", response_model=MenuItemResponse)
async def set_item_availability(
    item_id: str,
    body: MenuItemAvailabilityUpdate,
    service: MenuService = Depends(get_menu_service),
    _: dict = Depends(require_restaurant_role),
):
    item = await service.set_item_availability(item_id, body.is_available)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    return MenuItemResponse(
        id=item.id, restaurant_id=item.restaurant_id, name=item.name,
        description=item.description, price=item.price, is_available=item.is_available,
    )
