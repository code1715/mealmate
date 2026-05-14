from app.models.domain import Restaurant
from app.repositories.restaurant_repo import RestaurantRepository


class RestaurantService:
    def __init__(self, repo: RestaurantRepository) -> None:
        self._repo = repo

    async def list_restaurants(self) -> list[Restaurant]:
        return await self._repo.find_all()

    async def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        return await self._repo.find_by_id(restaurant_id)

    async def create_restaurant(self, name: str, address: str, cuisine: str, rating: float) -> Restaurant:
        return await self._repo.create(name, address, cuisine, rating)
