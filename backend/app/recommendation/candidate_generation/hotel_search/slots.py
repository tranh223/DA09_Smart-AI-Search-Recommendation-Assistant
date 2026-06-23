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
    trip_type = _pick_top_tag(ap.long_term_trip_types)
    profile_features = _collect_profile_features(inp)

    return {
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "trip_type": trip_type,
        "profile_features": profile_features if profile_features else None,
        "limit": inp.limit_per_source,
    }


def _pick_top_tag(values: dict[str, Any]) -> str | None:
    ranked = _sort_tag_items(values)
    return ranked[0][0] if ranked else None


def _collect_profile_features(inp: RecommendInput) -> list[str]:
    ap = inp.profile
    collected: list[str] = []
    seen: set[str] = set()

    for source in (
        ap.long_term_hotel_types,
        ap.long_term_room_views,
        ap.long_term_amenities,
        ap.long_term_preference_habits,
    ):
        for key, _value in _sort_tag_items(source):
            normalized_key = str(key).strip()
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            collected.append(normalized_key)

    return collected[:12]


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
