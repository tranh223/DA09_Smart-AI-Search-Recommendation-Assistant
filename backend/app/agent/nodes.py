"""Initial node implementations for OTA LangGraph workflow.

This module provides a runnable scaffold. It intentionally keeps logic simple
and deterministic so the team can incrementally replace each node with richer
business logic.
"""

from __future__ import annotations

from typing import Any

from app.agent.state import AgentState
from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged
from app.recommendation.models import PriceRange, Profile, RecommendInput, SessionContext


def session_node(state: AgentState) -> dict[str, Any]:
    """Ensure memory fields exist in state."""
    return {
        "chat_history": state.get("chat_history", []),
        "conversation_summary": state.get("conversation_summary", ""),
    }


def intent_node(state: AgentState) -> dict[str, Any]:
    """Baseline intent + slot extraction placeholder.

    TODO: replace with structured LLM extraction.
    """
    query = (state.get("raw_query") or "").strip()
    slots = state.get("slots", {})

    inferred_intent = state.get("intent", "hotel_search")
    if any(k in query.lower() for k in ("so sánh", "compare")):
        inferred_intent = "compare"
    elif any(k in query.lower() for k in ("book", "đặt")):
        inferred_intent = "booking_support"

    return {
        "intent": inferred_intent,
        "slots": slots,
    }


def slot_check_node(state: AgentState) -> dict[str, Any]:
    """Check if minimum booking slots are present."""
    slots = state.get("slots", {})
    has_destination = bool(slots.get("destination"))
    return {
        "slot_is_complete": has_destination,
        "needs_clarification": not has_destination,
    }


def clarify_node(state: AgentState) -> dict[str, Any]:
    """Ask for missing slots when destination is absent."""
    return {
        "clarification_question": "Anh/chị muốn đi đâu để mình gợi ý chính xác hơn?",
        "final_response": {
            "type": "clarification",
            "question": "Anh/chị muốn đi đâu để mình gợi ý chính xác hơn?",
        },
    }


def rewrite_node(state: AgentState) -> dict[str, Any]:
    """Simple rewrite placeholder for downstream retrieval."""
    return {"rewritten_query": state.get("raw_query", "")}


def _build_recommend_input_from_state(state: AgentState) -> RecommendInput | None:
    """Build minimal RecommendInput from state when upstream has not provided one."""
    provided = state.get("recommend_input")
    if provided is not None:
        return provided

    slots = state.get("slots", {})
    destination = slots.get("destination")
    if not destination:
        return None

    session_price_range = PriceRange(
        min=slots.get("budget_min"),
        max=slots.get("budget_max"),
        currency=slots.get("currency") or "VND",
    )
    session_context = SessionContext(
        destination=destination,
        nearby_place=slots.get("nearby_place"),
        number_of_guests=slots.get("number_of_guests"),
        check_in=slots.get("check_in"),
        check_out=slots.get("check_out"),
        has_children=slots.get("has_children"),
        has_pet=slots.get("has_pet"),
        session_price_range=session_price_range,
    )
    return RecommendInput(
        user_id=state.get("user_id", "anonymous_user"),
        profile=Profile(),
        session_context=session_context,
        original_query=state.get("rewritten_query") or state.get("raw_query", ""),
        limit_per_source=int(slots.get("limit", 10) or 10),
    )


def rag_node(state: AgentState) -> dict[str, Any]:
    """RAG placeholder.

    TODO: wire to planner/retrieval/generation modules under app/rag.
    """
    return {
        "rag_docs": [],
        "rag_answer": "",
        "rag_confidence": 0.0,
    }


def recommend_node(state: AgentState) -> dict[str, Any]:
    """Bridge existing recommendation engine into graph."""
    recommend_input = _build_recommend_input_from_state(state)
    if recommend_input is None:
        return {"recommend_input": None, "merged_candidates": []}

    merged = run_candidate_pipeline(recommend_input, trace=False)
    return {"recommend_input": recommend_input, "merged_candidates": merged}


def rerank_node(state: AgentState) -> dict[str, Any]:
    """Run production reranker on merged candidates."""
    recommend_input = state.get("recommend_input")
    merged = state.get("merged_candidates", [])
    if not recommend_input or not merged:
        return {"rerank_result": {"ranked_hotels": [], "ranked_items": []}, "ranked_recommendations": []}

    rerank_result = run_rerank_from_merged(
        inp=recommend_input,
        merged=merged,
        options=state.get("rerank_options"),
    )
    ranked_hotels = rerank_result.get("ranked_hotels", [])
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
        for item in ranked_hotels
    ]
    return {"rerank_result": rerank_result, "ranked_recommendations": ranked_recommendations}


def merge_result_node(state: AgentState) -> dict[str, Any]:
    """Merge RAG answer with ranked recommendations."""
    return {
        "final_response": {
            "answer": state.get("rag_answer", ""),
            "recommendations": state.get("ranked_recommendations", []),
            "sources": state.get("rag_docs", []),
        }
    }


def explain_node(state: AgentState) -> dict[str, Any]:
    """Add brief explanation text to final response."""
    recommendations = state.get("ranked_recommendations", [])
    explanation = "Gợi ý dựa trên mức độ phù hợp truy vấn và tín hiệu người dùng."
    if not recommendations:
        explanation = "Hiện chưa có gợi ý phù hợp, cần thêm thông tin để lọc tốt hơn."
    return {"explanation": explanation}


def format_response_node(state: AgentState) -> dict[str, Any]:
    """Standardize API response schema."""
    payload = dict(state.get("final_response", {}))
    payload["explanation"] = state.get("explanation", "")
    payload["intent"] = state.get("intent", "")
    payload["needs_clarification"] = state.get("needs_clarification", False)
    return {"final_response": payload}


def analytics_node(state: AgentState) -> dict[str, Any]:
    """Analytics hook placeholder for Kafka/Mongo logging."""
    return {}

