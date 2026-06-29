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


_ACCOMMODATION_TYPE_MAP = {
    "khách sạn": "hotel",
    "resort": "resort",
    "villa": "villa",
    "biệt thự": "villa",
    "biệt thự nghỉ dưỡng": "villa",
    "homestay": "homestay",
    "nhà dân": "homestay",
    "căn hộ": "homestay",
    "căn hộ dịch vụ": "homestay",
    "toàn bộ căn nhà": "homestay",
    "hostel": "hostel",
    "nhà nghỉ": "hostel",
    "nhà khách / nhà nghỉ b&b": "hostel",
    "giường và bữa sáng": "hostel",
    "nhà nghỉ ven đường": "hostel",
    "bungalow": "bungalow",
    "boutique": "boutique",
    
    # English taxonomies already mapped to themselves
    "hotel": "hotel",
    "resort": "resort",
    "villa": "villa",
    "homestay": "homestay",
    "hostel": "hostel",
    "bungalow": "bungalow",
    "boutique": "boutique",
}

_PROPERTY_TYPE_MAP = {
    "hotel": "hotel",
    "nonhotel": "homestay",
    "singleroom": "hostel",
}


def _extract_preference_habits(hotel: dict[str, Any]) -> list[str]:
    habits = []
    if hotel.get("is_luxury"):
        habits.append("luxury")
        
    amenities = {str(a).lower() for a in hotel.get("amenities", [])}
    
    # luxury indicators
    if "spa" in amenities or "massage" in amenities or "bể bơi vô cực" in amenities:
        habits.append("luxury")
        
    # comfort indicators
    comfort_keywords = {"dịch vụ phòng", "giặt là", "giặt khô", "đưa đón", "bữa sáng", "dịch vụ ủi", "dọn phòng"}
    if any(k in a for a in amenities for k in comfort_keywords):
        habits.append("comfort")
        
    # quiet indicators
    if "cách âm" in amenities or "phòng cách âm" in amenities or "yên tĩnh" in amenities:
        habits.append("quiet")
        
    # privacy indicators
    if "nhận/trả phòng riêng" in amenities or "nhận trả phòng riêng" in amenities or hotel.get("hotel_type") in {"villa", "homestay"}:
        habits.append("privacy")
        
    # safety indicators
    safety_keywords = {"bảo vệ 24 giờ", "cctv", "két an toàn", "tính năng an toàn", "bảo vệ"}
    if any(k in a for a in amenities for k in safety_keywords):
        habits.append("safety")
        
    # vibrant indicators
    vibrant_keywords = {"bar", "quán bar", "hộp đêm", "karaoke", "sòng bạc", "casino"}
    if any(k in a for a in amenities for k in vibrant_keywords):
        habits.append("vibrant")
        
    return list(set(habits))


def _external_hotel_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    
    # 1. IDs and basic mapping
    if "item_id" not in normalized:
        normalized["item_id"] = _first_present(normalized, "id", "hotel_id")
    normalized.setdefault("item_type", "hotel")
    _set_if_present(normalized, "keyword_score", "base_score", "search_score", "pre_rank_score")
    _set_if_present(normalized, "destination", "city", "address")
    
    # Normalize hotel type to lowercase English taxonomy
    raw_acc = normalized.get("accommodation_type")
    raw_prop = normalized.get("property_type")
    mapped_type = None
    if raw_acc:
        mapped_type = _ACCOMMODATION_TYPE_MAP.get(str(raw_acc).strip().lower())
    if not mapped_type and raw_prop:
        mapped_type = _PROPERTY_TYPE_MAP.get(str(raw_prop).strip().lower())
    normalized["hotel_type"] = mapped_type or "hotel"
    
    # 2. Ratings and Sentiments
    if "rating" not in normalized:
        normalized["rating"] = _review_to_rating(_first_present(normalized, "star_rating"))
    if "review_sentiment" not in normalized:
        normalized["review_sentiment"] = _review_to_sentiment(_first_present(normalized, "review_score"))
        
    normalized["is_luxury"] = bool(normalized.get("is_luxury"))
    normalized["review_count"] = int(normalized.get("review_count") or 0)

    # 3. Amenities
    if "amenities" in candidate and isinstance(candidate["amenities"], list):
        extracted_amenities = []
        for am in candidate["amenities"]:
            if isinstance(am, dict) and "name" in am:
                extracted_amenities.append(am["name"])
            elif isinstance(am, str):
                extracted_amenities.append(am)
        normalized["amenities"] = _dedupe_strings(extracted_amenities)

    # 4. Rooms (price, views)
    if "rooms" in candidate and isinstance(candidate["rooms"], list):
        prices = []
        room_views = []
        for room in candidate["rooms"]:
            if isinstance(room, dict):
                p = to_float(room.get("price"))
                if p is not None:
                    prices.append(p)
                if room.get("room_view"):
                    room_views.append(room["room_view"])
        if prices:
            normalized["price_min"] = min(prices)
            normalized["price_max"] = max(prices)
        if room_views:
            normalized["room_views"] = _dedupe_strings(normalized.get("room_views", []), room_views)
    
    # 5. Suitability -> Tags
    suitability_tags = []
    if "suitability" in candidate and isinstance(candidate["suitability"], list):
        for suit in candidate["suitability"]:
            if isinstance(suit, dict) and "suitable_for_tag" in suit:
                suitability_tags.append(suit["suitable_for_tag"])
    if "suitable_for" in candidate and isinstance(candidate["suitable_for"], list):
        for tag in candidate["suitable_for"]:
            if isinstance(tag, str):
                suitability_tags.append(tag)
    if suitability_tags:
        normalized["tags"] = _dedupe_strings(normalized.get("tags", []), suitability_tags)
        
    # Extract actual preference habits from traits & amenities (luxury, quiet, privacy, comfort, safety, vibrant)
    habits = _extract_preference_habits(normalized)
    normalized["preference_habits"] = _dedupe_strings(normalized.get("preference_habits", []), habits)

    # 6. Nearby Places
    if "nearby_places" in candidate and isinstance(candidate["nearby_places"], list):
        places = []
        for pl in candidate["nearby_places"]:
            if isinstance(pl, dict) and "name" in pl:
                places.append(pl["name"])
            elif isinstance(pl, str):
                places.append(pl)
        normalized["nearby_places"] = _dedupe_strings(places)

    if "available" not in normalized:
        normalized["available"] = True
    if "available_rooms" not in normalized:
        normalized["available_rooms"] = len(as_list(candidate.get("rooms")))

    return normalized


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = _external_hotel_candidate(candidate)
    if "item_id" not in normalized and "hotel_id" in normalized:
        normalized["item_id"] = normalized["hotel_id"]
    hotel = CandidateHotel.model_validate(normalized)
    return hotel.model_dump()


def normalize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_candidate(candidate) for candidate in candidates]
