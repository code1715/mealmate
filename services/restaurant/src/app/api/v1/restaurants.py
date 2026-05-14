from fastapi import APIRouter, Depends, HTTPException, status

from app.db.mongo import get_db
from app.models.menu_item import MenuItemResponse
from app.models.restaurant import RestaurantCreate, RestaurantListResponse, RestaurantResponse
from app.repositories.menu_repo import MenuRepository
from app.repositories.restaurant_repo import RestaurantRepository
from app.services.menu_service import MenuService
from app.services.restaurant_service import RestaurantService

router = APIRouter()


def get_restaurant_service() -> RestaurantService:
    return RestaurantService(RestaurantRepository(get_db()))


def get_menu_service() -> MenuService:
    return MenuService(MenuRepository(get_db()))


@router.get("/", response_model=RestaurantListResponse)
async def list_restaurants(service: RestaurantService = Depends(get_restaurant_service)):
    items = await service.list_restaurants()
    return RestaurantListResponse(
        items=[
            RestaurantResponse(
                id=r.id, name=r.name, address=r.address,
                cuisine=r.cuisine, rating=r.rating, is_active=r.is_active,
            )
            for r in items
        ],
        total=len(items),
    )


@router.post("/", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    body: RestaurantCreate,
    service: RestaurantService = Depends(get_restaurant_service),
):
    restaurant = await service.create_restaurant(
        name=body.name, address=body.address, cuisine=body.cuisine, rating=body.rating
    )
    return RestaurantResponse(
        id=restaurant.id, name=restaurant.name, address=restaurant.address,
        cuisine=restaurant.cuisine, rating=restaurant.rating, is_active=restaurant.is_active,
    )


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(
    restaurant_id: str,
    service: RestaurantService = Depends(get_restaurant_service),
):
    restaurant = await service.get_restaurant(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return RestaurantResponse(
        id=restaurant.id, name=restaurant.name, address=restaurant.address,
        cuisine=restaurant.cuisine, rating=restaurant.rating, is_active=restaurant.is_active,
    )


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemResponse])
async def get_restaurant_menu(
    restaurant_id: str,
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    menu_service: MenuService = Depends(get_menu_service),
):
    restaurant = await restaurant_service.get_restaurant(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    items = await menu_service.get_menu(restaurant_id)
    return [
        MenuItemResponse(
            id=item.id, restaurant_id=item.restaurant_id, name=item.name,
            description=item.description, price=item.price, is_available=item.is_available,
        )
        for item in items
    ]
