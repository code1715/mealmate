import pymongo.errors
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.exceptions import WriteUnavailableError
from app.models.domain import Restaurant


class RestaurantRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["restaurants"]

    async def find_all(self) -> list[Restaurant]:
        cursor = self._col.find({"is_active": True})
        return [self._to_domain(doc) async for doc in cursor]

    async def find_by_id(self, restaurant_id: str) -> Restaurant | None:
        try:
            doc = await self._col.find_one({"_id": ObjectId(restaurant_id)})
        except Exception:
            return None
        return self._to_domain(doc) if doc else None

    async def create(self, name: str, address: str, cuisine: str, rating: float) -> Restaurant:
        doc = {
            "name": name,
            "address": address,
            "cuisine": cuisine,
            "rating": rating,
            "is_active": True,
        }
        try:
            result = await self._col.insert_one(doc)
        except pymongo.errors.PyMongoError as exc:
            raise WriteUnavailableError(str(exc)) from exc
        doc["_id"] = result.inserted_id
        return self._to_domain(doc)

    def _to_domain(self, doc: dict) -> Restaurant:
        return Restaurant(
            id=str(doc["_id"]),
            name=doc["name"],
            address=doc["address"],
            cuisine=doc["cuisine"],
            rating=doc.get("rating", 0.0),
            is_active=doc.get("is_active", True),
        )
