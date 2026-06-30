"""Node implementations for OTA LangGraph workflow."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent.latency import build_latency_summary
from app.agent.qu_adapter import pipeline_result_to_state
from app.agent.response_builder import build_guardrail_response_with_llm, build_response_with_llm
from app.agent.state import AgentState
from app.core.trace import current_trace
from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged
from app.recommendation.candidate_generation.hotel_search.slots import extract_slots
from app.recommendation.models import PriceRange, Profile, RecommendInput, SessionContext

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_LIMIT_PER_SOURCE = 10
MAX_CANDIDATE_LIMIT_PER_SOURCE = 50
DEFAULT_TAGREMOVED_RECONCILE_INTERVAL_HOURS = 24


# ── QueryUnderstandingPipeline singleton ─────────────────────────────────────
# Khởi tạo một lần duy nhất (lazy, thread-safe) để tránh load lại
# FAISS index, Neo4j driver và ThreadPoolExecutor trên mỗi request.

_pipeline_lock = threading.Lock()
_pipeline: Any = None          # QueryUnderstandingPipeline instance
_pipeline_init_failed = False  # Flag để không retry sau khi init đã thất bại
_summary_jobs_lock = threading.Lock()
_summary_jobs_in_progress: set[str] = set()
SUMMARY_SESSION_GROUP_KEYS = (
    "session_trip_types",
    "session_preference_habits",
    "session_hotel_types",
    "session_room_views",
    "session_amenities",
    "session_budget_levels",
)


def _get_pipeline() -> Any:
    """Trả về singleton QueryUnderstandingPipeline, hoặc None nếu không khả dụng."""
    global _pipeline, _pipeline_init_failed
    if _pipeline_init_failed:
        return None
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:  # double-checked locking
            return _pipeline
        try:
            from query_understanding.pipeline import QueryUnderstandingPipeline
            _pipeline = QueryUnderstandingPipeline()
            logger.info("[intent_node] QueryUnderstandingPipeline initialized.")
        except Exception as exc:
            _pipeline_init_failed = True
            logger.warning(
                "[intent_node] QueryUnderstandingPipeline init failed — keyword fallback active. "
                "error=%s: %s",
                type(exc).__name__,
                exc,
            )
    return _pipeline


def _candidate_limit_per_source(state: AgentState) -> int:
    """Read candidate retrieval fanout independently from rerank top_k."""
    raw_limit = state.get("candidate_limit_per_source", DEFAULT_CANDIDATE_LIMIT_PER_SOURCE)
    try:
        limit = int(raw_limit or DEFAULT_CANDIDATE_LIMIT_PER_SOURCE)
    except (TypeError, ValueError):
        limit = DEFAULT_CANDIDATE_LIMIT_PER_SOURCE
    return min(max(limit, 1), MAX_CANDIDATE_LIMIT_PER_SOURCE)


# ── Session node ─────────────────────────────────────────────────────────────

def _normalize_chat_history_items(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "role" in item and "content" in item:
            normalized.append(item)
        else:
            if item.get("user_query"):
                normalized.append({"role": "user", "content": item["user_query"]})
            if item.get("llm_answer"):
                normalized.append({"role": "assistant", "content": item["llm_answer"]})
    return normalized


def _load_chat_history(
    session_id: str,
    user_id: str,
    *,
    allow_summary_fallback: bool = True,
) -> list[dict[str, Any]]:
    """Load chat history from MongoDB Summary.history.

    Format MongoDB: [{"user_query": "...", "llm_answer": "..."}]
    Normalize sang format QU pipeline: [{"role": "user", "content": "..."}, ...]
    """
    del session_id
    if not user_id or not allow_summary_fallback:
        return []
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        summaries = get_collection("Summary")
        doc = summaries.find_one({"user_id": user_id}, {"history": 1})
        if doc is None:
            doc = summaries.find_one({"_id": transform_id(user_id)}, {"history": 1})
        if doc and isinstance(doc.get("history"), list):
            return _normalize_chat_history_items(doc["history"])
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB history load failed: %s", exc)
        return []


def _load_conversation_summary(user_id: str) -> str:
    """Load conversation summary từ MongoDB Summary collection."""
    if not user_id:
        return ""
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        summaries = get_collection("Summary")
        doc = summaries.find_one({"user_id": user_id}, {"content": 1})
        if doc is None:
            from app.utils.util import transform_id  # noqa: PLC0415

            doc = summaries.find_one({"_id": transform_id(user_id)}, {"content": 1})
        return doc.get("content") or "" if doc else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB summary load failed: %s", exc)
        return ""


def _has_meaningful_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, dict):
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    return True


def _normalize_context_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip()


def _is_different_context_destination(current_destination: Any, incoming_destination: Any) -> bool:
    if not _has_meaningful_value(current_destination) or not _has_meaningful_value(incoming_destination):
        return False
    return _normalize_context_text(current_destination) != _normalize_context_text(incoming_destination)


def _is_chitchat_query(query: str) -> bool:
    normalized = " ".join(str(query or "").strip().lower().split())
    if not normalized:
        return False
    chitchat_patterns = (
        r"^(hi|hello|hey|xin chào|chào|chao)(\s|$)",
        r"(bạn|ban)\s+có\s+thể\s+giúp\s+gì",
        r"(ban|bạn)\s+co\s+the\s+giup\s+gi",
        r"(giúp|giup)\s+(gì|gi)",
        r"(có|co)\s+thể\s+làm\s+gì",
        r"(co|có)\s+the\s+lam\s+gi",
    )
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in chitchat_patterns)


def _merge_server_over_fallback(
    server_value: dict[str, Any],
    fallback_value: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(fallback_value or {})
    for key, value in (server_value or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_server_over_fallback(value, merged[key])
        elif _has_meaningful_value(value):
            merged[key] = value
    return merged


def _load_user_scoped_doc(
    collection_name: str,
    user_id: str,
    projection: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not user_id:
        return None
    from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
    from app.utils.util import transform_id  # noqa: PLC0415

    collection = get_collection(collection_name)
    doc = collection.find_one({"user_id": user_id}, projection)
    if doc is not None:
        return doc
    return collection.find_one({"_id": transform_id(user_id)}, projection)


def _normalize_user_scoped_doc_key(collection_name: str, user_id: str) -> None:
    if not user_id:
        return
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        collection = get_collection(collection_name)
        if collection.find_one({"user_id": user_id}, {"_id": 1}) is not None:
            return
        legacy_doc = collection.find_one({"_id": transform_id(user_id)}, {"_id": 1, "user_id": 1})
        if legacy_doc is None or legacy_doc.get("user_id") == user_id:
            return
        collection.update_one(
            {"_id": legacy_doc["_id"]},
            {"$set": {"user_id": user_id}},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[session_node] MongoDB %s key normalization failed for user=%s: %s",
            collection_name,
            user_id,
            exc,
        )


def _load_summary_session_context(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {}
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        summaries = get_collection("Summary")
        doc = summaries.find_one({"user_id": user_id}, {"session_context": 1})
        if doc is None:
            doc = summaries.find_one({"_id": transform_id(user_id)}, {"session_context": 1})
        summary_context = doc.get("session_context") if doc else None
        if not isinstance(summary_context, dict):
            return {}
        return _summary_session_context_to_runtime(summary_context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB summary session_context load failed: %s", exc)
        return {}


def _summary_session_context_to_runtime(summary_context: dict[str, Any]) -> dict[str, Any]:
    runtime: dict[str, Any] = {}
    for summary_key, runtime_key in (
        ("destination", "destination"),
        ("number_of_guests", "number_of_guests"),
        ("number_of_days", "number_of_days"),
        ("number_of_nights", "number_of_nights"),
        ("check_in", "check_in"),
        ("check_out", "check_out"),
        ("budget_type", "budget_type"),
        ("raw_budget_min", "raw_budget_min"),
        ("raw_budget_max", "raw_budget_max"),
    ):
        value = summary_context.get(summary_key)
        if _has_meaningful_value(value):
            runtime[runtime_key] = value

    price_range: dict[str, Any] = {}
    budget_min = summary_context.get("budget_min")
    budget_max = summary_context.get("budget_max")
    if budget_min is not None:
        price_range["min"] = budget_min
    if budget_max is not None:
        price_range["max"] = budget_max
    if price_range:
        price_range["currency"] = "VND"
        runtime["session_price_range"] = price_range
    for key in SUMMARY_SESSION_GROUP_KEYS:
        value = summary_context.get(key)
        if _has_meaningful_value(value):
            runtime[key] = value
    return runtime


def _runtime_session_context_to_summary(session_context: dict[str, Any]) -> dict[str, Any]:
    summary_context: dict[str, Any] = {}
    for runtime_key, summary_key in (
        ("destination", "destination"),
        ("number_of_guests", "number_of_guests"),
        ("number_of_days", "number_of_days"),
        ("number_of_nights", "number_of_nights"),
        ("check_in", "check_in"),
        ("check_out", "check_out"),
        ("budget_type", "budget_type"),
        ("raw_budget_min", "raw_budget_min"),
        ("raw_budget_max", "raw_budget_max"),
    ):
        value = session_context.get(runtime_key)
        if _has_meaningful_value(value):
            summary_context[summary_key] = value

    price_range = session_context.get("session_price_range")
    if isinstance(price_range, dict):
        budget_min = price_range.get("min")
        budget_max = price_range.get("max")
        if budget_min is not None:
            summary_context["budget_min"] = budget_min
        if budget_max is not None:
            summary_context["budget_max"] = budget_max
    for key in SUMMARY_SESSION_GROUP_KEYS:
        value = session_context.get(key)
        if _has_meaningful_value(value):
            summary_context[key] = value
    return summary_context


def _merge_summary_session_context(
    existing_context: dict[str, Any],
    incoming_context: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing_context or {})
    incoming_destination = incoming_context.get("destination")
    if _is_different_context_destination(merged.get("destination"), incoming_destination):
        merged.pop("number_of_days", None)
        merged.pop("number_of_nights", None)
    for key in (
        "destination",
        "number_of_guests",
        "number_of_days",
        "number_of_nights",
        "check_in",
        "check_out",
        "budget_min",
        "budget_max",
        "raw_budget_min",
        "raw_budget_max",
        "budget_type",
        *SUMMARY_SESSION_GROUP_KEYS,
    ):
        value = incoming_context.get(key)
        if _has_meaningful_value(value):
            merged[key] = value
    return merged


def _load_long_term_profile(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {}
    try:
        projection = {"long_term_profile": 1, "profile": 1, "name": 1}
        doc = _load_user_scoped_doc("Users", user_id, projection)
        if not doc:
            return {}
        profile = doc.get("profile") if isinstance(doc.get("profile"), dict) else {}
        long_term = doc.get("long_term_profile") or profile.get("long_term_profile")
        return long_term if isinstance(long_term, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB long_term_profile load failed: %s", exc)
        return {}


def _load_tagremoved_profile(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {}
    try:
        doc = _load_user_scoped_doc("TagRemoved", user_id, {"tagremoved_profile": 1})
        payload = doc.get("tagremoved_profile") if doc else None
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB tagremoved_profile load failed: %s", exc)
        return {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tagremoved_reconcile_interval_hours() -> int:
    raw = os.getenv(
        "TAGREMOVED_RECONCILE_INTERVAL_HOURS",
        str(DEFAULT_TAGREMOVED_RECONCILE_INTERVAL_HOURS),
    )
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        hours = DEFAULT_TAGREMOVED_RECONCILE_INTERVAL_HOURS
    return max(hours, 1)


def _latest_interaction(first: str, second: str) -> str:
    return max(first, second)


def _merge_count_maps(
    base_map: dict[str, Any],
    incoming_map: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in (base_map or {}).items():
        if isinstance(value, dict) and "count" in value and "last_interaction" in value:
            merged[str(key)] = {
                "count": int(value.get("count", 0)),
                "last_interaction": str(value.get("last_interaction", "")),
            }
    for key, value in (incoming_map or {}).items():
        if not (isinstance(value, dict) and "count" in value and "last_interaction" in value):
            continue
        normalized_key = str(key)
        current = merged.get(normalized_key)
        if current is None:
            merged[normalized_key] = {
                "count": int(value.get("count", 0)),
                "last_interaction": str(value.get("last_interaction", "")),
            }
            continue
        merged[normalized_key] = {
            "count": int(current.get("count", 0)) + int(value.get("count", 0)),
            "last_interaction": _latest_interaction(
                str(current.get("last_interaction", "")),
                str(value.get("last_interaction", "")),
            ),
        }
    return merged


def _merge_long_term_profile_dicts(
    base_profile: dict[str, Any],
    incoming_profile: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base_profile or {})
    score_fields = [
        "traveler_type",
        "long_term_trip_types",
        "long_term_budget_levels",
        "long_term_preference_habits",
        "long_term_hotel_types",
        "long_term_room_views",
        "long_term_amenities",
    ]
    for field in score_fields:
        merged[field] = _merge_count_maps(
            base_profile.get(field, {}) if isinstance(base_profile, dict) else {},
            incoming_profile.get(field, {}) if isinstance(incoming_profile, dict) else {},
        )

    base_neg = base_profile.get("long_term_negative_preferences", {}) if isinstance(base_profile, dict) else {}
    incoming_neg = (
        incoming_profile.get("long_term_negative_preferences", {})
        if isinstance(incoming_profile, dict)
        else {}
    )
    merged["long_term_negative_preferences"] = {
        field: _merge_count_maps(
            base_neg.get(field, {}) if isinstance(base_neg, dict) else {},
            incoming_neg.get(field, {}) if isinstance(incoming_neg, dict) else {},
        )
        for field in (
            "avoid_hotel_types",
            "avoid_amenities",
            "avoid_preference_habits",
            "avoid_nearby_places",
            "avoid_locations",
        )
    }

    merged["long_term_price_range"] = dict(
        (base_profile.get("long_term_price_range", {}) if isinstance(base_profile, dict) else {}) or {}
    )
    incoming_price = incoming_profile.get("long_term_price_range", {}) if isinstance(incoming_profile, dict) else {}
    if isinstance(incoming_price, dict):
        for key in ("min", "max", "currency"):
            if incoming_price.get(key) is not None:
                merged["long_term_price_range"][key] = incoming_price.get(key)

    for scalar_field in ("nationality", "age_group", "current_workplace", "is_enough"):
        incoming_value = incoming_profile.get(scalar_field) if isinstance(incoming_profile, dict) else None
        if incoming_value is not None:
            merged[scalar_field] = incoming_value
        elif scalar_field not in merged and isinstance(base_profile, dict):
            merged[scalar_field] = base_profile.get(scalar_field)
    base_clicks = base_profile.get("recommendation_clicks") if isinstance(base_profile, dict) else None
    incoming_clicks = incoming_profile.get("recommendation_clicks") if isinstance(incoming_profile, dict) else None
    if isinstance(incoming_clicks, dict) and incoming_clicks.get("hotel"):
        merged["recommendation_clicks"] = incoming_clicks
    elif base_clicks is not None:
        merged["recommendation_clicks"] = base_clicks
    return merged


def _reconcile_tagremoved_profile_if_due(user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not user_id:
        return {}, {}
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415

        users = get_collection("Users")
        tagremoved = get_collection("TagRemoved")
        _normalize_user_scoped_doc_key("Users", user_id)
        _normalize_user_scoped_doc_key("TagRemoved", user_id)
        user_doc = _load_user_scoped_doc("Users", user_id, {"long_term_profile": 1})
        tagremoved_doc = _load_user_scoped_doc("TagRemoved", user_id)

        long_term_profile = (
            user_doc.get("long_term_profile") if isinstance(user_doc, dict) else {}
        ) or {}
        removed_profile = (
            tagremoved_doc.get("tagremoved_profile") if isinstance(tagremoved_doc, dict) else {}
        ) or {}
        if not removed_profile:
            return long_term_profile if isinstance(long_term_profile, dict) else {}, {}

        last_reconciled_at = _parse_datetime(
            tagremoved_doc.get("last_reconciled_at") if isinstance(tagremoved_doc, dict) else None
        )
        interval_hours = _tagremoved_reconcile_interval_hours()
        now = datetime.now(timezone.utc)
        if last_reconciled_at and now < (last_reconciled_at + timedelta(hours=interval_hours)):
            return (
                long_term_profile if isinstance(long_term_profile, dict) else {},
                removed_profile if isinstance(removed_profile, dict) else {},
            )

        merged_profile = _merge_long_term_profile_dicts(
            long_term_profile if isinstance(long_term_profile, dict) else {},
            removed_profile if isinstance(removed_profile, dict) else {},
        )
        users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "long_term_profile": merged_profile,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        tagremoved.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "tagremoved_profile": {},
                    "updated_at": now,
                    "last_reconciled_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return merged_profile, {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB tagremoved reconcile failed: %s", exc)
        return _load_long_term_profile(user_id), _load_tagremoved_profile(user_id)


def _build_server_user_profile(state: AgentState) -> dict[str, Any]:
    user_id = state.get("user_id") or "anonymous_user"
    fallback = state.get("user_profile") or {}

    summary_session_context = _load_summary_session_context(user_id)
    fallback_session_context = fallback.get("session_context") if isinstance(fallback, dict) else {}
    session_context = _merge_server_over_fallback(
        summary_session_context,
        fallback_session_context if isinstance(fallback_session_context, dict) else {},
    )

    server_long_term, server_tagremoved = _reconcile_tagremoved_profile_if_due(user_id)
    fallback_long_term = fallback.get("long_term_profile") if isinstance(fallback, dict) else {}
    long_term_profile = _merge_server_over_fallback(
        server_long_term,
        fallback_long_term if isinstance(fallback_long_term, dict) else {},
    )
    fallback_tagremoved = fallback.get("tagremoved_profile") if isinstance(fallback, dict) else {}
    tagremoved_profile = _merge_server_over_fallback(
        server_tagremoved,
        fallback_tagremoved if isinstance(fallback_tagremoved, dict) else {},
    )

    return {
        "user_id": user_id,
        "name": fallback.get("name") if isinstance(fallback, dict) else None,
        "long_term_profile": long_term_profile,
        "tagremoved_profile": tagremoved_profile,
        "session_context": session_context,
    }


def session_node(state: AgentState) -> dict[str, Any]:
    """Load short-term memory từ MongoDB.

    Flow:
      1. Load chat_history từ MongoDB Summary.history (normalize về role/content format)
      2. Load conversation_summary từ MongoDB Summary
      3. Inject vào state để intent_node dùng làm conversation context

    Fallback: nếu MongoDB hoặc OpenAI fail, dùng giá trị từ request (client-side history).
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    user_id = state.get("user_id") or ""
    session_id = state.get("session_id") or ""
    query = state.get("raw_query") or ""

    user_profile = _build_server_user_profile(state)
    session_context = user_profile.get("session_context") or {}
    has_session_context = _has_meaningful_value(session_context)
    allow_summary_fallback = not (_is_chitchat_query(query) and not has_session_context)

    # Load từ MongoDB (ưu tiên DB, fallback về giá trị client gửi lên)
    history: list[dict[str, Any]] = (
        _load_chat_history(
            session_id=session_id,
            user_id=user_id,
            allow_summary_fallback=allow_summary_fallback,
        )
        or (state.get("chat_history") if allow_summary_fallback else [])
        or []
    )
    summary: str = (
        _load_conversation_summary(user_id)
        or state.get("conversation_summary")
        or ""
    )
    logger.debug(
        "[%s][session] loaded history=%d turns  summary=%s  dst=%s  check_in=%s  check_out=%s",
        req_id,
        len(history),
        bool(summary),
        session_context.get("destination"),
        session_context.get("check_in"),
        session_context.get("check_out"),
    )

    return {
        "chat_history": history,
        "conversation_summary": summary,
        "user_profile": user_profile,
    }


# ── Intent node ───────────────────────────────────────────────────────────────

def intent_node(state: AgentState) -> dict[str, Any]:
    """Chạy QueryUnderstandingPipeline để trích xuất intent, slots và profile.

    Pipeline: guardrail → LLM intent → FAISS semantic map → Neo4j graph
              expand → session profile update → search planner → router.

    Khi thành công, trả về recommend_input đã build đầy đủ để recommend_node
    dùng trực tiếp mà không cần build lại từ slots thủ công.

    Fallback: nếu pipeline không khởi tạo được hoặc lỗi tại runtime,
    về keyword-based intent để hệ thống không bị down hoàn toàn.
    """
    query = (state.get("raw_query") or "").strip()
    user_profile_raw: dict[str, Any] = state.get("user_profile") or {}
    user_id = state.get("user_id") or user_profile_raw.get("user_id") or "anonymous_user"

    if "user_id" not in user_profile_raw:
        user_profile_raw = {**user_profile_raw, "user_id": user_id}

    chat_history: list[dict[str, str]] = state.get("chat_history") or []
    conversation_summary: str = state.get("conversation_summary") or ""
    limit = _candidate_limit_per_source(state)

    req_id = state.get("request_id") or state.get("session_id") or "-"
    pipeline = _get_pipeline()
    if pipeline is None:
        logger.warning("[%s][intent] QU pipeline unavailable → keyword fallback", req_id)
        return _keyword_intent_fallback(query, state)

    try:
        result = pipeline.run(
            query=query,
            user_profile_input=user_profile_raw,
            conversation_history=chat_history,
            conversation_summary=conversation_summary,
        )
        mapped = pipeline_result_to_state(result, query=query, limit_per_source=limit)
        logger.debug(
            "[%s][intent] QU pipeline OK  intent=%s  destination=%s  slot_ok=%s",
            req_id,
            mapped.get("intent"),
            (mapped.get("slots") or {}).get("destination"),
            mapped.get("slot_is_complete"),
        )
        return mapped
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s][intent] pipeline.run() failed → keyword fallback. error=%s: %s",
            req_id, type(exc).__name__, exc,
        )
        return _keyword_intent_fallback(query, state)


def _keyword_intent_fallback(query: str, state: AgentState) -> dict[str, Any]:
    """Fallback khi QU pipeline không khả dụng."""
    slots: dict[str, Any] = state.get("slots") or {}
    if not slots:
        user_profile = state.get("user_profile") or {}
        session_context = user_profile.get("session_context") if isinstance(user_profile, dict) else {}
        if isinstance(session_context, dict):
            price = session_context.get("session_price_range") or {}
            slots = {
                "destination": session_context.get("destination"),
                "check_in": session_context.get("check_in"),
                "check_out": session_context.get("check_out"),
                "number_of_guests": session_context.get("number_of_guests"),
                "number_of_days": session_context.get("number_of_days"),
                "number_of_nights": session_context.get("number_of_nights"),
                "has_pet": session_context.get("has_pet"),
                "has_children": session_context.get("has_children"),
                "nearby_place": session_context.get("nearby_place"),
                "budget_min": price.get("min") if isinstance(price, dict) else None,
                "budget_max": price.get("max") if isinstance(price, dict) else None,
                "raw_budget_min": session_context.get("raw_budget_min"),
                "raw_budget_max": session_context.get("raw_budget_max"),
                "budget_type": session_context.get("budget_type"),
                "currency": (price.get("currency") if isinstance(price, dict) else None) or "VND",
            }
    intent = "hotel_search"
    if any(k in query.lower() for k in ("so sánh", "compare")):
        intent = "hotel_similar"
    elif any(k in query.lower() for k in ("book", "đặt phòng")):
        intent = "booking_support"
    has_destination = bool(slots.get("destination"))
    return {
        "intent": intent,
        "slots": slots,
        "slot_is_complete": has_destination,
        "needs_clarification": not has_destination,
        "clarification_question": (
            "" if has_destination
            else "Anh/chị muốn đặt phòng tại thành phố hoặc điểm đến nào?"
        ),
        "clarification_missing_fields": [] if has_destination else ["destination"],
        "recommend_input": None,
        "qu_trace": {},
    }


# ── Slot check node ───────────────────────────────────────────────────────────

def slot_check_node(state: AgentState) -> dict[str, Any]:
    """Chuyển tiếp quyết định slot_is_complete từ intent_node sang router.

    intent_node luôn set slot_is_complete (cả QU path lẫn fallback).
    Hàm này đảm bảo giá trị được đọc đúng bởi route_slot_check.
    Fallback destination-check để an toàn khi test gọi node này độc lập.
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    decision = state.get("slot_is_complete")
    if decision is not None:
        logger.debug(
            "[%s][slot_check] slot_is_complete=%s → route=%s",
            req_id, decision, "complete" if decision else "clarify",
        )
        return {"slot_is_complete": decision, "needs_clarification": not decision}
    has_destination = bool((state.get("slots") or {}).get("destination"))
    logger.debug(
        "[%s][slot_check] fallback destination_check=%s → route=%s",
        req_id, has_destination, "complete" if has_destination else "clarify",
    )
    return {"slot_is_complete": has_destination, "needs_clarification": not has_destination}


# ── Clarify node ──────────────────────────────────────────────────────────────

def clarify_node(state: AgentState) -> dict[str, Any]:
    """Trả câu hỏi làm rõ được QU pipeline sinh ra.

    final_response được format đúng schema của ChatData để _build_chat_data()
    trong chat.py map được chính xác (không đi qua format_response_node).
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    question = (
        state.get("clarification_question")
        or "Anh/chị muốn đặt phòng tại thành phố hoặc điểm đến nào?"
    )
    missing = state.get("clarification_missing_fields") or []
    intent = state.get("intent") or "clarification_needed"
    latency = build_latency_summary(state)
    guardrail = ((state.get("qu_trace") or {}).get("guardrail") or {})

    if intent in {"assistant_help", "assistant_capability"}:
        guardrail_response = build_guardrail_response_with_llm(
            query=state.get("raw_query") or "",
            category="ASSISTANT_HELP",
            reason=str(guardrail.get("reason") or ""),
            assistant_help_context_mode=str(guardrail.get("assistant_help_context_mode") or "NO_HISTORY"),
            conversation_summary=state.get("conversation_summary") or "",
            chat_history=state.get("chat_history") or [],
        )
        answer = guardrail_response.get("answer") or question
        next_suggestions = guardrail_response.get("next_suggestions") or []
        logger.debug("[%s][clarify] assistant_help answer=%.60s", req_id, answer)
        return {
            "clarification_question": "",
            "final_response": {
                "answer": answer,
                "intent": intent,
                "recommendations": [],
                "sources": [],
                "next_suggestions": next_suggestions,
                "needs_clarification": False,
                "clarification_question": "",
                "missing_fields": [],
                "explanation": "",
                "latency": latency,
            },
        }

    if guardrail and guardrail.get("allow") is False:
        guardrail_response = build_guardrail_response_with_llm(
            query=state.get("raw_query") or "",
            category=str(guardrail.get("category") or ""),
            reason=str(guardrail.get("reason") or ""),
            assistant_help_context_mode=str(guardrail.get("assistant_help_context_mode") or "NONE"),
            conversation_summary=state.get("conversation_summary") or "",
            chat_history=state.get("chat_history") or [],
        )
        answer = guardrail_response.get("answer") or question
        next_suggestions = guardrail_response.get("next_suggestions") or []
        logger.debug(
            "[%s][clarify] guardrail_blocked category=%s answer=%.60s",
            req_id,
            guardrail.get("category"),
            answer,
        )
        return {
            "clarification_question": "",
            "final_response": {
                "answer": answer,
                "intent": intent,
                "recommendations": [],
                "sources": [],
                "next_suggestions": next_suggestions,
                "needs_clarification": False,
                "clarification_question": "",
                "missing_fields": [],
                "explanation": str(guardrail.get("reason") or ""),
                "latency": latency,
            },
        }

    logger.debug(
        "[%s][clarify] missing_fields=%s  question=%.60s",
        req_id, missing, question,
    )
    return {
        "clarification_question": question,
        "final_response": {
            "answer": question,
            "intent": intent,
            "recommendations": [],
            "sources": [],
            "next_suggestions": [],
            "needs_clarification": True,
            "clarification_question": question,
            "missing_fields": missing,
            "explanation": "",
            "latency": latency,
        },
    }


# ── Rewrite node ──────────────────────────────────────────────────────────────
def rewrite_node(state: AgentState) -> dict[str, Any]:
    """Build a profile-based hotel search template for downstream Search API."""
    raw_query = state.get("raw_query", "")
    recommend_input = state.get("recommend_input")
    if recommend_input is None:
        return {"rewritten_query": raw_query, "search_query_template": ""}

    try:
        search_query_template = build_search_query_template(recommend_input)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[rewrite_node] build search query template failed: %s", exc)
        return {"rewritten_query": raw_query, "search_query_template": ""}

    if not search_query_template:
        return {"rewritten_query": raw_query, "search_query_template": ""}

    copy_fn = getattr(recommend_input, "model_copy", None) or getattr(recommend_input, "copy")
    updated_recommend_input = copy_fn(update={"search_query_template": search_query_template})
    return {
        "rewritten_query": raw_query,
        "search_query_template": search_query_template,
        "recommend_input": updated_recommend_input,
    }


# ── Search query template builder ─────────────────────────────────────────────
def build_search_query_template(inp: RecommendInput) -> str:
    """Build the external Search API query template from current recommendation state."""
    return _build_search_query_text(extract_slots(inp))


def _build_search_query_text(slots: dict[str, Any]) -> str:
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

    traveler_type = _normalize_search_template_items(slots.get("traveler_type"))
    if traveler_type:
        parts.append(f"Phong cách du lịch của tôi là {_join_search_template_items(traveler_type)}.")

    budget_text = _format_search_template_budget_range(slots.get("budget_min"), slots.get("budget_max"))
    if budget_text:
        if slots.get("budget_type") == "total" and not slots.get("number_of_nights"):
            parts.append(f"Tổng ngân sách khách sạn của tôi khoảng {budget_text} cho chuyến đi.")
        else:
            parts.append(f"Tôi muốn phòng có giá khoảng {budget_text} mỗi đêm.")

    hotel_types = _normalize_search_template_items(slots.get("hotel_types"))
    if hotel_types:
        parts.append(f"Tôi ưu tiên loại hình lưu trú như {_join_search_template_items(hotel_types)}.")

    room_views = _normalize_search_template_items(slots.get("room_views"))
    if room_views:
        parts.append(f"Tôi muốn phòng có hướng nhìn như {_join_search_template_items(room_views)}.")

    amenities = _normalize_search_template_items(slots.get("amenities"))
    if amenities:
        parts.append(f"Tôi muốn khách sạn có tiện ích như {_join_search_template_items(amenities)}.")

    preference_habits = _normalize_search_template_items(slots.get("preference_habits"))
    if preference_habits:
        parts.append(f"Tôi muốn khách sạn có đặc điểm như {_join_search_template_items(preference_habits)}.")

    profile_features = slots.get("profile_features") or []
    if profile_features and not any((hotel_types, room_views, amenities, preference_habits)):
        parts.append(
            "Tôi muốn khách sạn có các tiện ích và đặc điểm như "
            + _join_search_template_items(_normalize_search_template_items(profile_features)[:12])
            + "."
        )

    return " ".join(parts).strip()


def _normalize_search_template_items(values: Any, *, limit: int = 12) -> list[str]:
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


def _join_search_template_items(values: list[str]) -> str:
    return ", ".join(values)


def _format_search_template_budget_range(budget_min: Any, budget_max: Any) -> str:
    min_text = _format_vnd_million_for_search_template(budget_min)
    max_text = _format_vnd_million_for_search_template(budget_max)
    if min_text and max_text:
        if min_text == max_text:
            return f"{min_text} triệu"
        return f"{min_text} triệu đến {max_text} triệu"
    if max_text:
        return f"tối đa {max_text} triệu"
    if min_text:
        return f"từ {min_text} triệu"
    return ""


def _format_vnd_million_for_search_template(value: Any) -> str:
    if value is None:
        return ""
    try:
        million_value = float(value) / 1_000_000
    except (TypeError, ValueError):
        return ""
    if million_value <= 0:
        return ""
    rounded = round(million_value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _router_plan_lengths(state: AgentState) -> tuple[int, int] | None:
    """Return (rag_steps, recommendation_steps) from QU trace when available."""
    qu_trace = state.get("qu_trace") or {}
    if not isinstance(qu_trace, dict):
        return None

    router = qu_trace.get("router") or {}
    if not isinstance(router, dict):
        return None

    rag_plan = router.get("rag_plan")
    recommendation_plan = router.get("recommendation_plan")
    if not isinstance(rag_plan, list) or not isinstance(recommendation_plan, list):
        return None

    return (len(rag_plan), len(recommendation_plan))


def _should_run_rag(state: AgentState) -> bool:
    """Decide whether RAG should execute for current request."""
    plan_lengths = _router_plan_lengths(state)
    if plan_lengths is not None:
        rag_steps, _ = plan_lengths
        return rag_steps > 0

    # Fallback for legacy paths without QU router trace.
    return (state.get("intent") or "") in {"information", "special_feature", "hotel_similar"}


def _should_run_recommend(state: AgentState) -> bool:
    """Decide whether recommendation pipeline should execute for current request."""
    plan_lengths = _router_plan_lengths(state)
    if plan_lengths is not None:
        _, recommendation_steps = plan_lengths
        return recommendation_steps > 0

    # Fallback for legacy paths without QU router trace.
    return state.get("recommend_input") is not None or (state.get("intent") or "") in {
        "personalization",
        "hotel_search",
    }


# ── RAG node ──────────────────────────────────────────────────────────────────
def rag_node(state: AgentState) -> dict[str, Any]:
    """Chạy RAG pipeline (planner → retrieval → aggregation → generation).

    Chỉ kích hoạt với intent liên quan đến Q&A / thông tin / đặc điểm khách sạn:
      information, special_feature, hotel_similar

    Intent hotel_search / personalization bỏ qua RAG để giảm latency
    (RAG chạy song song với recommend+rerank nên không block).

    Fallback: trả empty nếu RAG chatbot không khởi tạo được.
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    if not _should_run_rag(state):
        logger.debug("[%s][rag] skipped — no rag plan", req_id)
        return {"rag_docs": [], "rag_answer": "", "rag_confidence": 0.0}

    from app.agent.rag_adapter import run_rag  # noqa: PLC0415
    return run_rag(
        query=state.get("rewritten_query") or state.get("raw_query") or "",
        intent=state.get("intent") or "",
        slots=state.get("slots") or {},
        chat_history=state.get("chat_history") or [],
    )


# ── Recommend node ────────────────────────────────────────────────────────────

def recommend_node(state: AgentState) -> dict[str, Any]:
    """Chạy candidate generation pipeline.

    Ưu tiên recommend_input đã được intent_node (QU pipeline) build sẵn.
    Fallback: build từ slots thủ công (client cũ hoặc khi QU không khả dụng).
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    if not _should_run_recommend(state):
        logger.debug("[%s][recommend] skipped — no recommendation plan", req_id)
        return {"recommend_input": None, "merged_candidates": [], "_raw_source_stats": {}}

    recommend_input = _resolve_recommend_input(state)
    if recommend_input is None:
        logger.warning("[%s][recommend] recommend_input=None (no destination) → empty candidates", req_id)
        return {"recommend_input": None, "merged_candidates": [], "_raw_source_stats": {}}
    try:
        dst = recommend_input.session_context.destination if hasattr(recommend_input, "session_context") else "?"
    except Exception:  # noqa: BLE001
        dst = "?"
    logger.debug("[%s][recommend] running candidate pipeline  dst=%s", req_id, dst)

    # Bật trace logging khi có FlowTrace (logs chi tiết vào ota.trace.rec file)
    has_flow_trace = current_trace() is not None
    merged, raw_source_stats = run_candidate_pipeline(
        recommend_input,
        trace=has_flow_trace,
        return_stats=True,
    )
    logger.debug("[%s][recommend] candidates=%d  raw_stats=%s", req_id, len(merged), raw_source_stats)
    return {
        "recommend_input": recommend_input,
        "merged_candidates": merged,
        "_raw_source_stats": raw_source_stats,  # dùng bởi tracer._ctx_recommend
    }


def _resolve_recommend_input(state: AgentState) -> RecommendInput | None:
    """Trả về RecommendInput từ state (QU path) hoặc build từ slots (fallback)."""
    provided = state.get("recommend_input")
    if provided is not None:
        return provided

    slots = state.get("slots") or {}
    destination = slots.get("destination")
    if not destination:
        return None

    return RecommendInput(
        user_id=state.get("user_id") or "anonymous_user",
        profile=Profile(),
        session_context=SessionContext(
            destination=destination,
            nearby_place=slots.get("nearby_place"),
            number_of_guests=slots.get("number_of_guests"),
            number_of_days=slots.get("number_of_days"),
            number_of_nights=slots.get("number_of_nights"),
            check_in=slots.get("check_in"),
            check_out=slots.get("check_out"),
            budget_type=slots.get("budget_type"),
            raw_budget_min=slots.get("raw_budget_min"),
            raw_budget_max=slots.get("raw_budget_max"),
            has_children=slots.get("has_children"),
            has_pet=slots.get("has_pet"),
            session_price_range=PriceRange(
                min=slots.get("budget_min"),
                max=slots.get("budget_max"),
                currency=slots.get("currency") or "VND",
            ),
        ),
        original_query=state.get("rewritten_query") or state.get("raw_query", ""),
        limit_per_source=int(slots.get("limit", 10) or 10),
    )


# ── Rerank node ───────────────────────────────────────────────────────────────

def rerank_node(state: AgentState) -> dict[str, Any]:
    """Chạy production reranker trên merged candidates."""
    req_id = state.get("request_id") or state.get("session_id") or "-"
    recommend_input = state.get("recommend_input")
    merged = state.get("merged_candidates") or []
    if not recommend_input or not merged:
        logger.warning(
            "[%s][rerank] skipped — recommend_input=%s  candidates=%d",
            req_id, recommend_input is not None, len(merged),
        )
        return {"rerank_result": {"ranked_hotels": [], "ranked_items": []}, "ranked_recommendations": []}

    logger.debug("[%s][rerank] running on %d candidates", req_id, len(merged))
    rerank_result = run_rerank_from_merged(
        inp=recommend_input,
        merged=merged,
        options=state.get("rerank_options"),
    )
    ranked_hotels = rerank_result.get("ranked_hotels") or []
    # Expose debug ke tracer — return_debug=True đã được engine.py set mặc định
    debug = rerank_result.get("debug") or {}
    rerank_result["llm_used"] = bool(debug.get("llm_used"))
    logger.debug("[%s][rerank] ranked=%d  filtered=%s  llm=%s",
                 req_id, len(ranked_hotels),
                 debug.get("filtered_count", "?"),
                 debug.get("llm_used", False))
    ranked_recommendations = [
        {
            "hotel_id": item.get("hotel_id") or item.get("item_id"),
            "item_id": item.get("item_id"),
            "hotel_name": item.get("name"),
            "rank": item.get("rank"),
            "score": item.get("final_score"),
            "base_score": item.get("base_score"),
            "llm_score": item.get("llm_score"),
            "sources": item.get("sources", []),
            "reasons": item.get("reasons", []),
            "warnings": item.get("warnings", []),
            "primary_image": item.get("primary_image"),
            "metadata": {
                "destination": item.get("destination"),
                "price_min": item.get("price_min"),
                "price_max": item.get("price_max"),
                "currency": item.get("currency"),
                "feature_scores": item.get("feature_scores"),
                "negative_penalty": item.get("negative_penalty"),
                "primary_image": item.get("primary_image"),
            },
        }
        for item in ranked_hotels
    ]
    return {"rerank_result": rerank_result, "ranked_recommendations": ranked_recommendations}


# ── Response Builder / Explain / Format / Analytics nodes ────────────────────

def response_builder_node(state: AgentState) -> dict[str, Any]:
    """Tổng hợp kết quả RAG + recommendation bằng LLM.

    Chờ cả hai nhánh song song (rag_node và rerank_node) hoàn thành,
    sau đó gọi LLM để:
      - Sinh câu trả lời tự nhiên tổng hợp (synthesized_answer)
      - Giải thích lý do cho từng khách sạn (hotel_reasons)
      - Đề xuất câu hỏi tiếp theo (next_suggestions)

    Fallback: nếu LLM không khả dụng, trả về plain-text tĩnh.
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    ranked = state.get("ranked_recommendations") or []
    rag_answer = state.get("rag_answer") or ""
    logger.debug(
        "[%s][response_builder] building LLM response  ranked=%d  rag_answer=%s",
        req_id, len(ranked), bool(rag_answer),
    )
    result = build_response_with_llm(
        query=state.get("rewritten_query") or state.get("raw_query") or "",
        intent=state.get("intent") or "hotel_search",
        destination=(state.get("slots") or {}).get("destination") or "",
        rag_answer=rag_answer,
        ranked_recommendations=ranked,
        session_context=(
            (state.get("updated_user_profile") or state.get("user_profile") or {}).get("session_context")
            if isinstance(state.get("updated_user_profile") or state.get("user_profile"), dict)
            else {}
        ),
    )
    return result  # keys: synthesized_answer, hotel_reasons, next_suggestions


def explain_node(state: AgentState) -> dict[str, Any]:
    """Embed hotel_reasons vào từng ranked recommendation.

    hotel_reasons được sinh bởi response_builder_node (LLM).
    Mỗi recommendation sẽ có thêm field `ai_reason` để UI hiển thị
    câu giải thích cụ thể tại sao khách sạn đó phù hợp.
    """
    recommendations = list(state.get("ranked_recommendations") or [])
    hotel_reasons: dict[str, str] = state.get("hotel_reasons") or {}

    if hotel_reasons:
        enriched: list[dict[str, Any]] = []
        for rec in recommendations:
            hotel_id = str(rec.get("hotel_id") or rec.get("item_id") or "")
            reason = hotel_reasons.get(hotel_id)
            enriched.append({**rec, "ai_reason": reason} if reason else rec)
        recommendations = enriched

    explanation = (
        "Gợi ý dựa trên mức độ phù hợp truy vấn và tín hiệu người dùng."
        if recommendations
        else "Hiện chưa có gợi ý phù hợp, cần thêm thông tin để lọc tốt hơn."
    )
    return {
        "ranked_recommendations": recommendations,
        "explanation": explanation,
    }


def format_response_node(state: AgentState) -> dict[str, Any]:
    """Chuẩn hoá schema API response trả về UI.

    Output:
      - answer: câu trả lời tổng hợp (LLM hoặc fallback)
      - recommendations: danh sách khách sạn (mỗi item có ai_reason)
      - sources: tài liệu RAG (rag_docs từ RAG pipeline)
      - next_suggestions: gợi ý câu hỏi tiếp theo
      - intent / needs_clarification / explanation: metadata
      - latency: per-stage timing để client hiển thị / debug
    """
    latency = build_latency_summary(state)
    return {
        "final_response": {
            "answer": state.get("synthesized_answer") or state.get("rag_answer") or "",
            "intent": state.get("intent") or "",
            "recommendations": state.get("ranked_recommendations") or [],
            "sources": state.get("rag_docs") or [],
            "next_suggestions": state.get("next_suggestions") or [],
            "needs_clarification": state.get("needs_clarification", False),
            "explanation": state.get("explanation") or "",
            "latency": latency,
        }
    }


def analytics_node(state: AgentState) -> dict[str, Any]:
    """Emit analytics events qua Kafka và build latency summary.

    Gửi 2 loại event lên Kafka topic 'users-topic':
      - RAG_CHAT: cặp (query, answer) để Kafka consumer lưu vào MongoDB Sessions
      - LATENCY: tổng thời gian xử lý (giây) để tracking SLA

    Graceful fallback: nếu Kafka không khả dụng (producer=None), bỏ qua
    và chỉ trả về latency_summary.
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    session_id = state.get("session_id") or ""
    latency_summary = build_latency_summary(state)

    logger.debug(
        "[%s][analytics] total_ms=%s  bottleneck=%s(%s ms)",
        req_id,
        latency_summary.get("total_ms"),
        latency_summary.get("bottleneck_stage"),
        latency_summary.get("bottleneck_ms"),
    )

    if session_id:
        user_id = state.get("user_id") or ""
        _persist_profile_state_directly(
            session_id=session_id,
            user_id=user_id,
            user_profile=state.get("updated_user_profile") or state.get("user_profile") or {},
        )
        _emit_analytics(
            session_id=session_id,
            user_id=user_id,
            query=state.get("raw_query") or "",
            final_response=state.get("final_response") or {},
            latency_summary=latency_summary,
        )

    return {"latency_summary": latency_summary}


def _persist_profile_state_directly(
    *,
    session_id: str,
    user_id: str,
    user_profile: dict[str, Any],
) -> None:
    if not session_id or not isinstance(user_profile, dict):
        return
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        now = datetime.now(timezone.utc)
        session_context = user_profile.get("session_context")
        long_term_profile = user_profile.get("long_term_profile")
        tagremoved_profile = user_profile.get("tagremoved_profile")

        session_set: dict[str, Any] = {
            "user_id": user_id or user_profile.get("user_id"),
            "updated_at": now,
        }
        if isinstance(session_context, dict):
            # Metrics/RAGAS/debug snapshot only. Runtime state is loaded from
            # Summary.session_context, not from Sessions.session_context.
            session_set["session_context"] = session_context

        sessions = get_collection("Sessions")
        sessions.update_one(
            {"_id": transform_id(session_id)},
            {
                "$set": session_set,
                "$setOnInsert": {
                    "history": [],
                    "num_like": 0,
                    "num_dislike": 0,
                    "final_reaction": None,
                    "latency": [],
                    "ttft": [],
                    "booking": False,
                    "evaluated": False,
                    "end": None,
                },
            },
            upsert=True,
        )

        if user_id and isinstance(session_context, dict):
            summary_session_context = _runtime_session_context_to_summary(session_context)
            if summary_session_context:
                _normalize_user_scoped_doc_key("Summary", user_id)
                summaries = get_collection("Summary")
                existing_summary = summaries.find_one(
                    {"user_id": user_id},
                    {"session_context": 1},
                )
                existing_summary_context = (
                    existing_summary.get("session_context")
                    if isinstance(existing_summary, dict)
                    else {}
                )
                if not isinstance(existing_summary_context, dict):
                    existing_summary_context = {}
                merged_summary_context = _merge_summary_session_context(
                    existing_summary_context,
                    summary_session_context,
                )
                summaries.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "user_id": user_id,
                            "session_context": merged_summary_context,
                            "updated_at": now,
                            "last_updated": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )

        if user_id and isinstance(long_term_profile, dict):
            _normalize_user_scoped_doc_key("Users", user_id)
            users = get_collection("Users")
            users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "long_term_profile": long_term_profile,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        if user_id and isinstance(tagremoved_profile, dict):
            _normalize_user_scoped_doc_key("TagRemoved", user_id)
            tagremoved = get_collection("TagRemoved")
            tagremoved.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "tagremoved_profile": tagremoved_profile,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] direct Mongo profile persist failed: %s", exc)


def _emit_analytics(
    *,
    session_id: str,
    user_id: str,
    query: str,
    final_response: dict[str, Any],
    latency_summary: dict[str, Any],
) -> None:
    """Gửi events Kafka. Bắt toàn bộ exception để không block graph."""
    try:
        from app.analytics.logging.logger import log_latency  # noqa: PLC0415
        answer = final_response.get("answer") or ""
        if query and answer:
            _persist_chat_history_directly(
                session_id=session_id,
                user_id=user_id,
                question=query,
                answer=answer,
            )
            _schedule_summary_update(user_id=user_id)
        total_s = (latency_summary.get("total_ms") or 0) / 1000.0
        if total_s > 0:
            log_latency(time=total_s, session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] Kafka emit failed (non-fatal): %s", exc)


def _schedule_summary_update(*, user_id: str) -> None:
    if not user_id:
        return
    enabled = os.getenv("SUMMARY_BACKGROUND_ENABLED", "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return
    with _summary_jobs_lock:
        if user_id in _summary_jobs_in_progress:
            return
        _summary_jobs_in_progress.add(user_id)

    worker = threading.Thread(
        target=_run_summary_update_background,
        kwargs={"user_id": user_id},
        name=f"summary-update-{user_id}",
        daemon=True,
    )
    worker.start()


def _run_summary_update_background(*, user_id: str) -> None:
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        summaries = get_collection("Summary")
        doc = summaries.find_one(
            {"user_id": user_id},
            {"content": 1, "history": 1, "summary_history_fingerprint": 1},
        )
        if doc is None:
            doc = summaries.find_one(
                {"_id": transform_id(user_id)},
                {"content": 1, "history": 1, "summary_history_fingerprint": 1},
            )
        if not isinstance(doc, dict):
            return

        summary = str(doc.get("content") or "")
        history = doc.get("history") if isinstance(doc.get("history"), list) else []
        threshold = int(os.getenv("SUMMARY_TRIGGER_THRESHOLD", "10") or "10")
        if len(history) < threshold:
            return

        fingerprint = hashlib.sha256(
            json.dumps(history, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        if doc.get("summary_history_fingerprint") == fingerprint:
            logger.debug("[summary_background] skipped unchanged history user=%s", user_id)
            return

        from app.memory.short_term.summary.summarizer import summarize_chat  # noqa: PLC0415

        summarize_chat(summary, history, user_id)
        summaries.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "summary_history_fingerprint": fingerprint,
                    "summary_updated_at": datetime.now(timezone.utc),
                },
            },
            upsert=False,
        )
        logger.debug("[summary_background] completed user=%s history=%d", user_id, len(history))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[summary_background] failed user=%s: %s", user_id, exc)
    finally:
        with _summary_jobs_lock:
            _summary_jobs_in_progress.discard(user_id)


def _persist_chat_history_directly(
    *,
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
) -> None:
    if not session_id and not user_id:
        return
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        now = datetime.now(timezone.utc)
        history_item = {
            "user_query": question,
            "llm_answer": answer,
        }

        if session_id:
            sessions = get_collection("Sessions")
            sessions.update_one(
                {"_id": transform_id(session_id)},
                {
                    "$push": {
                        "history": {
                            "$each": [history_item],
                            "$slice": -10,
                        }
                    },
                    "$set": {
                        "user_id": user_id,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "num_like": 0,
                        "num_dislike": 0,
                        "final_reaction": None,
                        "latency": [],
                        "ttft": [],
                        "booking": False,
                        "evaluated": False,
                        "end": None,
                    },
                },
                upsert=True,
            )

        if user_id:
            summaries = get_collection("Summary")
            _normalize_user_scoped_doc_key("Summary", user_id)
            summary_doc = summaries.find_one(
                {"user_id": user_id},
                {"history": {"$slice": -1}},
            )
            if summary_doc is None:
                summary_doc = summaries.find_one(
                    {"_id": transform_id(user_id)},
                    {"history": {"$slice": -1}},
                )

            last_history_item = None
            if isinstance(summary_doc, dict):
                history_tail = summary_doc.get("history")
                if isinstance(history_tail, list) and history_tail:
                    candidate = history_tail[-1]
                    if isinstance(candidate, dict):
                        last_history_item = candidate

            if last_history_item != history_item:
                summaries.update_one(
                    {"user_id": user_id},
                    {
                        "$push": {
                            "history": {
                                "$each": [history_item],
                                "$slice": -10,
                            }
                        },
                        "$set": {
                            "user_id": user_id,
                            "updated_at": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] direct Mongo history persist failed: %s", exc)
