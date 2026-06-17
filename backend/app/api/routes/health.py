"""Health check endpoint — kiểm tra trạng thái tất cả subsystems."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


def _check_qu_pipeline() -> dict[str, Any]:
    """Trạng thái QueryUnderstandingPipeline singleton."""
    try:
        from app.agent.nodes import _pipeline, _pipeline_init_failed  # noqa: PLC0415
        if _pipeline_init_failed:
            return {"status": "failed", "detail": "init failed (see startup logs)"}
        if _pipeline is not None:
            return {"status": "ok", "detail": "initialized"}
        return {"status": "not_initialized", "detail": "lazy — will init on first request"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_llm_client() -> dict[str, Any]:
    """Trạng thái OpenAIResponsesClient (response_builder singleton)."""
    try:
        from app.agent.response_builder import _llm_client, _llm_init_failed  # noqa: PLC0415
        if _llm_init_failed:
            return {"status": "failed", "detail": "init failed — check OPENAI_API_KEY"}
        if _llm_client is not None:
            return {"status": "ok", "detail": "initialized"}
        return {"status": "not_initialized", "detail": "lazy — will init on first /chat call"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_openai_key() -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"status": "missing", "detail": "OPENAI_API_KEY not set"}
    masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
    return {"status": "present", "detail": masked}


def _check_recommendation_engine() -> dict[str, Any]:
    """Kiểm tra import recommendation engine (không kết nối DB)."""
    try:
        from app.recommendation.engine import run_candidate_pipeline  # noqa: F401, PLC0415
        return {"status": "ok", "detail": "importable"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_graph() -> dict[str, Any]:
    """Kiểm tra LangGraph workflow đã compile chưa."""
    try:
        from app.api.routes.chat import graph  # noqa: PLC0415
        if graph is not None:
            return {"status": "ok", "detail": "compiled"}
        return {"status": "not_compiled", "detail": "graph is None"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get(
    "",
    summary="Health check",
    description="Kiểm tra trạng thái tất cả subsystems: QU Pipeline, LLM, Recommendation Engine, LangGraph.",
)
async def health():
    checks = {
        "qu_pipeline": _check_qu_pipeline(),
        "llm_response_builder": _check_llm_client(),
        "openai_api_key": _check_openai_key(),
        "recommendation_engine": _check_recommendation_engine(),
        "langgraph": _check_graph(),
    }

    statuses = [v["status"] for v in checks.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "error" for s in statuses):
        overall = "degraded"
    elif any(s == "failed" for s in statuses):
        overall = "degraded"
    else:
        overall = "starting"

    return {"status": overall, "checks": checks}
