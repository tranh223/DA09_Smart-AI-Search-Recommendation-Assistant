from __future__ import annotations

from typing import Any

from .schemas import CandidateHotel
from .utils import as_list, string_list, to_float


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _dedupe_strings(*values: Any) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        for item in string_list(value):
            if item not in seen:
                seen.add(item)
                items.append(item)
    return items


def _review_to_rating(value: Any) -> float | None:
    score = to_float(value, None)
    if score is None:
        return None
    if score > 5:
        score = score / 2
    return max(0.0, min(score, 5.0))


def _review_to_sentiment(value: Any) -> float | None:
    score = to_float(value, None)
    if score is None:
        return None
    if score <= 5:
        return round(max(0.0, min(score / 5, 1.0)), 3)
    return round(max(0.0, min(score / 10, 1.0)), 3)


def _set_if_present(payload: dict[str, Any], target: str, *sources: str, default: Any = None) -> None:
    if target in payload:
        return
    value = _first_present(payload, *sources)
    if value is not None:
        payload[target] = value
    elif default is not None:
        payload[target] = default


def _postgres_hotel_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    if "item_id" not in normalized:
        normalized["item_id"] = _first_present(normalized, "hotel_id", "id")
    normalized.setdefault("item_type", "hotel")
    _set_if_present(normalized, "keyword_score", "search_score", "retrieval_score", "semantic_score", "keyword_score")
    _set_if_present(normalized, "destination", "city", "destination_city")
    _set_if_present(normalized, "hotel_type", "accommodation_type", "hotel_type")
    _set_if_present(normalized, "price_min", "min_price", "room_price_min")
    _set_if_present(normalized, "price_max", "max_price", "room_price_max", "price")
    normalized.setdefault("currency", "VND")
    if "rating" not in normalized:
        normalized["rating"] = _review_to_rating(_first_present(normalized, "review_score", "hotel_review_score", "star_rating"))
    if "review_sentiment" not in normalized:
        normalized["review_sentiment"] = _review_to_sentiment(_first_present(normalized, "review_score", "hotel_review_score"))
    if "available" not in normalized:
        normalized["available"] = True
    if "available_rooms" not in normalized:
        available_rooms = _first_present(normalized, "available_rooms", "room_count")
        normalized["available_rooms"] = len(as_list(normalized.get("rooms"))) if available_rooms is None else available_rooms
    if "amenities" not in normalized:
        normalized["amenities"] = _dedupe_strings(normalized.get("amenities"), normalized.get("room_amenities"))
    if "room_views" not in normalized:
        normalized["room_views"] = _dedupe_strings(normalized.get("room_views"), normalized.get("room_view"))
    if "tags" not in normalized:
        normalized["tags"] = _dedupe_strings(normalized.get("suitable_for"), normalized.get("policyNotes"), normalized.get("activity_titles"))
    if "preference_habits" not in normalized:
        normalized["preference_habits"] = []
    if "nearby_places" not in normalized:
        normalized["nearby_places"] = _dedupe_strings(normalized.get("nearby_places"), normalized.get("nearby_place_names"))
    return normalized


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = _postgres_hotel_candidate(candidate)
    if "item_id" not in normalized and "hotel_id" in normalized:
        normalized["item_id"] = normalized["hotel_id"]
    hotel = CandidateHotel.model_validate(normalized)
    return hotel.model_dump()


def normalize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_candidate(candidate) for candidate in candidates]
