"""Extract current-profile search context for hotel embedding search."""

from __future__ import annotations

from typing import Any

from app.recommendation.models import RecommendInput


def extract_slots(inp: RecommendInput) -> dict[str, Any]:
    """Convert RecommendInput into a compact, profile-driven search context."""
    sc = inp.session_context
    ap = inp.profile

    city = sc.destination or ""
    check_in = sc.check_in
    check_out = sc.check_out
    price_range = getattr(sc, "session_price_range", None)
    trip_type = _pick_top_tag(ap.long_term_trip_types)
    traveler_type = _collect_profile_group(_get_profile_group(ap, "traveler_type"))
    budget_levels = _collect_profile_group(_get_profile_group(ap, "long_term_budget_levels"))
    hotel_types = _collect_profile_group(_get_profile_group(ap, "long_term_hotel_types"))
    room_views = _collect_profile_group(_get_profile_group(ap, "long_term_room_views"))
    amenities = _collect_profile_group(_get_profile_group(ap, "long_term_amenities"))
    preference_habits = _collect_profile_group(_get_profile_group(ap, "long_term_preference_habits"))
    profile_features = _collect_profile_features(inp)

    return {
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "budget_min": _get_price_value(price_range, "min"),
        "budget_max": _get_price_value(price_range, "max"),
        "trip_type": trip_type,
        "traveler_type": traveler_type,
        "budget_levels": budget_levels,
        "hotel_types": hotel_types,
        "room_views": room_views,
        "amenities": amenities,
        "preference_habits": preference_habits,
        "profile_features": profile_features if profile_features else None,
        "limit": inp.limit_per_source,
    }


def _pick_top_tag(values: dict[str, Any]) -> str | None:
    ranked = _sort_tag_items(values)
    return ranked[0][0] if ranked else None


def _get_price_value(price_range: Any, field_name: str) -> float | None:
    if price_range is None:
        return None
    value = price_range.get(field_name) if isinstance(price_range, dict) else getattr(price_range, field_name, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_profile_features(inp: RecommendInput) -> list[str]:
    ap = inp.profile
    collected: list[str] = []
    seen: set[str] = set()

    for source in (
        _get_profile_group(ap, "long_term_hotel_types"),
        _get_profile_group(ap, "long_term_room_views"),
        _get_profile_group(ap, "long_term_amenities"),
        _get_profile_group(ap, "long_term_preference_habits"),
    ):
        for key, _value in _sort_tag_items(source):
            normalized_key = str(key).strip()
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            collected.append(normalized_key)

    return collected[:12]


def _get_profile_group(profile: Any, field_name: str) -> dict[str, Any]:
    value = getattr(profile, field_name, None)
    if isinstance(value, dict):
        return value
    if hasattr(profile, "model_extra") and isinstance(profile.model_extra, dict):
        extra_value = profile.model_extra.get(field_name)
        if isinstance(extra_value, dict):
            return extra_value
    return {}


def _collect_profile_group(values: dict[str, Any], *, limit: int = 8) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()
    for key, _value in _sort_tag_items(values):
        normalized_key = str(key).strip()
        if not normalized_key or normalized_key in seen:
            continue
        seen.add(normalized_key)
        collected.append(normalized_key)
        if len(collected) >= limit:
            break
    return collected


def _sort_tag_items(values: dict[str, Any]) -> list[tuple[str, Any]]:
    items = list((values or {}).items())
    return sorted(
        items,
        key=lambda item: (
            int(getattr(item[1], "count", 0) or 0),
            str(getattr(item[1], "last_interaction", "") or ""),
            str(item[0]),
        ),
        reverse=True,
    )
