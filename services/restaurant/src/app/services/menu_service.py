from app.models.domain import MenuItem
from app.repositories.menu_repo import MenuRepository


class MenuService:
    def __init__(self, repo: MenuRepository) -> None:
        self._repo = repo

    async def get_menu(self, restaurant_id: str) -> list[MenuItem]:
        return await self._repo.find_by_restaurant(restaurant_id)

    async def add_item(self, restaurant_id: str, name: str, description: str, price: float) -> MenuItem:
        return await self._repo.create(restaurant_id, name, description, price)

    async def set_item_availability(self, item_id: str, is_available: bool) -> MenuItem | None:
        return await self._repo.set_availability(item_id, is_available)
