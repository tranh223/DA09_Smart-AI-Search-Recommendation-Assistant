from __future__ import annotations

from datetime import timedelta
from typing import Any

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ModuleNotFoundError:  # pragma: no cover - exercised by environments without pymongo.
    MongoClient = None

    class PyMongoError(Exception):
        pass

from .config import Settings
from .utils import to_str_id, utc_now


class MongoStore:
    def __init__(self, settings: Settings) -> None:
        if MongoClient is None:
            raise PyMongoError("pymongo is not installed")
        self.settings = settings
        self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[settings.mongodb_db]

    def ping(self) -> None:
        self.client.admin.command("ping")

    def get_user_profile(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        return self.db[self.settings.user_profile_collection].find_one({"user_id": user_id})

    def get_user_context(self, user_id: str | None) -> dict[str, Any] | None:
        return self.get_user_profile(user_id)

    def get_bookings(self, user_id: str | None, hotel_ids: list[str]) -> list[dict[str, Any]]:
        ids = list({to_str_id(item) for item in hotel_ids})
        numeric_ids = [int(item) for item in ids if item.isdigit()]
        since = utc_now() - timedelta(days=30)
        query = {
            "$and": [
                {"$or": [{"user_id": user_id}, {"hotel_id": {"$in": ids + numeric_ids}}]},
                {"$or": [{"booked_at": {"$gte": since.isoformat()}}, {"booking_date": {"$gte": since.isoformat()}}, {"user_id": user_id}]},
            ]
        }
        return list(self.db[self.settings.bookings_collection].find(query))

    def close(self) -> None:
        self.client.close()


def safe_mongo_store(settings: Settings) -> MongoStore | None:
    try:
        store = MongoStore(settings)
        store.ping()
        return store
    except PyMongoError:
        return None
