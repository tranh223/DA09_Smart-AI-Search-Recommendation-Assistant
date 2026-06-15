"""Trích xuất slots từ RecommendInput cho embedding search."""

from __future__ import annotations

from typing import Any

from app.recommendation.models import RecommendInput

_TRIP_TYPE_TAG_MAP = {
    "Gia đình có trẻ nhỏ": "Gia đình có trẻ nhỏ",
    "Gia đình có thanh thiếu niên": "Gia đình có thanh thiếu niên",
    "Cặp đôi": "Cặp đôi",
    "Khách đi công tác": "Khách đi công tác",
    "Khách du lịch một mình": "Khách du lịch một mình",
    "Nhóm du khách": "Nhóm du khách",
    "family": "Gia đình có trẻ nhỏ",
    "couple": "Cặp đôi",
    "solo": "Khách du lịch một mình",
    "business": "Khách đi công tác",
    "group": "Nhóm du khách",
}


def extract_slots(inp: RecommendInput) -> dict[str, Any]:
    """Chuyển RecommendInput → flat slot dict (city, price, tags, ...)."""
    sc = inp.session_context
    ap = inp.profile

    city = sc.destination or ""

    max_price: float | None = None
    if sc.session_price_range and sc.session_price_range.max:
        max_price = float(sc.session_price_range.max)
    elif ap.long_term_price_range and ap.long_term_price_range.max:
        max_price = float(ap.long_term_price_range.max)

    nearby_place = sc.nearby_place or ""

    tags: list[str] = []
    for trip_key in ap.long_term_trip_types:
        mapped = _TRIP_TYPE_TAG_MAP.get(trip_key, trip_key)
        if mapped not in tags:
            tags.append(mapped)
    for habit_tag in ap.long_term_preference_habits:
        if habit_tag not in tags:
            tags.append(habit_tag)
    for view_tag in ap.long_term_room_views:
        if view_tag not in tags:
            tags.append(view_tag)
    for amenity_tag in ap.long_term_amenities:
        if amenity_tag not in tags:
            tags.append(amenity_tag)

    return {
        "city": city,
        "max_price": max_price,
        "nearby_place": nearby_place if nearby_place else None,
        "tags": tags if tags else None,
        "limit": inp.limit_per_source,
    }
