"""Chat endpoint — main production entry point."""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re as _re
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.agent.graph import build_graph
from app.agent.tracer import log_flow_end, log_flow_start
from app.api.middleware import get_request_id
from app.api.models import APIResponse
from app.auth.dependencies import get_current_user_dep
from app.core.trace import FlowTrace, reset_trace, set_current_trace

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
    """Main chat request body.

    Note: ``user_id`` is no longer accepted in the body.
    It is extracted automatically from the JWT Bearer token.
    """

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

    # Number of raw candidates to request from each recommendation source.
    # Kept separate from rerank_options.top_k, which controls final ranked output size.
    candidate_limit_per_source: int = Field(default=10, ge=1, le=50)

    rerank_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def session_id_not_blank(cls, v: str) -> str:
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
async def chat(
    req: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user_dep),
) -> APIResponse:
    req_id = get_request_id()
    # user_id is extracted from JWT token, not from request body
    user_id: str = current_user["account"]["user_id"]

    if graph is None:
        logger.error("[%s] graph is None — compilation failed at startup", req_id)
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: workflow engine failed to initialize.",
        )

    fallback_user_profile: dict[str, Any] = {**req.user_profile, "user_id": user_id}
    if req.slots:
        fallback_user_profile = _merge_slots_into_profile(fallback_user_profile, req.slots)

    state: dict[str, Any] = {
        "request_id": req_id,
        "user_id": user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        # Backward-compatible seed only. session_node replaces this with
        # server-side state from MongoDB when available.
        "user_profile": fallback_user_profile,
        "slots": req.slots,
        "candidate_limit_per_source": req.candidate_limit_per_source,
        "rerank_options": req.rerank_options,
        "request_started_at": time.perf_counter(),
    }

    # ── Khởi tạo FlowTrace cho toàn bộ request ───────────────────────────────
    flow_trace = FlowTrace(
        request_id=req_id,
        user_id=user_id,
        session_id=req.session_id,
        query=req.query,
    )
    trace_token = set_current_trace(flow_trace)
    log_flow_start(req_id, user_id, req.session_id, req.query)

    t0 = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(state),
            timeout=CHAT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[%s] chat timeout after %ds for user=%s query='%.80s'",
            req_id, CHAT_TIMEOUT_SECONDS, user_id, req.query,
        )
        flow_trace.log_end(needs_clarify=False, intent="timeout", n_recs=0)
        flow_trace.finalize()
        reset_trace(trace_token)
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {CHAT_TIMEOUT_SECONDS}s.",
        )
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "[%s] graph.ainvoke failed after %dms for user=%s: %s",
            req_id, elapsed, user_id, exc, exc_info=True,
        )
        flow_trace.log_end(needs_clarify=False, intent="error", n_recs=0)
        flow_trace.finalize()
        reset_trace(trace_token)
        raise HTTPException(status_code=500, detail="Pipeline execution failed.") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    final_response: dict[str, Any] = result.get("final_response") or {}
    data = _build_chat_data(final_response)

    # log_flow_end + finalize JSON trace
    log_flow_end(req_id, elapsed_ms, result)
    reset_trace(trace_token)

    return APIResponse.ok(data=data.model_dump(), request_id=req_id, latency_ms=elapsed_ms)


# ── Streaming helpers ─────────────────────────────────────────────────────────

def _sse(event: dict) -> str:
    """Encode một dict thành SSE data line."""
    return f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"


# ── /chat/stream endpoint ─────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Chat — Server-Sent Events streaming",
    description=(
        "Phiên bản streaming của /chat.\n\n"
        "Trả về `text/event-stream` với các event JSON:\n\n"
        "- `{type: 'status', message}` — trạng thái đang xử lý\n"
        "- `{type: 'delta', text}` — từng token answer (Markdown)\n"
        "- `{type: 'metadata', recommendations, next_suggestions, ...}` — kết quả đầy đủ\n"
        "- `{type: 'done'}` — kết thúc stream\n"
        "- `{type: 'error', message}` — lỗi (nếu có)\n\n"
        "Graph pipeline chạy đầy đủ (session → intent → rag/recommend → rerank → "
        "response_builder → analytics). Sau khi graph hoàn thành, answer được "
        "stream từng token qua OpenAI text streaming. Metadata trả cuối stream."
    ),
)
async def chat_stream(
    req: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user_dep),
) -> StreamingResponse:
    req_id = get_request_id()
    user_id: str = current_user["account"]["user_id"]

    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: workflow engine failed to initialize.",
        )

    fallback_user_profile: dict[str, Any] = {**req.user_profile, "user_id": user_id}
    if req.slots:
        fallback_user_profile = _merge_slots_into_profile(fallback_user_profile, req.slots)

    state: dict[str, Any] = {
        "request_id": req_id,
        "user_id": user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        "user_profile": fallback_user_profile,
        "slots": req.slots,
        "candidate_limit_per_source": req.candidate_limit_per_source,
        "rerank_options": req.rerank_options,
        "request_started_at": time.perf_counter(),
    }

    async def event_generator():
        t0 = time.perf_counter()
        flow_trace = FlowTrace(
            request_id=req_id,
            user_id=user_id,
            session_id=req.session_id,
            query=req.query,
        )
        trace_token = set_current_trace(flow_trace)
        log_flow_start(req_id, user_id, req.session_id, req.query)

        # ── Bước 1: chạy graph, gửi status trong lúc chờ ─────────────────────
        try:
            yield _sse({"type": "status", "message": "Đang phân tích yêu cầu..."})

            graph_task = asyncio.create_task(
                asyncio.wait_for(
                    graph.ainvoke(state),
                    timeout=CHAT_TIMEOUT_SECONDS,
                )
            )

            _status_queue = [
                "Đang tổng hợp câu trả lời...",
            ]
            for _msg in _status_queue:
                done, _ = await asyncio.wait({graph_task}, timeout=3.0)
                if done:
                    break
                yield _sse({"type": "status", "message": _msg})

            result = await graph_task

        except asyncio.TimeoutError:
            yield _sse({"type": "error", "message": "Yêu cầu hết thời gian, vui lòng thử lại."})
            yield _sse({"type": "done"})
            flow_trace.log_end(needs_clarify=False, intent="timeout", n_recs=0)
            flow_trace.finalize()
            reset_trace(trace_token)
            return
        except Exception as exc:
            logger.error("[%s] chat_stream graph failed: %s", req_id, exc, exc_info=True)
            yield _sse({"type": "error", "message": "Đã xảy ra lỗi khi xử lý yêu cầu."})
            yield _sse({"type": "done"})
            flow_trace.log_end(needs_clarify=False, intent="error", n_recs=0)
            flow_trace.finalize()
            reset_trace(trace_token)
            return

        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        final_response: dict[str, Any] = result.get("final_response") or {}
        data = _build_chat_data(final_response)

        # ── Bước 2: stream answer từng token từ LLM ──────────────────────────
        # Dùng build_response_stream_with_llm() để gọi OpenAI streaming thật.
        # Chạy sync generator trong thread riêng để không block event loop.
        from app.agent.response_builder import build_response_stream_with_llm  # noqa: PLC0415

        rag_answer: str = result.get("rag_answer") or ""
        intent: str = data.intent or ""
        destination: str = (
            (result.get("user_profile") or {})
            .get("session_context", {})
            .get("destination", "")
            or ""
        )
        ranked_recs: list[dict[str, Any]] = data.recommendations or []

        token_queue: asyncio.Queue = asyncio.Queue()
        _SENTINEL = object()

        def _produce_tokens() -> None:
            try:
                for token in build_response_stream_with_llm(
                    query=req.query,
                    intent=intent,
                    destination=destination,
                    rag_answer=rag_answer,
                    ranked_recommendations=ranked_recs,
                ):
                    loop.call_soon_threadsafe(token_queue.put_nowait, token)
            except Exception as _exc:
                logger.warning("[%s] stream token producer error: %s", req_id, _exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, _SENTINEL)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _produce_tokens)

        while True:
            token = await token_queue.get()
            if token is _SENTINEL:
                break
            yield _sse({"type": "delta", "text": token})

        # ── Bước 3: metadata đầy đủ ──────────────────────────────────────────
        yield _sse({
            "type": "metadata",
            "intent": data.intent,
            "recommendations": data.recommendations,
            "sources": data.sources,
            "next_suggestions": data.next_suggestions,
            "needs_clarification": data.needs_clarification,
            "clarification_question": data.clarification_question,
            "explanation": data.explanation,
            "latency": data.latency,
        })

        yield _sse({"type": "done"})

        log_flow_end(req_id, elapsed_ms, result)
        reset_trace(trace_token)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
