from __future__ import annotations

import time
from typing import Any

import requests

from .booking_signals import compute_booking_signals
from .config import load_settings
from .explain_builder import build_reasons, build_warnings
from .llm_reranker import rerank_with_llm
from .logger import write_rerank_log
from .mock_store import MockStore
from .normalizer import normalize_candidates
from .profile_normalizer import normalize_profile
from .rule_scorer import score_candidate
from .trend_scorer import apply_trend_scores
from .utils import as_dict, clamp, normalize_text, round_score


SESSION_OPTION_KEYS = {
    "destination",
    "current_location",
    "nearby_place",
    "number_of_guests",
    "has_pet",
    "has_children",
    "check_in",
    "check_out",
    "session_trip_types",
    "session_budget_levels",
    "session_price_range",
    "session_preference_habits",
    "session_hotel_types",
    "session_room_views",
    "session_amenities",
    "session_negative_preferences",
    "boost_amenity_rich_hotels",
}


def _hotel_api_config(settings: Any, options: dict[str, Any]) -> tuple[str, str]:
    base_url = str(options.get("hotel_api_base_url") or getattr(settings, "hotel_api_base_url", "") or "").rstrip("/")
    api_key = str(options.get("hotel_api_key") or getattr(settings, "hotel_api_key", "") or "")
    return base_url, api_key


def _enrich_candidates_from_hotel_api(
    candidate_items: list[dict],
    settings: Any,
    options: dict[str, Any],
) -> tuple[list[dict], str, dict[str, Any]]:
    # Always attempt hotel API enrichment (caller no longer toggles this).
    base_url, api_key = _hotel_api_config(settings, options)
    debug: dict[str, Any] = {
        "requested": True,
        "requested_ids": [],
        "enriched_ids": [],
        "missing_ids": [],
        "errors": [],
    }
    if not base_url or not api_key:
        debug["reason"] = "hotel_api_base_url_or_key_missing"
        return candidate_items, "input_api_fallback", debug

    enriched_candidates: list[dict[str, Any]] = []
    for candidate in candidate_items:
        item_id = _candidate_id(candidate)
        if not item_id:
            enriched_candidates.append(candidate)
            continue
        debug["requested_ids"].append(item_id)
        try:
            url = f"{base_url}/api/hotels/{item_id}"
            response = requests.get(url, headers={"X-API-Key": api_key}, timeout=10)
            if response.status_code == 200:
                hotel_data = response.json() or {}
                enriched = dict(candidate)
                enriched.update(hotel_data)
                enriched["item_id"] = item_id
                enriched_candidates.append(enriched)
                debug["enriched_ids"].append(item_id)
            elif response.status_code == 404:
                debug["missing_ids"].append(item_id)
                enriched_candidates.append(candidate)
            else:
                debug["errors"].append(
                    {"item_id": item_id, "status_code": response.status_code, "body": response.text}
                )
                enriched_candidates.append(candidate)
        except Exception as error:
            debug["errors"].append({"item_id": item_id, "error": str(error)})
            enriched_candidates.append(candidate)

    return enriched_candidates, "hotel_api_enriched", debug


def _load_profile_and_bookings(
    user_id: str | None,
    user_context: dict | None,
    candidate_ids: list[str],
    settings: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str, str]:
    # Prefer provided `user_context`. Do NOT fetch from Mongo here — upstream
    # now passes full profile when available. If not provided, proceed with
    # minimal profile (None) and no bookings.
    if user_context:
        profile = user_context
        profile_source = "provided"
    elif settings.mock_mode:
        profile = MockStore(settings).get_user_context(user_id)
        profile_source = "mock"
    else:
        profile = None
        profile_source = "none"

    if settings.mock_mode:
        bookings = MockStore(settings).get_bookings(user_id, candidate_ids)
        booking_source = "mock"
    else:
        bookings = []
        booking_source = "none"

    return profile, bookings, profile_source, booking_source


def _session_context_from_options(options: dict[str, Any]) -> dict[str, Any]:
    session = dict(as_dict(options.get("session_context")))
    for key in SESSION_OPTION_KEYS:
        if key in options and options[key] is not None:
            session[key] = options[key]
    return session


def _with_input_session_context(profile: dict[str, Any] | None, user_id: str | None, options: dict[str, Any]) -> dict[str, Any]:
    merged = dict(as_dict(profile) or {"user_id": user_id})
    merged.pop("session_context", None)
    if not merged.get("user_id"):
        merged["user_id"] = user_id
    session = _session_context_from_options(options)
    if session:
        merged["session_context"] = session
    return merged


def _enrich_candidates_from_postgres(
    candidate_items: list[dict],
    settings: Any,
    options: dict[str, Any],
) -> tuple[list[dict], str, dict[str, Any]]:
    # Postgres enrichment removed; keep a no-op placeholder for backward compatibility
    return candidate_items, "input", {"requested": False}


def _candidate_id(candidate: dict[str, Any]) -> str:
    return str(candidate.get("item_id") or candidate.get("hotel_id") or candidate.get("id") or "")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        import decimal

        if isinstance(value, decimal.Decimal):
            return float(value)
    except Exception:
        pass
    return value


def _hotel_log_summary(hotel: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": hotel.get("item_id"),
        "rank": hotel.get("rank"),
        "name": hotel.get("name"),
        "city": hotel.get("city") or hotel.get("destination"),
        "hotel_type": hotel.get("accommodation_type") or hotel.get("hotel_type"),
        "price_min": hotel.get("min_price") or hotel.get("price_min"),
        "price_max": hotel.get("max_price") or hotel.get("price_max"),
        "final_score": hotel.get("final_score"),
        "base_score": hotel.get("base_score"),
        "llm_score": hotel.get("llm_score"),
    }


def _negative_matches(
    profile: dict[str, Any],
    group_name: str,
    values: list[str],
    threshold: float,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for source in ("session", "long_term"):
        negative = as_dict(as_dict(profile.get(source)).get("negative_preferences"))
        group = as_dict(negative.get(group_name))
        for value in values:
            weight = float(group.get(value, 0.0) or 0.0)
            if weight >= threshold:
                matches.append({"source": source, "value": value, "weight": round(weight, 3)})
    return matches


def _filter_debug_detail(profile: dict[str, Any], candidate: dict[str, Any], reason: str | None) -> dict[str, Any]:
    session = as_dict(profile.get("session"))
    detail: dict[str, Any] = {
        "reason": reason,
        "summary": reason or "unknown",
    }
    if reason == "destination_mismatch":
        requested = session.get("destination")
        actual = candidate.get("destination")
        detail.update(
            {
                "summary": "Hotel destination does not match requested session destination.",
                "requested_destination": requested,
                "hotel_destination": actual,
                "normalized_requested_destination": normalize_text(requested),
                "normalized_hotel_destination": normalize_text(actual),
            }
        )
    elif reason == "not_available":
        detail.update(
            {
                "summary": "Hotel is not available.",
                "available": candidate.get("available"),
                "available_rooms": candidate.get("available_rooms"),
            }
        )
    elif reason == "price_far_outside":
        detail.update(
            {
                "summary": "Hotel price range is too far outside the requested session budget.",
                "session_price_range": session.get("price_range"),
                "hotel_price_range": {
                    "min": candidate.get("price_min"),
                    "max": candidate.get("price_max"),
                    "currency": candidate.get("currency"),
                },
            }
        )
    elif reason == "strong_avoid_hotel_type":
        detail.update(
            {
                "summary": "Hotel type strongly matches a negative preference.",
                "hotel_type": candidate.get("hotel_type"),
                "matches": _negative_matches(profile, "avoid_hotel_types", [candidate.get("hotel_type")], 0.85),
            }
        )
    elif reason == "strong_avoid_amenity":
        amenities = [str(item) for item in candidate.get("amenities", [])]
        detail.update(
            {
                "summary": "Hotel amenities strongly match negative preferences.",
                "hotel_amenities": amenities,
                "matches": _negative_matches(profile, "avoid_amenities", amenities, 0.90),
            }
        )
    elif reason == "strong_avoid_preference_habit":
        habits = [str(item) for item in candidate.get("preference_habits", [])]
        detail.update(
            {
                "summary": "Hotel preference habits strongly match negative preferences.",
                "hotel_preference_habits": habits,
                "matches": _negative_matches(profile, "avoid_preference_habits", habits, 0.90),
            }
        )
    elif reason == "strong_avoid_location":
        locations = [str(item) for item in candidate.get("location_tags", [])]
        detail.update(
            {
                "summary": "Hotel location tags strongly match negative location preferences.",
                "hotel_location_tags": locations,
                "matches": _negative_matches(profile, "avoid_locations", locations, 0.90),
            }
        )
    return detail


def _hotel_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    score = 0.0
    if left.get("hotel_type") and left.get("hotel_type") == right.get("hotel_type"):
        score += 0.4

    left_nearby = set(left.get("nearby_places", []))
    right_nearby = set(right.get("nearby_places", []))
    if left_nearby and right_nearby:
        shared = left_nearby.intersection(right_nearby)
        total = left_nearby.union(right_nearby)
        score += 0.3 * (len(shared) / max(len(total), 1))

    left_tags = set(left.get("tags", []))
    right_tags = set(right.get("tags", []))
    if left_tags and right_tags:
        shared = left_tags.intersection(right_tags)
        total = left_tags.union(right_tags)
        score += 0.3 * (len(shared) / max(len(total), 1))

    return clamp(score)


def _apply_diversity_rerank(rankings: list[dict[str, Any]], strength: float) -> list[dict[str, Any]]:
    if len(rankings) <= 1 or strength <= 0:
        return rankings

    remaining = list(rankings)
    selected: list[dict[str, Any]] = []
    reordered: list[dict[str, Any]] = []

    while remaining:
        if not selected:
            chosen = max(remaining, key=lambda item: item["final_score"])
        else:
            for item in remaining:
                similarity = max(_hotel_similarity(item, existing) for existing in selected)
                item["diversity_score"] = item["final_score"] - strength * similarity
            chosen = max(remaining, key=lambda item: (item["diversity_score"], item["final_score"]))
        remaining.remove(chosen)
        chosen.pop("diversity_score", None)
        reordered.append(chosen)

    return reordered


def _bool_option(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def rerank(
    user_id: str | None,
    user_context: dict | None,
    candidate_items: list[dict],
    query: str | None,
    options: dict | None,
) -> dict:
    started = time.perf_counter()
    settings = load_settings()
    opts = as_dict(options)
    top_k = int(opts.get("top_k", 5) or 5)
    llm_top_n = int(opts.get("llm_top_n", 20) or 20)
    use_llm = _bool_option(opts.get("use_llm_rerank"), False)
    llm_dry_run = _bool_option(opts.get("llm_dry_run"), False)
    return_debug = _bool_option(opts.get("return_debug"), False)
    base_weight = float(opts.get("base_score_weight", 0.7) or 0.7)
    llm_weight = float(opts.get("llm_score_weight", 0.3) or 0.3)
    weight_total = max(base_weight + llm_weight, 0.0001)
    base_weight = base_weight / weight_total
    llm_weight = llm_weight / weight_total
    diversify_recommendations = _bool_option(opts.get("diversify_recommendations"), False)
    diversity_strength = float(opts.get("diversity_strength", 0.15) or 0.15)
    # control whether to write pretty debug JSON files (may be large)
    debug_write = _bool_option(opts.get("write_debug_file"), True)

    # Enrich candidates from hotel API only. Postgres enrichment removed.
    candidate_items, api_source, api_debug = _enrich_candidates_from_hotel_api(candidate_items or [], settings, opts)
    candidate_source = api_source
    candidate_enrichment_debug = {"hotel_api": api_debug}
    raw_candidates_by_id = {_candidate_id(candidate): _json_safe(candidate) for candidate in candidate_items}
    candidates = normalize_candidates(candidate_items)
    candidate_ids = [item["item_id"] for item in candidates]
    raw_profile, bookings, profile_source, booking_source = _load_profile_and_bookings(
        user_id, user_context, candidate_ids, settings
    )
    profile = normalize_profile(_with_input_session_context(raw_profile, user_id, opts))
    signals = apply_trend_scores(compute_booking_signals(bookings, candidates, user_id))

    scored: list[dict[str, Any]] = []
    scored_debug_items: list[dict[str, Any]] = []
    filtered = 0
    filtered_items: list[dict[str, Any]] = []
    for candidate in candidates:
        signal = signals.get(candidate["item_id"], {})
        result = score_candidate(profile, candidate, signal)
        if result.filtered:
            filtered += 1
            filtered_items.append(
                {
                    "item_id": candidate["item_id"],
                    "name": candidate.get("name"),
                    "reason": result.filter_reason,
                    "detail": _filter_debug_detail(profile, candidate, result.filter_reason),
                    "destination": candidate.get("destination"),
                    "hotel_type": candidate.get("hotel_type"),
                    "price_min": candidate.get("price_min"),
                    "price_max": candidate.get("price_max"),
                    "available": candidate.get("available"),
                }
            )
            continue
        item = dict(candidate)
        item["booking_signals"] = signal
        item["base_score"] = round_score(result.base_score)
        item["feature_scores"] = result.feature_scores
        item["negative_penalty"] = result.negative_penalty
        scored.append(item)
        scored_debug_items.append(
            {
                "item_id": item["item_id"],
                "name": item.get("name"),
                "base_score": item["base_score"],
                "feature_scores": item["feature_scores"],
                "feature_contributions": result.feature_contributions,
                "raw_base_before_penalty": round(sum(result.feature_contributions.values()), 6) if hasattr(result, "feature_contributions") else None,
                "base_after_penalty": round(sum(result.feature_contributions.values()) - result.negative_penalty, 6) if hasattr(result, "feature_contributions") else None,
                "negative_penalty": item["negative_penalty"],
                "booking_signals": signal,
                "price_range": {
                    "min": item.get("price_min"),
                    "max": item.get("price_max"),
                    "currency": item.get("currency"),
                },
                "destination": item.get("destination"),
                "hotel_type": item.get("hotel_type"),
                "amenities": item.get("amenities"),
                "room_views": item.get("room_views"),
                "preference_habits": item.get("preference_habits"),
                "tags": item.get("tags"),
                "nearby_places": item.get("nearby_places"),
            }
        )

    scored.sort(key=lambda item: item["base_score"], reverse=True)
    scored_debug_items.sort(key=lambda item: item["base_score"], reverse=True)
    llm_candidates = scored[:llm_top_n]
    llm_results, llm_source, llm_fallback, llm_debug = rerank_with_llm(
        settings, query, profile, llm_candidates, use_llm, llm_dry_run
    )

    ranked: list[dict[str, Any]] = []
    for item in scored:
        llm_payload = llm_results.get(item["item_id"])
        llm_score = llm_payload["llm_score"] if llm_payload else None
        if llm_score is None:
            final_score = item["base_score"]
        else:
            final_score = clamp(base_weight * item["base_score"] + llm_weight * llm_score)
        ranked.append(
            {
                "item_id": item["item_id"],
                "name": item.get("name"),
                "final_score": round_score(final_score),
                "base_score": round_score(item["base_score"]),
                "llm_score": None if llm_score is None else round_score(llm_score),
                "feature_scores": item["feature_scores"],
                "negative_penalty": item["negative_penalty"],
                "reasons": build_reasons(item, profile, as_dict(llm_payload).get("reasons")),
                "warnings": build_warnings(item, as_dict(llm_payload).get("warnings")),
            }
        )

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    if diversify_recommendations:
        ranked = _apply_diversity_rerank(ranked, diversity_strength)
    ranked = ranked[:top_k]
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index

    ranked_hotels: list[dict[str, Any]] = []
    for item in ranked:
        hotel = dict(as_dict(raw_candidates_by_id.get(item["item_id"])))
        hotel.update(
            {
                "item_id": item["item_id"],
                "rank": item["rank"],
                "final_score": item["final_score"],
                "base_score": item["base_score"],
                "llm_score": item["llm_score"],
                "feature_scores": item["feature_scores"],
                "negative_penalty": item["negative_penalty"],
                "reasons": item["reasons"],
                "warnings": item["warnings"],
            }
        )
        ranked_hotels.append(hotel)

    fallback_used = llm_fallback or (use_llm and not llm_results)
    debug = {
        "total_candidates": len(candidates),
        "after_hard_filter": len(scored),
        "filtered_count": filtered,
        "filtered_items": filtered_items,
        "scored_items": scored_debug_items,
        "normalized_session": profile.get("session"),
        "normalized_long_term": profile.get("long_term"),
        # include raw and normalized candidate data for debugging
        "raw_candidates": raw_candidates_by_id,
        "normalized_candidates": candidates,
        "booking_signals_all": signals,
        "llm_used": bool(llm_results),
        "fallback_used": fallback_used,
        "mock_mode": settings.mock_mode,
        "candidate_source": candidate_source,
        "candidate_enrichment_debug": candidate_enrichment_debug,
        "diversified": diversify_recommendations,
        "diversity_strength": diversity_strength,
        "profile_source": profile_source,
        "booking_source": booking_source,
        "llm_source": llm_source,
        "llm_debug": llm_debug,
        "llm_candidates": [c["item_id"] for c in llm_candidates],
        "llm_results": llm_results,
    }
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    write_rerank_log(
        settings,
        {
            "user_id": user_id,
            "query": query,
            "total_candidates": len(candidates),
            "after_hard_filter": len(scored),
            "filtered_count": filtered,
            "filtered_items": filtered_items,
            "scored_items": scored_debug_items,
            "llm_used": bool(llm_results),
            "llm_source": llm_source,
            "llm_debug": llm_debug,
            "fallback_used": fallback_used,
            "candidate_source": candidate_source,
            "candidate_enrichment_debug": candidate_enrichment_debug,
            # include detailed buckets
            "raw_candidates": raw_candidates_by_id,
            "normalized_candidates": candidates,
            "booking_signals_all": signals,
            "llm_candidates": [c["item_id"] for c in llm_candidates],
            "llm_results": llm_results,
            "final_ranked_hotel_ids": [item["item_id"] for item in ranked],
            "ranked_hotel_summaries": [_hotel_log_summary(item) for item in ranked_hotels],
            "feature_scores": {item["item_id"]: item["feature_scores"] for item in ranked},
            "feature_contributions": {item["item_id"]: item.get("feature_contributions") for item in ranked},
            "trend_score": {item["item_id"]: item["feature_scores"].get("trend", 0.0) for item in ranked},
            "normalized_profile_summary": {
                "user_id": profile.get("user_id"),
                "session": profile.get("session"),
                "long_term_top_hotel_types": profile.get("long_term", {}).get("hotel_types"),
            },
            "latency_ms": latency_ms,
        },
        write_debug_file=debug_write,
    )

    output = {"ranked_items": ranked, "ranked_hotels": ranked_hotels}
    if return_debug:
        output["debug"] = debug
    return output
