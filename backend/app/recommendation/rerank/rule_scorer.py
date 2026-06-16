from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .utils import as_dict, as_list, clamp, normalize_text, normalize_weighted_maps, to_float, to_str_id, weighted_overlap


SCHEMA_TRIP_TYPES = {
    "Nhóm du khách",
    "Cặp đôi",
    "Khách du lịch một mình",
    "Gia đình có trẻ nhỏ",
    "Gia đình có thanh thiếu niên",
    "Khách đi công tác",
}
SCHEMA_PREFERENCE_HABITS = {"luxury", "comfort", "quiet", "privacy", "unique", "safety", "vibrant"}


@dataclass
class ScoreResult:
    item: dict[str, Any]
    base_score: float
    feature_scores: dict[str, float]
    feature_contributions: dict[str, float]
    negative_penalty: float
    filtered: bool = False
    filter_reason: str | None = None


def _session(profile: dict[str, Any]) -> dict[str, Any]:
    return as_dict(profile.get("session"))


def _long(profile: dict[str, Any]) -> dict[str, Any]:
    return as_dict(profile.get("long_term"))


def _neg(profile: dict[str, Any], source: str) -> dict[str, dict[str, float]]:
    return as_dict(as_dict(profile.get(source)).get("negative_preferences"))


def _schema_trip_tags(hotel: dict[str, Any]) -> set[str]:
    return {item for item in set(hotel.get("tags", [])) if item in SCHEMA_TRIP_TYPES}


def _schema_preference_habits(hotel: dict[str, Any]) -> set[str]:
    return {item for item in set(hotel.get("preference_habits", [])) if item in SCHEMA_PREFERENCE_HABITS}


def price_far_outside(profile: dict[str, Any], hotel: dict[str, Any]) -> bool:
    price_range = as_dict(_session(profile).get("price_range"))
    user_min = to_float(price_range.get("min"), None)
    user_max = to_float(price_range.get("max"), None)
    hotel_min = to_float(hotel.get("price_min"), None)
    hotel_max = to_float(hotel.get("price_max"), None)
    if user_min is None or user_max is None or hotel_min is None or hotel_max is None:
        return False
    width = max(user_max - user_min, 1.0)
    return hotel_min > user_max + width * 0.75 or hotel_max < user_min - width * 0.75


def hard_filter(profile: dict[str, Any], hotel: dict[str, Any]) -> tuple[bool, str | None]:
    session = _session(profile)
    destination = session.get("destination")
    if destination and hotel.get("destination") and normalize_text(hotel.get("destination")) != normalize_text(destination):
        return False, "destination_mismatch"
    if not bool(hotel.get("available")):
        return False, "not_available"

    hotel_type = hotel.get("hotel_type")
    amenities = set(hotel.get("amenities", []))
    habits = set(hotel.get("preference_habits", []))
    locations = set(hotel.get("location_tags", []))

    for source in ("session", "long_term"):
        negative = _neg(profile, source)
        if float(as_dict(negative.get("avoid_hotel_types")).get(hotel_type, 0.0) or 0.0) >= 0.85:
            return False, "strong_avoid_hotel_type"
        if any(float(as_dict(negative.get("avoid_amenities")).get(item, 0.0) or 0.0) >= 0.90 for item in amenities):
            return False, "strong_avoid_amenity"
        if any(float(as_dict(negative.get("avoid_preference_habits")).get(item, 0.0) or 0.0) >= 0.90 for item in habits):
            return False, "strong_avoid_preference_habit"
        if any(float(as_dict(negative.get("avoid_locations")).get(item, 0.0) or 0.0) >= 0.90 for item in locations):
            return False, "strong_avoid_location"

    if price_far_outside(profile, hotel):
        return False, "price_far_outside"
    return True, None


def budget_score(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    price_range = as_dict(_session(profile).get("price_range"))
    user_min = to_float(price_range.get("min"), None)
    user_max = to_float(price_range.get("max"), None)
    hotel_min = to_float(hotel.get("price_min"), None)
    hotel_max = to_float(hotel.get("price_max"), None)
    if user_min is None or user_max is None or hotel_min is None or hotel_max is None or user_max <= user_min:
        return 0.5
    overlap = max(0.0, min(user_max, hotel_max) - max(user_min, hotel_min))
    coverage = overlap / max(user_max - user_min, 1.0)
    hotel_center = (hotel_min + hotel_max) / 2
    user_center = (user_min + user_max) / 2
    center_score = 1 - abs(hotel_center - user_center) / max(user_max - user_min, 1.0)
    if overlap <= 0:
        distance = min(abs(hotel_min - user_max), abs(user_min - hotel_max))
        return clamp(1 - distance / max(user_max - user_min, 1.0))
    return clamp(0.65 * coverage + 0.35 * center_score)


def _blend_overlap(session_map: dict[str, float], long_map: dict[str, float], actual: set[str]) -> float:
    sw, lw = normalize_weighted_maps(session_map, long_map)
    if sw == 0 and lw == 0:
        return 0.5
    return clamp(sw * weighted_overlap(session_map, actual) + lw * weighted_overlap(long_map, actual))


def amenity_score(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    base = _blend_overlap(as_dict(_session(profile).get("amenities")), as_dict(_long(profile).get("amenities")), set(hotel.get("amenities", [])))
    if _session(profile).get("boost_amenity_rich_hotels"):
        amenities = set(hotel.get("amenities", []))
        if amenities:
            bonus = min(len(amenities) / 20.0, 0.25)
            return clamp(base + bonus)
    return base


def room_view_score(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    return _blend_overlap(as_dict(_session(profile).get("room_views")), as_dict(_long(profile).get("room_views")), set(hotel.get("room_views", [])))


def review_score(hotel: dict[str, Any]) -> float:
    rating = to_float(hotel.get("rating"), 0.0) or 0.0
    sentiment = to_float(hotel.get("review_sentiment"), 0.5) or 0.5
    return clamp(((rating - 3.0) / 2.0) * 0.7 + sentiment * 0.3)


def availability_score(hotel: dict[str, Any]) -> float:
    if not hotel.get("available"):
        return 0.0
    rooms = int(hotel.get("available_rooms") or 0)
    if rooms >= 10:
        return 1.0
    if rooms >= 5:
        return 0.85
    if rooms >= 1:
        return 0.65
    return 0.0


def personalization_score(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    session = _session(profile)
    long = _long(profile)
    hotel_type = hotel.get("hotel_type")
    trip_tags = _schema_trip_tags(hotel)
    habits = _schema_preference_habits(hotel)
    clicked = {to_str_id(item) for item in as_list(as_dict(long.get("recommendation_clicks")).get("hotel"))}

    def source_score(source: dict[str, Any]) -> float:
        score = 0.0
        total = 0.0
        hotel_types = as_dict(source.get("hotel_types"))
        if hotel_types:
            total += 1
            score += clamp(hotel_types.get(hotel_type, 0.0))
        trip_types = as_dict(source.get("trip_types"))
        if trip_types:
            total += 1
            score += weighted_overlap(trip_types, trip_tags)
        pref_habits = as_dict(source.get("preference_habits"))
        if pref_habits:
            total += 1
            score += weighted_overlap(pref_habits, habits)
        return 0.5 if total <= 0 else clamp(score / total)

    score = 0.70 * source_score(session) + 0.30 * source_score(long)
    if hotel.get("item_id") in clicked:
        score = clamp(score + 0.12)
    return score


def location_score(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    session = _session(profile)
    nearby = session.get("nearby_place")
    score = 0.45
    if nearby and nearby in set(hotel.get("nearby_places", [])):
        score += 0.30
    return clamp(score)


def negative_penalty(profile: dict[str, Any], hotel: dict[str, Any]) -> float:
    hotel_type = hotel.get("hotel_type")
    amenities = set(hotel.get("amenities", []))
    habits = set(hotel.get("preference_habits", []))
    nearby = set(hotel.get("nearby_places", []))
    locations = set(hotel.get("location_tags", []))
    penalty = 0.0
    for source, weight in (("session", 0.70), ("long_term", 0.30)):
        negative = _neg(profile, source)
        penalty += weight * float(as_dict(negative.get("avoid_hotel_types")).get(hotel_type, 0.0) or 0.0) * 0.40
        penalty += weight * max([float(as_dict(negative.get("avoid_amenities")).get(x, 0.0) or 0.0) for x in amenities] or [0]) * 0.18
        penalty += weight * max([float(as_dict(negative.get("avoid_preference_habits")).get(x, 0.0) or 0.0) for x in habits] or [0]) * 0.30
        penalty += weight * max([float(as_dict(negative.get("avoid_nearby_places")).get(x, 0.0) or 0.0) for x in nearby] or [0]) * 0.15
        penalty += weight * max([float(as_dict(negative.get("avoid_locations")).get(x, 0.0) or 0.0) for x in locations] or [0]) * 0.25
    return clamp(penalty, 0.0, 0.8)


def score_candidate(profile: dict[str, Any], hotel: dict[str, Any], trend_signal: dict[str, Any] | None = None) -> ScoreResult:
    passed, reason = hard_filter(profile, hotel)
    if not passed:
        return ScoreResult(hotel, 0.0, {}, {}, 0.0, True, reason)
    trend = clamp(as_dict(trend_signal).get("trend_score", 0.0))
    features = {
        "keyword": clamp(hotel.get("keyword_score") if hotel.get("keyword_score") is not None else 0.5),
        "budget": budget_score(profile, hotel),
        "amenity": amenity_score(profile, hotel),
        "room_view": room_view_score(profile, hotel),
        "review": review_score(hotel),
        "availability": availability_score(hotel),
        "personalization": personalization_score(profile, hotel),
        "location": location_score(profile, hotel),
        "trend": trend,
    }
    penalty = negative_penalty(profile, hotel)
    # weights used for transparency
    weights = {
        "keyword": 0.12,
        "budget": 0.09,
        "amenity": 0.20,
        "room_view": 0.09,
        "review": 0.09,
        "availability": 0.13,
        "personalization": 0.11,
        "location": 0.08,
        "trend": 0.09,
    }
    contributions: dict[str, float] = {}
    for k, v in features.items():
        w = weights.get(k, 0.0)
        contributions[k] = round(w * v, 6)

    base_before_penalty = sum(contributions.values())
    base_after_penalty = base_before_penalty - penalty
    final_base = clamp(base_after_penalty)

    return ScoreResult(
        hotel,
        round(final_base, 3),
        {key: round(clamp(value), 3) for key, value in features.items()},
        {key: float(contributions.get(key, 0.0)) for key in contributions},
        round(penalty, 3),
    )
