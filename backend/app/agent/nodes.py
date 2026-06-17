"""Node implementations for OTA LangGraph workflow."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.agent.qu_adapter import pipeline_result_to_state
from app.agent.response_builder import build_response_with_llm
from app.agent.state import AgentState
from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged
from app.recommendation.models import PriceRange, Profile, RecommendInput, SessionContext

logger = logging.getLogger(__name__)


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


# ── Session node ─────────────────────────────────────────────────────────────

def session_node(state: AgentState) -> dict[str, Any]:
    """Ensure memory fields exist in state."""
    return {
        "chat_history": state.get("chat_history", []),
        "conversation_summary": state.get("conversation_summary", ""),
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
    limit = int(((state.get("rerank_options") or {}).get("top_k") or 10))

    pipeline = _get_pipeline()
    if pipeline is None:
        return _keyword_intent_fallback(query, state)

    try:
        result = pipeline.run(
            query=query,
            user_profile_input=user_profile_raw,
            conversation_history=chat_history,
        )
        return pipeline_result_to_state(result, query=query, limit_per_source=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[intent_node] pipeline.run() failed — keyword fallback. error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return _keyword_intent_fallback(query, state)


def _keyword_intent_fallback(query: str, state: AgentState) -> dict[str, Any]:
    """Fallback khi QU pipeline không khả dụng."""
    slots: dict[str, Any] = state.get("slots") or {}
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
    decision = state.get("slot_is_complete")
    if decision is not None:
        return {"slot_is_complete": decision, "needs_clarification": not decision}
    has_destination = bool((state.get("slots") or {}).get("destination"))
    return {"slot_is_complete": has_destination, "needs_clarification": not has_destination}


# ── Clarify node ──────────────────────────────────────────────────────────────

def clarify_node(state: AgentState) -> dict[str, Any]:
    """Trả câu hỏi làm rõ được QU pipeline sinh ra."""
    question = (
        state.get("clarification_question")
        or "Anh/chị muốn đặt phòng tại thành phố hoặc điểm đến nào?"
    )
    return {
        "clarification_question": question,
        "final_response": {
            "type": "clarification",
            "question": question,
            "missing_fields": state.get("clarification_missing_fields") or [],
        },
    }


# ── Rewrite node ──────────────────────────────────────────────────────────────

def rewrite_node(state: AgentState) -> dict[str, Any]:
    """Query rewrite placeholder — pass-through hiện tại, chờ RAG module."""
    return {"rewritten_query": state.get("raw_query", "")}


# ── RAG node ──────────────────────────────────────────────────────────────────

def rag_node(state: AgentState) -> dict[str, Any]:
    """RAG placeholder — chờ app/rag/ được implement."""
    return {"rag_docs": [], "rag_answer": "", "rag_confidence": 0.0}


# ── Recommend node ────────────────────────────────────────────────────────────

def recommend_node(state: AgentState) -> dict[str, Any]:
    """Chạy candidate generation pipeline.

    Ưu tiên recommend_input đã được intent_node (QU pipeline) build sẵn.
    Fallback: build từ slots thủ công (client cũ hoặc khi QU không khả dụng).
    """
    recommend_input = _resolve_recommend_input(state)
    if recommend_input is None:
        return {"recommend_input": None, "merged_candidates": []}
    merged = run_candidate_pipeline(recommend_input, trace=False)
    return {"recommend_input": recommend_input, "merged_candidates": merged}


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
    recommend_input = state.get("recommend_input")
    merged = state.get("merged_candidates") or []
    if not recommend_input or not merged:
        return {"rerank_result": {"ranked_hotels": [], "ranked_items": []}, "ranked_recommendations": []}

    rerank_result = run_rerank_from_merged(
        inp=recommend_input,
        merged=merged,
        options=state.get("rerank_options"),
    )
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
            "metadata": {
                "destination": item.get("destination"),
                "price_min": item.get("price_min"),
                "price_max": item.get("price_max"),
                "currency": item.get("currency"),
                "feature_scores": item.get("feature_scores"),
                "negative_penalty": item.get("negative_penalty"),
            },
        }
        for item in rerank_result.get("ranked_hotels", [])
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
    ranked = state.get("ranked_recommendations") or []
    result = build_response_with_llm(
        query=state.get("rewritten_query") or state.get("raw_query") or "",
        intent=state.get("intent") or "hotel_search",
        destination=(state.get("slots") or {}).get("destination") or "",
        rag_answer=state.get("rag_answer") or "",
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

    Output bao gồm:
      - answer: câu trả lời tổng hợp (LLM hoặc fallback)
      - recommendations: danh sách khách sạn (mỗi item có ai_reason nếu LLM thành công)
      - sources: tài liệu RAG (hiện trống, sẽ có khi RAG implement)
      - next_suggestions: gợi ý câu hỏi tiếp theo
      - intent / needs_clarification / explanation: metadata
    """
    return {
        "final_response": {
            "answer": state.get("synthesized_answer") or state.get("rag_answer") or "",
            "intent": state.get("intent") or "",
            "recommendations": state.get("ranked_recommendations") or [],
            "sources": state.get("rag_docs") or [],
            "next_suggestions": state.get("next_suggestions") or [],
            "needs_clarification": state.get("needs_clarification", False),
            "explanation": state.get("explanation") or "",
        }
    }


def analytics_node(state: AgentState) -> dict[str, Any]:
    """Analytics hook — chờ Kafka/Mongo logging được wire vào."""
    return {}
