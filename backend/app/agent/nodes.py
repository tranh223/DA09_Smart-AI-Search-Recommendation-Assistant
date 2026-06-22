"""Node implementations for OTA LangGraph workflow."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.agent.latency import build_latency_summary
from app.agent.qu_adapter import pipeline_result_to_state
from app.agent.response_builder import build_response_with_llm
from app.agent.state import AgentState
from app.core.trace import current_trace
from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged
from app.recommendation.models import PriceRange, Profile, RecommendInput, SessionContext

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_LIMIT_PER_SOURCE = 10
MAX_CANDIDATE_LIMIT_PER_SOURCE = 50


# ── QueryUnderstandingPipeline singleton ─────────────────────────────────────
# Khởi tạo một lần duy nhất (lazy, thread-safe) để tránh load lại
# FAISS index, Neo4j driver và ThreadPoolExecutor trên mỗi request.

_pipeline_lock = threading.Lock()
_pipeline: Any = None          # QueryUnderstandingPipeline instance
_pipeline_init_failed = False  # Flag để không retry sau khi init đã thất bại


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

def _load_chat_history(session_id: str) -> list[dict[str, Any]]:
    """Load chat history từ MongoDB Sessions collection.

    Format MongoDB: [{"user_query": "...", "llm_answer": "..."}]
    Normalize sang format QU pipeline: [{"role": "user", "content": "..."}, ...]
    """
    if not session_id:
        return []
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415
        sessions = get_collection("Sessions")
        doc = sessions.find_one({"_id": transform_id(session_id)}, {"history": 1})
        if not doc or not isinstance(doc.get("history"), list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in doc["history"]:
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB history load failed: %s", exc)
        return []


def _load_conversation_summary(user_id: str) -> str:
    """Load conversation summary từ MongoDB Summary collection."""
    if not user_id:
        return ""
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415
        summaries = get_collection("Summary")
        doc = summaries.find_one({"user_id": transform_id(user_id)}, {"content": 1})
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


def _load_session_context(session_id: str) -> dict[str, Any]:
    if not session_id:
        return {}
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        sessions = get_collection("Sessions")
        doc = sessions.find_one(
            {"_id": transform_id(session_id)},
            {"session_context": 1},
        )
        session_context = doc.get("session_context") if doc else None
        return session_context if isinstance(session_context, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB session_context load failed: %s", exc)
        return {}


def _load_long_term_profile(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {}
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        users = get_collection("Users")
        projection = {"long_term_profile": 1, "profile": 1, "name": 1}
        doc = users.find_one({"_id": transform_id(user_id)}, projection)
        if doc is None:
            doc = users.find_one({"user_id": user_id}, projection)
        if not doc:
            return {}
        profile = doc.get("profile") if isinstance(doc.get("profile"), dict) else {}
        long_term = doc.get("long_term_profile") or profile.get("long_term_profile")
        return long_term if isinstance(long_term, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] MongoDB long_term_profile load failed: %s", exc)
        return {}


def _build_server_user_profile(state: AgentState) -> dict[str, Any]:
    user_id = state.get("user_id") or "anonymous_user"
    session_id = state.get("session_id") or ""
    fallback = state.get("user_profile") or {}

    server_session_context = _load_session_context(session_id)
    fallback_session_context = fallback.get("session_context") if isinstance(fallback, dict) else {}
    session_context = _merge_server_over_fallback(
        server_session_context,
        fallback_session_context if isinstance(fallback_session_context, dict) else {},
    )

    server_long_term = _load_long_term_profile(user_id)
    fallback_long_term = fallback.get("long_term_profile") if isinstance(fallback, dict) else {}
    long_term_profile = _merge_server_over_fallback(
        server_long_term,
        fallback_long_term if isinstance(fallback_long_term, dict) else {},
    )

    return {
        "user_id": user_id,
        "name": fallback.get("name") if isinstance(fallback, dict) else None,
        "long_term_profile": long_term_profile,
        "session_context": session_context,
    }


def session_node(state: AgentState) -> dict[str, Any]:
    """Load short-term memory từ MongoDB và compress history nếu quá dài.

    Flow:
      1. Load chat_history từ MongoDB Sessions (normalize về role/content format)
      2. Load conversation_summary từ MongoDB Summary
      3. Nếu history >= 6 turns → gọi summarize_chat() để compress (LLM_MODEL)
      4. Inject vào state để intent_node dùng làm conversation context

    Fallback: nếu MongoDB hoặc OpenAI fail, dùng giá trị từ request (client-side history).
    """
    req_id = state.get("request_id") or state.get("session_id") or "-"
    user_id = state.get("user_id") or ""
    session_id = state.get("session_id") or ""

    # Load từ MongoDB (ưu tiên DB, fallback về giá trị client gửi lên)
    history: list[dict[str, Any]] = (
        _load_chat_history(session_id)
        or state.get("chat_history")
        or []
    )
    summary: str = (
        _load_conversation_summary(user_id)
        or state.get("conversation_summary")
        or ""
    )
    user_profile = _build_server_user_profile(state)
    session_context = user_profile.get("session_context") or {}
    logger.debug(
        "[%s][session] loaded history=%d turns  summary=%s  dst=%s  check_in=%s  check_out=%s",
        req_id,
        len(history),
        bool(summary),
        session_context.get("destination"),
        session_context.get("check_in"),
        session_context.get("check_out"),
    )

    # Compress nếu lịch sử quá dài
    try:
        from app.memory.short_term.summary.summarizer import summarize_chat  # noqa: PLC0415
        prev_len = len(history)
        summary, history = summarize_chat(summary, history, user_id)
        if len(history) < prev_len:
            logger.debug(
                "[%s][session] history compressed %d→%d turns", req_id, prev_len, len(history),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session_node] summarize_chat failed — dùng history gốc: %s", exc)

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
                "has_pet": session_context.get("has_pet"),
                "has_children": session_context.get("has_children"),
                "nearby_place": session_context.get("nearby_place"),
                "budget_min": price.get("min") if isinstance(price, dict) else None,
                "budget_max": price.get("max") if isinstance(price, dict) else None,
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
    """Query rewrite placeholder — pass-through hiện tại, chờ RAG module."""
    return {"rewritten_query": state.get("raw_query", "")}


# ── RAG node ──────────────────────────────────────────────────────────────────

def rag_node(state: AgentState) -> dict[str, Any]:
    """Chạy RAG pipeline (planner → retrieval → aggregation → generation).

    Chỉ kích hoạt với intent liên quan đến Q&A / thông tin / đặc điểm khách sạn:
      information, special_feature, hotel_similar

    Intent hotel_search / personalization / trending bỏ qua RAG để giảm latency
    (RAG chạy song song với recommend+rerank nên không block).

    Fallback: trả empty nếu RAG chatbot không khởi tạo được.
    """
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
            check_in=slots.get("check_in"),
            check_out=slots.get("check_out"),
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
        _persist_profile_state_directly(
            session_id=session_id,
            user_id=state.get("user_id") or "",
            user_profile=state.get("updated_user_profile") or state.get("user_profile") or {},
        )
        _emit_analytics(
            session_id=session_id,
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

        session_set: dict[str, Any] = {
            "user_id": user_id or user_profile.get("user_id"),
            "updated_at": now,
        }
        if isinstance(session_context, dict):
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

        if user_id and isinstance(long_term_profile, dict):
            users = get_collection("Users")
            users.update_one(
                {"_id": transform_id(user_id)},
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] direct Mongo profile persist failed: %s", exc)


def _emit_analytics(
    *,
    session_id: str,
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
                question=query,
                answer=answer,
            )
        total_s = (latency_summary.get("total_ms") or 0) / 1000.0
        if total_s > 0:
            log_latency(time=total_s, session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] Kafka emit failed (non-fatal): %s", exc)


def _persist_chat_history_directly(
    *,
    session_id: str,
    question: str,
    answer: str,
) -> None:
    try:
        from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
        from app.utils.util import transform_id  # noqa: PLC0415

        sessions = get_collection("Sessions")
        sessions.update_one(
            {"_id": transform_id(session_id)},
            {
                "$push": {
                    "history": {
                        "user_query": question,
                        "llm_answer": answer,
                    }
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("[analytics_node] direct Mongo history persist failed: %s", exc)
