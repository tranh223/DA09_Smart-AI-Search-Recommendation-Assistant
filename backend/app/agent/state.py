"""Shared state for the OTA LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from typing_extensions import Annotated

from app.agent.latency import merge_latency_trace
from app.recommendation.models import MergedCandidate, RecommendInput

LatencyTrace = Annotated[dict[str, float], merge_latency_trace]


class AgentState(TypedDict, total=False):
    # ── Request / session ────────────────────────────────────────────────────
    request_id: str          # UUIDv4 hex từ RequestIDMiddleware — dùng để trace log
    user_id: str
    session_id: str
    conversation_id: str
    raw_query: str
    # time.perf_counter() tại thời điểm nhận request — dùng để tính total_ms
    request_started_at: float
    # Annotated với merge_latency_trace reducer — cho phép parallel nodes cùng ghi
    latency_trace: LatencyTrace
    latency_summary: dict[str, Any]

    # Raw user profile dict từ client — được coerce sang QU UserProfile
    # bởi QueryUnderstandingPipeline._coerce_user_profile()
    user_profile: dict[str, Any]

    # ── Context memory ───────────────────────────────────────────────────────
    chat_history: list[dict[str, Any]]
    conversation_summary: str

    # ── Query understanding (set bởi intent_node) ────────────────────────────
    intent: str
    slots: dict[str, Any]
    slot_is_complete: bool
    rewritten_query: str
    needs_clarification: bool
    clarification_question: str
    clarification_missing_fields: list[str]

    # Trace đầy đủ từ QueryUnderstandingPipeline — dùng cho debug / analytics
    qu_trace: dict[str, Any]
    updated_user_profile: dict[str, Any]

    # ── Recommend pipeline ───────────────────────────────────────────────────
    recommend_input: RecommendInput
    merged_candidates: list[MergedCandidate]
    ranked_recommendations: list[dict[str, Any]]
    candidate_limit_per_source: int
    rerank_options: dict[str, Any]
    rerank_result: dict[str, Any]

    # ── RAG pipeline ─────────────────────────────────────────────────────────
    rag_docs: list[dict[str, Any]]
    rag_answer: str
    rag_confidence: float

    # ── Response Builder (set bởi response_builder_node) ────────────────────
    # LLM tổng hợp từ RAG answer + ranked recommendations
    synthesized_answer: str
    # {hotel_id → lý do cụ thể tại sao phù hợp} — được embed vào từng rec bởi explain_node
    hotel_reasons: dict[str, str]
    # Gợi ý câu hỏi tiếp theo để người dùng tinh chỉnh
    next_suggestions: list[str]

    # ── Final response ───────────────────────────────────────────────────────
    explanation: str
    final_response: dict[str, Any]
    error: str

