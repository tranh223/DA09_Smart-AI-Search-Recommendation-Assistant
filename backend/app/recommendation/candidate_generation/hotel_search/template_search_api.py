"""Hotel search adapter that calls the external search API."""

from __future__ import annotations

import logging
import json
import os
from typing import Any

import httpx

from app.recommendation.candidate_generation.hotel_search.slots import extract_slots
from app.recommendation.models import CandidateHotel, RecommendInput
from app.recommendation.trace import RecommendTrace

logger = logging.getLogger(__name__)

DEFAULT_HOTEL_SEARCH_API_URL = os.getenv(
    "HOTEL_SEARCH_API_URL",
    "https://search-api-760679907616.asia-southeast1.run.app/search",
)
DEFAULT_HOTEL_SEARCH_TIMEOUT_SECONDS = float(
    os.getenv("HOTEL_SEARCH_API_TIMEOUT_SECONDS", "20") or "20"
)


def _build_query_text(slots: dict[str, Any]) -> str:
    parts: list[str] = []

    city = slots.get("city")
    if city:
        check_in = slots.get("check_in")
        check_out = slots.get("check_out")
        if check_in and check_out:
            parts.append(f"Tôi sắp đi {city} từ ngày {check_in} đến ngày {check_out}.")
        elif check_in:
            parts.append(f"Tôi sắp đi {city} từ ngày {check_in}.")
        else:
            parts.append(f"Tôi sắp đi {city}.")

    trip_type = slots.get("trip_type")
    if trip_type:
        parts.append(f"Tôi muốn khách sạn phù hợp cho {trip_type}.")

    traveler_type = _normalize_text_items(slots.get("traveler_type"))
    if traveler_type:
        parts.append(f"Phong cách du lịch của tôi là {_join_items(traveler_type)}.")

    budget_levels = _normalize_text_items(slots.get("budget_levels"))
    if budget_levels:
        parts.append(f"Mức ngân sách ưu tiên là {_join_items(budget_levels)}.")

    hotel_types = _normalize_text_items(slots.get("hotel_types"))
    if hotel_types:
        parts.append(f"Tôi ưu tiên loại hình lưu trú như {_join_items(hotel_types)}.")

    room_views = _normalize_text_items(slots.get("room_views"))
    if room_views:
        parts.append(f"Tôi muốn phòng có hướng nhìn như {_join_items(room_views)}.")

    amenities = _normalize_text_items(slots.get("amenities"))
    if amenities:
        parts.append(f"Tôi muốn khách sạn có tiện ích như {_join_items(amenities)}.")

    preference_habits = _normalize_text_items(slots.get("preference_habits"))
    if preference_habits:
        parts.append(f"Tôi muốn khách sạn có đặc điểm như {_join_items(preference_habits)}.")

    profile_features = slots.get("profile_features") or []
    if profile_features and not any((hotel_types, room_views, amenities, preference_habits)):
        parts.append(
            "Tôi muốn khách sạn có các tiện ích và đặc điểm như "
            + _join_items(_normalize_text_items(profile_features)[:12])
            + "."
        )

    return " ".join(parts).strip()


def _normalize_text_items(values: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _join_items(values: list[str]) -> str:
    return ", ".join(values)


def build_search_query_template(inp: RecommendInput) -> str:
    """Build the external search API query template from current recommendation state."""
    return _build_query_text(extract_slots(inp))


def _search_hotels_via_api(
    *,
    query_text: str,
    top_k: int,
) -> list[dict[str, Any]]:
    payload = {
        "query": query_text,
        "filters": {},
        "top_k": top_k,
    }
    logger.info("[TemplateSearchAPI] Search API request payload=%s", payload)
    raw_payload = json.dumps(payload, ensure_ascii=False)
    headers = {"Content-Type": "application/json"}
    with httpx.Client(timeout=DEFAULT_HOTEL_SEARCH_TIMEOUT_SECONDS) as client:
        response = client.post(
            DEFAULT_HOTEL_SEARCH_API_URL,
            headers=headers,
            content=raw_payload,
        )
        response.raise_for_status()
        data = response.json()
    return _extract_result_items(data)


def _extract_result_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "items", "hotels"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "hotels"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _coerce_hotel_id(hit: dict[str, Any]) -> int | None:
    for key in ("hotel_id", "id", "hotelId"):
        value = hit.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _coerce_hotel_name(hit: dict[str, Any]) -> str | None:
    for key in ("hotel_name", "name", "hotelName", "title"):
        value = hit.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _coerce_score(hit: dict[str, Any]) -> float:
    for key in ("score", "search_score", "similarity", "retrieval_score"):
        value = hit.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _coerce_city(hit: dict[str, Any]) -> str | None:
    for key in ("city_name", "city", "destination"):
        value = hit.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _coerce_tags(hit: dict[str, Any]) -> list[Any]:
    tags = hit.get("tags")
    return tags if isinstance(tags, list) else []


def _hits_to_candidates(hits: list[dict[str, Any]]) -> list[CandidateHotel]:
    candidates: list[CandidateHotel] = []
    for hit in hits:
        hotel_id = _coerce_hotel_id(hit)
        if hotel_id is None:
            continue

        tag_names = [str(t.get("tag_id", "")).split("::", 1)[-1] for t in _coerce_tags(hit) if isinstance(t, dict)]
        city_name = _coerce_city(hit)
        score = _coerce_score(hit)

        candidates.append(
            CandidateHotel(
                hotel_id=hotel_id,
                hotel_name=_coerce_hotel_name(hit),
                source="template_search_api",
                score=score,
                matched_paths=[f"Tag({name})" for name in tag_names[:5] if name],
                reason=f"search_api match ({score:.3f}) | {city_name or ''}",
                metadata={
                    "strategy": "external_search_api",
                    "city": city_name,
                    "tags": _coerce_tags(hit),
                    "retrieval": "search_api",
                    "raw_hit": hit,
                },
            )
        )
    return candidates


def get_template_search_api_candidates(
    inp: RecommendInput,
    trace: RecommendTrace | None = None,
) -> list[CandidateHotel]:
    slots = extract_slots(inp)
    city = slots.get("city") or ""

    if trace and trace.enabled:
        trace.step("slots extracted from profile + session", slots)

    if not city:
        if trace and trace.enabled:
            trace.info("Missing city -> skip template_search_api")
        logger.info("[TemplateSearchAPI] No city -> skip.")
        return []

    query_text = (inp.search_query_template or "").strip()
    if not query_text:
        query_text = _build_query_text(slots)
    if not query_text:
        if trace and trace.enabled:
            trace.info("Empty query template -> skip template_search_api")
        logger.info("[TemplateSearchAPI] Empty query template -> skip.")
        return []

    try:
        hits = _search_hotels_via_api(
            query_text=query_text,
            top_k=inp.limit_per_source,
        )
        if trace and trace.enabled:
            trace.step(
                "Search API",
                {
                    "endpoint": DEFAULT_HOTEL_SEARCH_API_URL,
                    "query_text": query_text,
                    "hits": len(hits),
                    "city": city,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TemplateSearchAPI] Search API error: %s", exc)
        if trace and trace.enabled:
            trace.info(f"Search API error: {exc}")
        return []

    candidates = _hits_to_candidates(hits)
    logger.info(
        "[TemplateSearchAPI] Returned %d candidates at %s via search API.",
        len(candidates),
        city,
    )
    return candidates
