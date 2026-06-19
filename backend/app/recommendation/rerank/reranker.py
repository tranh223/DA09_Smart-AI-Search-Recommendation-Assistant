from __future__ import annotations

import decimal
import logging
import time
from datetime import timedelta
from typing import Any, TypedDict

from .booking_signals import compute_booking_signals
from .config import load_settings
from .explain_builder import build_reasons, build_warnings
from .llm_reranker import rerank_with_llm
from .logger import write_rerank_log
from .normalizer import normalize_candidates
from .profile_normalizer import normalize_profile
from .rule_scorer import score_candidate
from .trend_scorer import apply_trend_scores
from .utils import as_dict, clamp, normalize_text, round_score, to_str_id, utc_now


class _ProfileLoadResult(TypedDict):
    profile: dict[str, Any] | None
    bookings: list[dict[str, Any]]
    profile_source: str
    booking_source: str
    booking_counts: dict[str, int]


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


# ── Global engine pool (one engine per DSN, reused across requests) ────────
_engines: dict[str, Any] = {}


def _get_sync_engine(dsn: str) -> Any:
    """Return (and cache) a synchronous SQLAlchemy engine for *dsn*."""
    if dsn not in _engines:
        from sqlalchemy import create_engine
        # Supabase pooler uses postgresql:// — SQLAlchemy sync dialect is fine.
        _engines[dsn] = create_engine(
            dsn,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10},
        )
        logging.getLogger(__name__).info("[Hotel DB] Created new SQLAlchemy engine for DSN host.")
    return _engines[dsn]


def _decimal_safe(val: Any) -> Any:
    """Recursively convert Decimal / date types to JSON-friendly primitives."""
    if isinstance(val, decimal.Decimal):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _decimal_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_decimal_safe(v) for v in val]
    return val


def _enrich_candidates_from_db(
    candidate_items: list[dict],
    settings: Any,
    options: dict[str, Any],
) -> tuple[list[dict], str, dict[str, Any]]:
    """Synchronous DB enrichment using SQLAlchemy ORM + eager selectinload."""
    log = logging.getLogger(__name__)
    debug: dict[str, Any] = {
        "requested": True,
        "requested_ids": [],
        "enriched_ids": [],
        "missing_ids": [],
        "errors": [],
    }

    postgres_dsn = str(
        options.get("postgres_dsn") or getattr(settings, "postgres_dsn", "") or ""
    ).strip()
    if not postgres_dsn:
        debug["reason"] = "postgres_dsn_missing"
        log.warning("[Hotel DB] POSTGRES_DSN not configured — skipping DB enrichment.")
        return candidate_items, "db_skipped", debug

    # Collect numeric hotel IDs
    hotel_ids: list[int] = []
    for candidate in candidate_items:
        item_id = _candidate_id(candidate)
        if item_id and item_id.isdigit():
            hotel_ids.append(int(item_id))
            debug["requested_ids"].append(item_id)

    if not hotel_ids:
        debug["reason"] = "no_valid_ids"
        return candidate_items, "db_skipped", debug

    try:
        from sqlalchemy.orm import Session, selectinload
        from sqlalchemy import select
        from .db_models import HotelModel

        t0 = time.perf_counter()
        engine = _get_sync_engine(postgres_dsn)
        engine_ms = (time.perf_counter() - t0) * 1000

        # Log trước khi query để biết đang fetch bao nhiêu hotel
        log.info(
            "[Hotel DB] ▶ Querying %d hotels from Supabase (engine pool: %.2f ms)",
            len(hotel_ids), engine_ms,
        )

        t1 = time.perf_counter()
        with Session(engine) as session:
            stmt = (
                select(HotelModel)
                .where(HotelModel.id.in_(hotel_ids))
                .options(
                    selectinload(HotelModel.images),
                    selectinload(HotelModel.policy),
                    selectinload(HotelModel.suitability),
                    selectinload(HotelModel.amenities),
                    selectinload(HotelModel.rooms),
                    selectinload(HotelModel.nearby_places),
                    selectinload(HotelModel.activities),
                )
            )
            result = session.execute(stmt)
            hotels = result.scalars().all()
        query_ms = (time.perf_counter() - t1) * 1000

        log.info(
            "[Hotel DB] ◀ Fetched %d/%d hotels | DB query: %.2f ms",
            len(hotels), len(hotel_ids), query_ms,
        )

        # Build id → dict map
        t2 = time.perf_counter()
        hotels_map: dict[int, dict] = {}
        for h in hotels:
            amenity_names = [am.name for am in h.amenities]
            room_prices = [float(rm.price) for rm in h.rooms if rm.price is not None]
            h_dict: dict[str, Any] = {
                "id": h.id,
                "name": h.name,
                "property_type": h.property_type,
                "accommodation_type": h.accommodation_type,
                "star_rating": _decimal_safe(h.star_rating),
                "is_luxury": h.is_luxury,
                "review_score": _decimal_safe(h.review_score),
                "review_count": h.review_count,
                "address": h.address,
                "city": h.city,
                "city_id": h.city_id,
                "area": h.area,
                "country": h.country,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "description": h.description,
                "source_url": h.source_url,
                # Flattened derived fields for normalizer
                "amenities": amenity_names,
                "price_min": min(room_prices) if room_prices else None,
                "price_max": max(room_prices) if room_prices else None,
                "images": [
                    {"url": img.url, "is_primary": img.is_primary}
                    for img in h.images
                ],
                "primary_image": h.images[0].url if h.images else None,
                "policy": (
                    {
                        "check_in_from": h.policy.check_in_from,
                        "check_out_until": h.policy.check_out_until,
                        "service_fee_pct": _decimal_safe(h.policy.service_fee_pct),
                        "child_policy": h.policy.child_policy,
                        "pet_policy": h.policy.pet_policy,
                        "deposit_required": h.policy.deposit_required,
                        "policy_notes": h.policy.policy_notes or [],
                    }
                    if h.policy else None
                ),
                "suitable_for": [
                    suit.suitable_for_tag for suit in h.suitability
                ],
                "rooms": [
                    {
                        "id": rm.id,
                        "name": rm.name,
                        "price": _decimal_safe(rm.price),
                        "room_size": rm.room_size,
                        "max_occupancy": rm.max_occupancy,
                        "bed_type": rm.bed_type,
                        "room_view": rm.room_view,
                        "room_amenities": rm.room_amenities or [],
                        "review_score": _decimal_safe(rm.review_score),
                    }
                    for rm in h.rooms
                ],
                "nearby_places": [
                    np.name for np in h.nearby_places
                ],
                "activities": [
                    {
                        "id": act.id,
                        "title": act.title,
                        "description": act.description,
                        "price_amount": _decimal_safe(act.price_amount),
                        "review_score": _decimal_safe(act.review_score),
                    }
                    for act in h.activities
                ],
            }
            hotels_map[h.id] = h_dict
        serialize_ms = (time.perf_counter() - t2) * 1000

        # Merge enriched data back into candidates
        t3 = time.perf_counter()
        enriched_candidates: list[dict] = []
        for candidate in candidate_items:
            item_id = _candidate_id(candidate)
            if item_id and item_id.isdigit():
                int_id = int(item_id)
                if int_id in hotels_map:
                    enriched = dict(candidate)
                    enriched.update(hotels_map[int_id])
                    enriched["item_id"] = str(int_id)
                    debug["enriched_ids"].append(item_id)
                    enriched_candidates.append(enriched)
                    continue
                else:
                    debug["missing_ids"].append(item_id)
            enriched_candidates.append(candidate)
        merge_ms = (time.perf_counter() - t3) * 1000

        total_ms = engine_ms + query_ms + serialize_ms + merge_ms
        log.info(
            "[Hotel DB] Enrichment done | Enriched %d/%d | Serialize: %.2f ms | Merge: %.2f ms | Total: %.2f ms",
            len(debug["enriched_ids"]), len(hotel_ids),
            serialize_ms, merge_ms, total_ms,
        )
        return enriched_candidates, "hotel_db_enriched", debug

    except Exception as exc:
        log.error(
            "[Hotel DB] Enrichment failed: %s: %s",
            type(exc).__name__, str(exc),
        )
        debug["errors"].append({"error": str(exc)})
        return candidate_items, "db_error", debug


def _load_profile_and_bookings(
    user_id: str | None,
    user_context: dict | None,
    candidate_ids: list[str],
    settings: Any,
) -> _ProfileLoadResult:
    # Prefer provided `user_context`. Do NOT fetch from Mongo here — upstream
    # now passes full profile when available. If not provided, proceed with
    # minimal profile (None) and no bookings.
    if user_context:
        profile = user_context
        profile_source = "provided"
    else:
        profile = None
        profile_source = "none"

    # Attempt to fetch recent bookings from the shared backend mongo client
    counts: dict[str, int] = {}
    bookings: list[dict[str, Any]] = []
    booking_source = "none"
    try:
        from app.db.mongo.mongo_client import get_collection

        ids = list({to_str_id(item) for item in candidate_ids})
        numeric_ids = [int(item) for item in ids if item.isdigit()]
        since = utc_now() - timedelta(days=30)
        query = {
            "$and": [
                {"hotel_id": {"$in": ids + numeric_ids}},
                {"$or": [
                    {"booked_at": {"$gte": since.isoformat()}},
                    {"booking_date": {"$gte": since.isoformat()}},
                ]},
            ]
        }
        coll = get_collection(settings.bookings_collection)
        bookings = list(coll.find(query))
        booking_source = "mongo_shared"
        for b in bookings:
            hid = to_str_id(b.get("hotel_id") or b.get("item_id"))
            counts[hid] = counts.get(hid, 0) + 1
        logging.getLogger(__name__).info(
            "Fetched %d recent bookings for candidate hotel_ids=%s; counts=%s",
            len(bookings),
            ids,
            {k: counts[k] for k in list(counts)[:10]},
        )
    except Exception:
        pass

    return _ProfileLoadResult(
        profile=profile,
        bookings=bookings,
        profile_source=profile_source,
        booking_source=booking_source,
        booking_counts=counts,
    )


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


# _enrich_candidates_from_postgres — alias kept for import compatibility
# _enrich_candidates_from_postgres = _enrich_candidates_from_db


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
    log = logging.getLogger(__name__)
    started = time.perf_counter()

    if not candidate_items:
        log.info("[Rerank] No candidates — returning empty immediately.")
        return {"ranked_items": [], "ranked_hotels": []}

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

    # ── Phase 1: DB Enrichment ───────────────────────────────────────────
    t_enrich = time.perf_counter()
    candidate_items, candidate_source, db_debug = _enrich_candidates_from_db(
        candidate_items or [], settings, opts
    )
    enrich_ms = (time.perf_counter() - t_enrich) * 1000
    log.info(
        "[Rerank] Phase 1 DB Enrichment | %.2f ms | enriched=%d/%d",
        enrich_ms,
        len(db_debug.get("enriched_ids", [])),
        len(db_debug.get("requested_ids", [])),
    )
    candidate_enrichment_debug = {"hotel_db": db_debug}

    # ── Phase 2: Normalize candidates ───────────────────────────────────
    t_norm = time.perf_counter()
    raw_candidates_by_id = {_candidate_id(c): _json_safe(c) for c in candidate_items}
    candidates = normalize_candidates(candidate_items)
    candidate_ids = [item["item_id"] for item in candidates]
    norm_ms = (time.perf_counter() - t_norm) * 1000
    log.info("[Rerank] Phase 2 Normalize | %.2f ms | %d candidates", norm_ms, len(candidates))

    # ── Phase 3: Load profile + bookings ────────────────────────────────
    t_profile = time.perf_counter()
    _loaded = _load_profile_and_bookings(user_id, user_context, candidate_ids, settings)
    raw_profile = _loaded["profile"]
    bookings = _loaded["bookings"]
    profile_source = _loaded["profile_source"]
    booking_source = _loaded["booking_source"]
    booking_counts = _loaded["booking_counts"]
    profile_ms = (time.perf_counter() - t_profile) * 1000
    log.info(
        "[Rerank] Phase 3 Profile+Bookings | %.2f ms | bookings=%d | source=%s",
        profile_ms, len(bookings), profile_source,
    )

    # ── Phase 4: Score candidates ────────────────────────────────────────
    t_score = time.perf_counter()
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
    score_ms = (time.perf_counter() - t_score) * 1000
    log.info(
        "[Rerank] Phase 4 Scoring | %.2f ms | scored=%d filtered=%d",
        score_ms, len(scored), filtered,
    )

    # ── Phase 5: LLM rerank ──────────────────────────────────────────────
    t_llm = time.perf_counter()
    llm_candidates = scored[:llm_top_n]
    llm_results, llm_source, llm_fallback, llm_debug = rerank_with_llm(
        settings, query, profile, llm_candidates, use_llm, llm_dry_run
    )
    llm_ms = (time.perf_counter() - t_llm) * 1000
    log.info("[Rerank] Phase 5 LLM | %.2f ms | source=%s used=%s", llm_ms, llm_source, bool(llm_results))

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
                "primary_image": item.get("primary_image"),
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
                "primary_image": item.get("primary_image"),
            }
        )
        ranked_hotels.append(hotel)

    # ── Phase 6: Build final ranking ─────────────────────────────────────
    t_rank = time.perf_counter()
    fallback_used = llm_fallback or (use_llm and not llm_results)
    rank_ms = (time.perf_counter() - t_rank) * 1000

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    log.info(
        "[Rerank] ✅ DONE | Total: %.2f ms | Breakdown → Enrich: %.2f ms | Norm: %.2f ms | Profile: %.2f ms | Score: %.2f ms | LLM: %.2f ms | Rank: %.2f ms",
        latency_ms, enrich_ms, norm_ms, profile_ms, score_ms, llm_ms, rank_ms,
    )

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
        "booking_fetch": {
                "count": len(bookings),
                "strategy": booking_source,
                "candidate_ids_checked": candidate_ids,
                "counts": booking_counts,
            },
        "llm_used": bool(llm_results),
        "fallback_used": fallback_used,
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
        "latency_ms": latency_ms,
        "latency_breakdown": {
            "enrich_db_ms": round(enrich_ms, 2),
            "normalize_ms": round(norm_ms, 2),
            "profile_load_ms": round(profile_ms, 2),
            "scoring_ms": round(score_ms, 2),
            "llm_ms": round(llm_ms, 2),
            "rank_ms": round(rank_ms, 2),
        },
    }
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
            "raw_candidates": raw_candidates_by_id,
            "normalized_candidates": candidates,
            "booking_signals_all": signals,
            "booking_fetch": {"count": len(bookings), "strategy": booking_source, "candidate_ids_checked": candidate_ids, "counts": booking_counts},
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
            "latency_breakdown": debug["latency_breakdown"],
        },
        write_debug_file=debug_write,
    )

    output = {
        "ranked_items": ranked,
        "ranked_hotels": ranked_hotels,
        # Luôn expose latency để latency.py (build_latency_summary) đọc được
        "latency_ms": latency_ms,
        "latency_breakdown": debug["latency_breakdown"],
    }
    if return_debug:
        output["debug"] = debug
    return output
