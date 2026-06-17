"""Test endpoints — gọi trực tiếp từng module để debug/kiểm tra hệ thống.

Tất cả endpoint ở đây bypass LangGraph và gọi module thẳng,
giúp isolate vấn đề ở từng tầng riêng lẻ.

Endpoints:
  POST /test/query-understanding  — test QU Pipeline
  POST /test/recommend            — test Candidate Generation + Merge
  POST /test/rerank               — test full Recommend + Rerank
  POST /test/response-builder     — test LLM Response Builder
  POST /test/full                 — chạy toàn bộ graph, trả về full state (debug)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.recommendation.models import (
    PriceRange,
    Profile,
    RecommendInput,
    SessionContext,
)

router = APIRouter(prefix="/test", tags=["test"])


# ── Request models ────────────────────────────────────────────────────────────

class QURequest(BaseModel):
    """Input cho test Query Understanding Pipeline."""
    query: str = Field(..., examples=["Tìm khách sạn 4 sao ở Đà Nẵng gần biển, 2 người, ngân sách 2 triệu"])
    user_id: str = Field(default="test_user")
    user_profile: dict[str, Any] = Field(
        default_factory=dict,
        description="Profile người dùng. Có thể để {} để test với profile trống.",
        examples=[{
            "session_context": {
                "destination": "Đà Nẵng",
                "check_in": "2026-07-15",
                "check_out": "2026-07-18",
            }
        }],
    )
    chat_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Lịch sử hội thoại. [{\"role\": \"user\", \"content\": \"...\"}]",
    )


class RecommendRequest(BaseModel):
    """Input cho test Candidate Generation / Rerank (bỏ qua QU Pipeline)."""
    user_id: str = Field(default="test_user")
    query: str = Field(default="", examples=["khách sạn gần biển Mỹ Khê"])
    destination: str = Field(..., examples=["Đà Nẵng"])
    check_in: str | None = Field(default=None, examples=["2026-07-15"])
    check_out: str | None = Field(default=None, examples=["2026-07-18"])
    number_of_guests: int | None = Field(default=None, examples=[2])
    budget_max: float | None = Field(default=None, examples=[2000000])
    nearby_place: str | None = Field(default=None, examples=["Cầu Rồng"])
    has_children: bool | None = None
    has_pet: bool | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ResponseBuilderRequest(BaseModel):
    """Input cho test LLM Response Builder."""
    query: str = Field(..., examples=["Tìm khách sạn ở Hội An cho cặp đôi"])
    intent: str = Field(default="hotel_search")
    destination: str = Field(default="")
    rag_answer: str = Field(default="", description="Câu trả lời RAG (có thể để trống)")
    recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Danh sách gợi ý giả lập. Để [] để test với list rỗng.",
        examples=[[
            {
                "hotel_id": "101",
                "hotel_name": "Anantara Hoi An Resort",
                "score": 0.92,
                "reasons": ["Vị trí trung tâm phố cổ", "Hồ bơi ngoài trời"],
                "metadata": {"price_min": 1500000, "price_max": 3000000},
            },
            {
                "hotel_id": "102",
                "hotel_name": "Silk Sense Hoi An River Resort",
                "score": 0.87,
                "reasons": ["Bên sông Thu Bồn", "Bữa sáng included"],
                "metadata": {"price_min": 900000, "price_max": 1800000},
            },
        ]],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_recommend_input(req: RecommendRequest) -> RecommendInput:
    return RecommendInput(
        user_id=req.user_id,
        profile=Profile(),
        session_context=SessionContext(
            destination=req.destination,
            check_in=req.check_in,
            check_out=req.check_out,
            number_of_guests=req.number_of_guests,
            nearby_place=req.nearby_place,
            has_children=req.has_children,
            has_pet=req.has_pet,
            session_price_range=PriceRange(max=req.budget_max) if req.budget_max else PriceRange(),
        ),
        original_query=req.query or req.destination,
        limit_per_source=req.limit,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/query-understanding",
    summary="Test Query Understanding Pipeline",
    description=(
        "Gọi trực tiếp QueryUnderstandingPipeline. "
        "Trả về intent, slots, slot_is_complete và toàn bộ qu_trace để debug. "
        "**Không** chạy recommendation."
    ),
)
async def test_query_understanding(req: QURequest):
    from app.agent.nodes import _get_pipeline  # noqa: PLC0415
    from app.agent.qu_adapter import pipeline_result_to_state  # noqa: PLC0415

    pipeline = _get_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="QueryUnderstandingPipeline not available (check OPENAI_API_KEY and startup logs).",
        )

    user_profile = {**req.user_profile, "user_id": req.user_id}

    t0 = time.perf_counter()
    try:
        result = pipeline.run(
            query=req.query,
            user_profile_input=user_profile,
            conversation_history=req.chat_history,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    state = pipeline_result_to_state(result, query=req.query, limit_per_source=10)

    return {
        "elapsed_ms": elapsed_ms,
        "intent": state["intent"],
        "slots": state["slots"],
        "slot_is_complete": state["slot_is_complete"],
        "needs_clarification": state["needs_clarification"],
        "clarification_question": state.get("clarification_question"),
        "clarification_missing_fields": state.get("clarification_missing_fields"),
        "recommend_input_built": state.get("recommend_input") is not None,
        "qu_trace": state.get("qu_trace"),
    }


@router.post(
    "/recommend",
    summary="Test Candidate Generation",
    description=(
        "Gọi trực tiếp Candidate Generation (embedding + trending + personalization). "
        "Bỏ qua QU Pipeline — dùng để test DB (Qdrant, MongoDB, Neo4j) và logic nguồn ứng viên."
    ),
)
async def test_recommend(req: RecommendRequest):
    from app.recommendation.engine import run_candidate_pipeline  # noqa: PLC0415

    inp = _build_recommend_input(req)

    t0 = time.perf_counter()
    try:
        merged = run_candidate_pipeline(inp, trace=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Candidate pipeline error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    by_source: dict[str, int] = {}
    for c in merged:
        for src in (c.sources if hasattr(c, "sources") else []):
            by_source[src] = by_source.get(src, 0) + 1

    return {
        "elapsed_ms": elapsed_ms,
        "merged_count": len(merged),
        "by_source": by_source,
        "candidates": [
            {
                "hotel_id": c.hotel_id,
                "hotel_name": c.hotel_name,
                "sources": c.sources,
                "pre_rank_score": round(c.pre_rank_score, 4),
                "reasons": c.reasons,
            }
            for c in merged
        ],
    }


@router.post(
    "/rerank",
    summary="Test Recommend + Rerank Pipeline",
    description=(
        "Chạy đầy đủ Candidate Generation → Merge → Rerank. "
        "Bỏ qua QU Pipeline. Trả về danh sách khách sạn đã được xếp hạng."
    ),
)
async def test_rerank(req: RecommendRequest):
    from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged  # noqa: PLC0415

    inp = _build_recommend_input(req)

    t0 = time.perf_counter()
    try:
        merged = run_candidate_pipeline(inp, trace=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Candidate pipeline error: {exc}") from exc

    t1 = time.perf_counter()
    try:
        rerank_result = run_rerank_from_merged(inp=inp, merged=merged)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rerank error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    rerank_ms = round((time.perf_counter() - t1) * 1000)

    ranked = rerank_result.get("ranked_hotels") or []
    return {
        "elapsed_ms": elapsed_ms,
        "rerank_ms": rerank_ms,
        "candidate_count": len(merged),
        "ranked_count": len(ranked),
        "ranked_hotels": [
            {
                "rank": h.get("rank"),
                "hotel_id": h.get("hotel_id") or h.get("item_id"),
                "hotel_name": h.get("name"),
                "final_score": round(h.get("final_score", 0), 4),
                "base_score": round(h.get("base_score", 0), 4),
                "llm_score": h.get("llm_score"),
                "sources": h.get("sources", []),
                "reasons": h.get("reasons", []),
                "warnings": h.get("warnings", []),
                "price_min": h.get("price_min"),
                "price_max": h.get("price_max"),
            }
            for h in ranked
        ],
    }


@router.post(
    "/response-builder",
    summary="Test LLM Response Builder",
    description=(
        "Gọi trực tiếp LLM Response Builder với dữ liệu tuỳ chỉnh. "
        "Dùng để kiểm tra chất lượng tổng hợp kết quả và giải thích lý do."
    ),
)
async def test_response_builder(req: ResponseBuilderRequest):
    from app.agent.response_builder import build_response_with_llm  # noqa: PLC0415

    t0 = time.perf_counter()
    try:
        result = build_response_with_llm(
            query=req.query,
            intent=req.intent,
            destination=req.destination,
            rag_answer=req.rag_answer,
            ranked_recommendations=req.recommendations,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Response builder error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "elapsed_ms": elapsed_ms,
        "synthesized_answer": result.get("synthesized_answer"),
        "hotel_reasons": result.get("hotel_reasons"),
        "next_suggestions": result.get("next_suggestions"),
    }


@router.post(
    "/full",
    summary="Full Graph — Debug Mode",
    description=(
        "Chạy toàn bộ LangGraph workflow (giống /chat) nhưng trả về "
        "full AgentState thay vì chỉ `final_response`. "
        "Dùng để debug end-to-end, kiểm tra từng field trong state."
    ),
)
async def test_full(
    user_id: str = "test_user",
    session_id: str = "test_session",
    query: str = "Tìm khách sạn ở Đà Nẵng",
    user_profile: dict[str, Any] | None = None,
    slots: dict[str, Any] | None = None,
    rerank_options: dict[str, Any] | None = None,
):
    from app.api.routes.chat import _merge_slots_into_profile, graph  # noqa: PLC0415

    profile = dict(user_profile or {})
    profile["user_id"] = user_id

    if slots:
        profile = _merge_slots_into_profile(profile, slots)

    state = {
        "user_id": user_id,
        "session_id": session_id,
        "raw_query": query,
        "user_profile": profile,
        "slots": slots or {},
        "rerank_options": rerank_options or {},
    }

    t0 = time.perf_counter()
    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    # Serialize — loại bỏ các object Pydantic không JSON-serializable
    safe_result: dict[str, Any] = {}
    for k, v in result.items():
        if k == "recommend_input" and v is not None:
            # RecommendInput Pydantic — serialize
            safe_result[k] = v.model_dump()
        elif k == "merged_candidates" and v:
            safe_result[k] = [c.model_dump() for c in v]
        else:
            safe_result[k] = v

    return {"elapsed_ms": elapsed_ms, "state": safe_result}
