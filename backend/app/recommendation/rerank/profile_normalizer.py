from __future__ import annotations

from typing import Any

from .utils import as_dict, clamp, to_float, to_str_id


def normalize_count_group(group: Any) -> dict[str, float]:
    if not isinstance(group, dict):
        return {}
    counts: dict[str, float] = {}
    for key, payload in group.items():
        count = to_float(as_dict(payload).get("count"), 0.0)
        counts[str(key)] = max(0.0, count or 0.0)
    max_count = max(counts.values(), default=0.0)
    if max_count <= 0:
        return {key: 0.0 for key in counts}
    return {key: round(clamp(value / max_count), 3) for key, value in counts.items()}


def _negative_groups(raw: Any) -> dict[str, dict[str, float]]:
    negative = as_dict(raw)
    return {
        "avoid_hotel_types": normalize_count_group(negative.get("avoid_hotel_types")),
        "avoid_amenities": normalize_count_group(negative.get("avoid_amenities")),
        "avoid_preference_habits": normalize_count_group(negative.get("avoid_preference_habits")),
        "avoid_nearby_places": normalize_count_group(negative.get("avoid_nearby_places")),
        "avoid_locations": normalize_count_group(negative.get("avoid_locations")),
    }


def _hotel_click_ids(raw: Any) -> list[str]:
    click_ids: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        value = item.get("hotel_id") if isinstance(item, dict) else item
        if value is not None:
            click_ids.append(to_str_id(value))
    return click_ids


def normalize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    raw = as_dict(profile)
    session = as_dict(raw.get("session_context"))
    long_term = as_dict(raw.get("long_term_profile"))
    clicks = as_dict(long_term.get("recommendation_clicks"))
    hotel_clicks = _hotel_click_ids(clicks.get("hotel", []))

    return {
        "user_id": raw.get("user_id"),
        "session": {
            "destination": session.get("destination"),
            "nearby_place": session.get("nearby_place"),
            "number_of_guests": session.get("number_of_guests"),
            "has_children": session.get("has_children"),
            "price_range": as_dict(session.get("session_price_range")),
            "trip_types": normalize_count_group(session.get("session_trip_types")),
            "budget_levels": normalize_count_group(session.get("session_budget_levels")),
            "preference_habits": normalize_count_group(session.get("session_preference_habits")),
            "hotel_types": normalize_count_group(session.get("session_hotel_types")),
            "room_views": normalize_count_group(session.get("session_room_views")),
            "amenities": normalize_count_group(session.get("session_amenities")),
            "negative_preferences": _negative_groups(session.get("session_negative_preferences")),
            "boost_amenity_rich_hotels": bool(session.get("boost_amenity_rich_hotels")),
        },
        "long_term": {
            "hotel_types": normalize_count_group(long_term.get("long_term_hotel_types")),
            "trip_types": normalize_count_group(long_term.get("long_term_trip_types")),
            "budget_levels": normalize_count_group(long_term.get("long_term_budget_levels")),
            "preference_habits": normalize_count_group(long_term.get("long_term_preference_habits")),
            "room_views": normalize_count_group(long_term.get("long_term_room_views")),
            "amenities": normalize_count_group(long_term.get("long_term_amenities")),
            "recommendation_clicks": {"hotel": hotel_clicks},
            "negative_preferences": _negative_groups(long_term.get("long_term_negative_preferences")),
        },
    }
