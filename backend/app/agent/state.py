"""Shared state for the OTA LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from app.recommendation.models import MergedCandidate, RecommendInput


class AgentState(TypedDict, total=False):
    # Request/session
    user_id: str
    session_id: str
    conversation_id: str
    raw_query: str

    # Context memory
    chat_history: list[dict[str, Any]]
    conversation_summary: str

    # Query understanding
    intent: str
    slots: dict[str, Any]
    slot_is_complete: bool
    rewritten_query: str
    needs_clarification: bool
    clarification_question: str

    # Recommend pipeline
    recommend_input: RecommendInput
    merged_candidates: list[MergedCandidate]
    ranked_recommendations: list[dict[str, Any]]
    rerank_options: dict[str, Any]
    rerank_result: dict[str, Any]
    rerank_result: dict[str, Any]

    # RAG pipeline
    rag_docs: list[dict[str, Any]]
    rag_answer: str
    rag_confidence: float

    # Final response
    explanation: str
    final_response: dict[str, Any]
    error: str

