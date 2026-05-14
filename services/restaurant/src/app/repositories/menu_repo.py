import pymongo.errors
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.exceptions import WriteUnavailableError
from app.models.domain import MenuItem


class MenuRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["menu_items"]

    async def find_by_restaurant(self, restaurant_id: str) -> list[MenuItem]:
        cursor = self._col.find({"restaurant_id": restaurant_id, "is_available": True})
        return [self._to_domain(doc) async for doc in cursor]

    async def create(self, restaurant_id: str, name: str, description: str, price: float) -> MenuItem:
        doc = {
            "restaurant_id": restaurant_id,
            "name": name,
            "description": description,
            "price": price,
            "is_available": True,
        }
        try:
            result = await self._col.insert_one(doc)
        except pymongo.errors.PyMongoError as exc:
            raise WriteUnavailableError(str(exc)) from exc
        doc["_id"] = result.inserted_id
        return self._to_domain(doc)

    async def set_availability(self, item_id: str, is_available: bool) -> MenuItem | None:
        try:
            oid = ObjectId(item_id)
        except Exception:
            return None
        try:
            result = await self._col.find_one_and_update(
                {"_id": oid},
                {"$set": {"is_available": is_available}},
                return_document=True,
            )
        except pymongo.errors.PyMongoError as exc:
            raise WriteUnavailableError(str(exc)) from exc
        return self._to_domain(result) if result else None

    def _to_domain(self, doc: dict) -> MenuItem:
        return MenuItem(
            id=str(doc["_id"]),
            restaurant_id=doc["restaurant_id"],
            name=doc["name"],
            description=doc["description"],
            price=doc["price"],
            is_available=doc.get("is_available", True),
        )
