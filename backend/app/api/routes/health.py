"""Health endpoints — Kubernetes-style liveness + readiness probes.

GET /health/live   — Liveness probe: is the process alive?
                     Returns 200 as long as the process is running.
GET /health/ready  — Readiness probe: are all critical subsystems ready?
                     Returns 200 (ok) or 503 (degraded/starting).
GET /health        — Full detailed check (alias for /health/ready with full payload).
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])

# ── Check functions ───────────────────────────────────────────────────────────

def _check_qu_pipeline() -> dict[str, Any]:
    try:
        from app.agent.nodes import _pipeline, _pipeline_init_failed  # noqa: PLC0415
        if _pipeline_init_failed:
            return {"status": "failed", "detail": "init failed — check OPENAI_API_KEY"}
        if _pipeline is not None:
            return {"status": "ok", "detail": "initialized"}
        return {"status": "starting", "detail": "lazy — initializes on first request"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_llm_client() -> dict[str, Any]:
    try:
        from app.agent.response_builder import _llm_client, _llm_init_failed  # noqa: PLC0415
        if _llm_init_failed:
            return {"status": "failed", "detail": "init failed — check OPENAI_API_KEY"}
        if _llm_client is not None:
            return {"status": "ok", "detail": "initialized"}
        return {"status": "starting", "detail": "lazy — initializes on first request"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_openai_key() -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"status": "missing", "detail": "OPENAI_API_KEY not set"}
    # Show only prefix+suffix to confirm key presence without leaking
    masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    return {"status": "ok", "detail": masked}


def _check_recommendation_engine() -> dict[str, Any]:
    try:
        from app.recommendation.engine import run_candidate_pipeline  # noqa: F401, PLC0415
        return {"status": "ok", "detail": "importable"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_rag_system() -> dict[str, Any]:
    try:
        from app.agent.rag_adapter import _rag_chatbot, _rag_init_failed  # noqa: PLC0415
        if _rag_init_failed:
            return {"status": "failed", "detail": "init failed — check Qdrant/Neo4j"}
        if _rag_chatbot is not None:
            return {"status": "ok", "detail": "initialized"}
        return {"status": "starting", "detail": "lazy — initializes on first information query"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_mongodb() -> dict[str, Any]:
    try:
        from app.db.mongo.mongo_client import db  # noqa: PLC0415
        if db is None:
            return {"status": "failed", "detail": "db=None — check MONGO_URI"}
        # Ping to verify real connectivity
        db.client.admin.command("ping")
        return {"status": "ok", "detail": "connected"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_kafka() -> dict[str, Any]:
    try:
        from app.analytics.logging.logger import producer  # noqa: PLC0415
        if producer is None:
            return {"status": "failed", "detail": "producer=None — check KAFKA_URL"}
        return {"status": "ok", "detail": "connected"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_graph() -> dict[str, Any]:
    try:
        from app.api.routes.chat import graph  # noqa: PLC0415
        if graph is not None:
            return {"status": "ok", "detail": "compiled"}
        return {"status": "failed", "detail": "graph is None — compilation failed"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


# ── Critical subsystems (readiness depends on these) ─────────────────────────
# "optional" checks (Kafka, RAG) degrade gracefully; they don't block readiness.

def _run_all_checks() -> dict[str, dict[str, Any]]:
    return {
        "langgraph": _check_graph(),
        "openai_api_key": _check_openai_key(),
        "qu_pipeline": _check_qu_pipeline(),
        "llm_response_builder": _check_llm_client(),
        "recommendation_engine": _check_recommendation_engine(),
        "mongodb": _check_mongodb(),
        "rag_system": _check_rag_system(),
        "kafka": _check_kafka(),
    }


# Critical: if any of these fail, the service is not ready to serve traffic.
_CRITICAL = {"langgraph", "openai_api_key", "mongodb"}

OverallStatus = Literal["ok", "degraded", "starting"]


def _derive_overall(checks: dict[str, dict[str, Any]]) -> OverallStatus:
    critical_statuses = {k: checks[k]["status"] for k in _CRITICAL if k in checks}
    all_statuses = [v["status"] for v in checks.values()]

    # Any critical system has failed/errored → not ready
    if any(s in ("error", "failed", "missing") for s in critical_statuses.values()):
        return "degraded"
    # Some non-critical systems still initializing
    if any(s == "starting" for s in all_statuses):
        return "starting"
    # All systems ok
    if all(s == "ok" for s in all_statuses):
        return "ok"
    # Non-critical degraded but critical are ok → still "ok" for readiness
    return "ok"


# ── Response model ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: OverallStatus
    checks: dict[str, dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/live",
    summary="Liveness probe",
    description="Returns 200 if the process is alive. No subsystem checks.",
    include_in_schema=True,
)
async def liveness():
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description=(
        "Returns 200 when all **critical** subsystems are ready.\n\n"
        "Returns 503 when the service is degraded (critical subsystem failure).\n\n"
        "Critical: `langgraph`, `openai_api_key`, `mongodb`."
    ),
)
async def readiness(http_response: Response) -> HealthResponse:
    checks = _run_all_checks()
    overall = _derive_overall(checks)

    if overall == "degraded":
        http_response.status_code = 503

    return HealthResponse(status=overall, checks=checks)


@router.get(
    "",
    response_model=HealthResponse,
    summary="Full health check",
    description="Alias for /health/ready — returns full subsystem status.",
)
async def health(http_response: Response) -> HealthResponse:
    return await readiness(http_response)
