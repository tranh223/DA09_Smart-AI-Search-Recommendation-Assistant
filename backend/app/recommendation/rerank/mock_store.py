from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .utils import to_str_id


class MockStore:
    def __init__(self, settings: Settings) -> None:
        self.data_dir = settings.base_dir / "data"

    def _load(self, name: str) -> Any:
        return json.loads((self.data_dir / name).read_text(encoding="utf-8"))

    def get_user_profile(self, user_id: str | None) -> dict[str, Any] | None:
        payload = self._load("mock_user_profiles.json")
        profiles = payload.get("users", payload if isinstance(payload, list) else [])
        for profile in profiles:
            if profile.get("user_id") == user_id:
                return profile
        return None

    def get_user_context(self, user_id: str | None) -> dict[str, Any] | None:
        return self.get_user_profile(user_id)

    def get_candidate_hotels(self) -> list[dict[str, Any]]:
        payload = self._load("mock_candidate_hotels.json")
        return payload.get("candidate_items", payload)

    def get_bookings(self, user_id: str | None, hotel_ids: list[str]) -> list[dict[str, Any]]:
        payload = self._load("mock_bookings.json")
        bookings = payload.get("bookings", payload)
        wanted = {to_str_id(item) for item in hotel_ids}
        return [
            booking
            for booking in bookings
            if booking.get("user_id") == user_id or to_str_id(booking.get("hotel_id")) in wanted
        ]

    def get_llm_response(self) -> dict[str, Any]:
        return self._load("mock_llm_rerank_response.json")


def data_path(settings: Settings, name: str) -> Path:
    return settings.base_dir / "data" / name
