from fastapi import APIRouter, Depends, status

from app.db.mongo import get_db
from app.models.menu_item import MenuItemCreate, MenuItemResponse
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
