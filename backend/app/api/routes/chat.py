"""Chat endpoint — main production entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.agent.graph import build_graph
from app.agent.tracer import log_flow_end, log_flow_start
from app.api.middleware import get_request_id
from app.api.models import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# LangGraph compiled app — built once at import time (thread-safe, read-only after compile)
try:
    graph = build_graph()
    logger.info("[chat] LangGraph compiled successfully.")
except Exception as _graph_exc:
    graph = None
    logger.error("[chat] LangGraph compilation failed: %s", _graph_exc, exc_info=True)

CHAT_TIMEOUT_SECONDS = int(os.getenv("CHAT_TIMEOUT_SECONDS", "90"))


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Main chat request body."""

    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=2000)

    # Full user profile — passed to QueryUnderstandingPipeline.
    # Minimum: {} (pipeline creates an empty profile with user_id).
    # Full format:
    #   {
    #     "long_term_profile": {"nationality": "VN", ...},
    #     "session_context": {"destination": "Hà Nội", "check_in": "2026-07-01", ...}
    #   }
    user_profile: dict[str, Any] = Field(default_factory=dict)

    # slots: backward-compat for older clients that don't send user_profile.
    # Values are injected into session_context only when destination is missing.
    slots: dict[str, Any] = Field(default_factory=dict)

    rerank_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v.strip()

    @field_validator("user_id", "session_id")
    @classmethod
    def ids_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ChatData(BaseModel):
    """Payload inside APIResponse.data for a successful chat."""

    answer: str = ""
    intent: str = ""
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    next_suggestions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    explanation: str = ""
    latency: dict[str, Any] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _merge_slots_into_profile(
    user_profile: dict[str, Any],
    slots: dict[str, Any],
) -> dict[str, Any]:
    """Inject slots into session_context for backward-compat clients.

    Creates new dict instances — never mutates the original Pydantic objects.
    Slots do not overwrite values already present in session_context.
    """
    session = dict(user_profile.get("session_context") or {})

    for key in (
        "destination", "check_in", "check_out",
        "number_of_guests", "has_pet", "has_children", "nearby_place",
    ):
        if key not in session and slots.get(key) is not None:
            session[key] = slots[key]

    price = dict(session.get("session_price_range") or {})
    if "min" not in price and slots.get("budget_min") is not None:
        price["min"] = slots["budget_min"]
    if "max" not in price and slots.get("budget_max") is not None:
        price["max"] = slots["budget_max"]
    if price:
        session["session_price_range"] = price

    return {**user_profile, "session_context": session}


def _build_chat_data(final_response: dict[str, Any]) -> ChatData:
    """Map AgentState.final_response → ChatData."""
    return ChatData(
        answer=final_response.get("answer") or "",
        intent=final_response.get("intent") or "",
        recommendations=final_response.get("recommendations") or [],
        sources=final_response.get("sources") or [],
        next_suggestions=final_response.get("next_suggestions") or [],
        needs_clarification=bool(final_response.get("needs_clarification")),
        clarification_question=final_response.get("clarification_question") or "",
        explanation=final_response.get("explanation") or "",
        latency=final_response.get("latency"),
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse,
    summary="Chat — main AI search & recommendation",
    description=(
        "Runs the full LangGraph pipeline:\n\n"
        "1. `session_node` — load memory from MongoDB\n"
        "2. `intent_node` — QueryUnderstandingPipeline (guardrail → NLP → FAISS → Neo4j)\n"
        "3. `slot_check_node` — route to clarification or recommendation\n"
        "4. `rag_node` + `recommend_node` — parallel retrieval\n"
        "5. `rerank_node` — rule + LLM reranking\n"
        "6. `response_builder_node` — GPT-4o-mini synthesis\n"
        "7. `analytics_node` — Kafka logging\n\n"
        "Returns a structured response with ranked hotels, AI-generated explanation, "
        "next-step suggestions, and per-stage latency."
    ),
)
async def chat(req: ChatRequest, request: Request) -> APIResponse:
    req_id = get_request_id()

    if graph is None:
        logger.error("[%s] graph is None — compilation failed at startup", req_id)
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: workflow engine failed to initialize.",
        )

    user_profile: dict[str, Any] = {**req.user_profile, "user_id": req.user_id}
    if req.slots:
        user_profile = _merge_slots_into_profile(user_profile, req.slots)

    state: dict[str, Any] = {
        "request_id": req_id,
        "user_id": req.user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        "user_profile": user_profile,
        "slots": req.slots,
        "rerank_options": req.rerank_options,
        "request_started_at": time.perf_counter(),
    }

    log_flow_start(req_id, req.user_id, req.session_id, req.query)

    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(state),
            timeout=CHAT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[%s] chat timeout after %ds for user=%s query='%.80s'",
            req_id, CHAT_TIMEOUT_SECONDS, req.user_id, req.query,
        )
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {CHAT_TIMEOUT_SECONDS}s.",
        )
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "[%s] graph.ainvoke failed after %dms for user=%s: %s",
            req_id, elapsed, req.user_id, exc, exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Pipeline execution failed.") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    final_response: dict[str, Any] = result.get("final_response") or {}
    data = _build_chat_data(final_response)

    log_flow_end(req_id, elapsed_ms, result)

    return APIResponse.ok(data=data.model_dump(), request_id=req_id, latency_ms=elapsed_ms)
