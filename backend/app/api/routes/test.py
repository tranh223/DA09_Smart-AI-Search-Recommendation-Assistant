"""Test endpoints — isolated module testing for development/QA.

**These endpoints are disabled in production.**
Enable via env: ENABLE_TEST_ENDPOINTS=true

All endpoints bypass LangGraph and call modules directly,
which makes it easy to isolate failures by layer.

Endpoints:
  POST /test/query-understanding  — test QU Pipeline
  POST /test/recommend            — test Candidate Generation
  POST /test/rerank               — test full Recommend + Rerank
  POST /test/response-builder     — test LLM Response Builder
  POST /test/full                 — run full graph, return complete AgentState (debug)
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["test / debug"])


# ── Request models ────────────────────────────────────────────────────────────

class QURequest(BaseModel):
    query: str = Field(..., examples=["Tìm khách sạn 4 sao ở Đà Nẵng gần biển, 2 người, ngân sách 2 triệu"])
    user_id: str = Field(default="test_user")
    user_profile: dict[str, Any] = Field(
        default_factory=dict,
        description="Có thể để {} để test với profile trống.",
        examples=[{"session_context": {"destination": "Đà Nẵng", "check_in": "2026-07-15"}}],
    )
    chat_history: list[dict[str, str]] = Field(
        default_factory=list,
        description='[{"role": "user", "content": "..."}]',
    )


class RecommendRequest(BaseModel):
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
    query: str = Field(..., examples=["Tìm khách sạn ở Hội An cho cặp đôi"])
    intent: str = Field(default="hotel_search")
    destination: str = Field(default="")
    rag_answer: str = Field(default="")
    recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        examples=[[
            {
                "hotel_id": "101",
                "hotel_name": "Anantara Hoi An Resort",
                "score": 0.92,
                "reasons": ["Vị trí trung tâm phố cổ", "Hồ bơi ngoài trời"],
                "metadata": {"price_min": 1500000, "price_max": 3000000},
            },
        ]],
    )


class FullGraphRequest(BaseModel):
    """Full graph debug — same input shape as /chat but returns full AgentState."""

    user_id: str = Field(default="test_user")
    session_id: str = Field(default="test_session")
    query: str = Field(default="Tìm khách sạn ở Đà Nẵng", min_length=1)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    slots: dict[str, Any] = Field(default_factory=dict)
    rerank_options: dict[str, Any] = Field(default_factory=dict)


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
            session_price_range=(
                PriceRange(max=req.budget_max) if req.budget_max else PriceRange()
            ),
        ),
        original_query=req.query or req.destination,
        limit_per_source=req.limit,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/query-understanding",
    summary="Test: Query Understanding Pipeline",
    description=(
        "Calls QueryUnderstandingPipeline directly. "
        "Returns intent, slots, slot_is_complete, and full qu_trace. "
        "Does **not** run recommendation."
    ),
)
async def test_query_understanding(req: QURequest):
    from app.agent.nodes import _get_pipeline  # noqa: PLC0415
    from app.agent.qu_adapter import pipeline_result_to_state  # noqa: PLC0415

    pipeline = _get_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="QueryUnderstandingPipeline unavailable — check OPENAI_API_KEY and startup logs.",
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
        logger.error("[test/qu] pipeline.run failed: %s", exc, exc_info=True)
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
    summary="Test: Candidate Generation",
    description=(
        "Calls Candidate Generation (embedding + trending + personalization) directly. "
        "Bypasses QU Pipeline. Tests Qdrant, MongoDB, Neo4j connectivity."
    ),
)
async def test_recommend(req: RecommendRequest):
    from app.recommendation.engine import run_candidate_pipeline  # noqa: PLC0415

    inp = _build_recommend_input(req)

    t0 = time.perf_counter()
    try:
        merged = run_candidate_pipeline(inp, trace=False)
    except Exception as exc:
        logger.error("[test/recommend] candidate pipeline failed: %s", exc, exc_info=True)
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
    summary="Test: Recommend + Rerank Pipeline",
    description=(
        "Runs full Candidate Generation → Merge → Rerank. "
        "Bypasses QU Pipeline. Returns ranked hotel list."
    ),
)
async def test_rerank(req: RecommendRequest):
    from app.recommendation.engine import run_candidate_pipeline, run_rerank_from_merged  # noqa: PLC0415

    inp = _build_recommend_input(req)

    t0 = time.perf_counter()
    try:
        merged = run_candidate_pipeline(inp, trace=False)
    except Exception as exc:
        logger.error("[test/rerank] candidate pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Candidate pipeline error: {exc}") from exc

    t1 = time.perf_counter()
    try:
        rerank_result = run_rerank_from_merged(inp=inp, merged=merged)
    except Exception as exc:
        logger.error("[test/rerank] rerank failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rerank error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    rerank_ms = round((time.perf_counter() - t1) * 1000)

    ranked: list[dict] = rerank_result.get("ranked_hotels") or []
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
    summary="Test: LLM Response Builder",
    description=(
        "Calls LLM Response Builder directly with custom data. "
        "Use to evaluate synthesis quality and explanation generation."
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
        logger.error("[test/response-builder] failed: %s", exc, exc_info=True)
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
    summary="Test: Full Graph (debug)",
    description=(
        "Runs the complete LangGraph workflow (same as `/chat`) but returns "
        "the **full AgentState** instead of just `final_response`. "
        "Use for end-to-end debugging and state inspection."
    ),
)
async def test_full(req: FullGraphRequest):
    from app.api.routes.chat import _merge_slots_into_profile, graph  # noqa: PLC0415

    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not available — compilation failed.")

    profile: dict[str, Any] = {**req.user_profile, "user_id": req.user_id}
    if req.slots:
        profile = _merge_slots_into_profile(profile, req.slots)

    state: dict[str, Any] = {
        "user_id": req.user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        "user_profile": profile,
        "slots": req.slots,
        "rerank_options": req.rerank_options,
        "request_started_at": time.perf_counter(),
    }

    t0 = time.perf_counter()
    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        logger.error("[test/full] graph.ainvoke failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph error: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    # Serialize — strip non-JSON-serializable Pydantic objects
    safe: dict[str, Any] = {}
    for k, v in result.items():
        if k == "recommend_input" and v is not None:
            safe[k] = v.model_dump()
        elif k == "merged_candidates" and v:
            safe[k] = [c.model_dump() for c in v]
        else:
            safe[k] = v

    return {
        "elapsed_ms": elapsed_ms,
        "latency_summary": safe.get("latency_summary"),
        "state": safe,
    }
