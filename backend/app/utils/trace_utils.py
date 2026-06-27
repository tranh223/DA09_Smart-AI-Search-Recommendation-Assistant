from __future__ import annotations

import json
import logging
import os
from typing import Any

try:
    from app.api.middleware import get_request_id
except Exception:  # pragma: no cover - standalone smoke scripts
    def get_request_id() -> str:
        return ""

try:
    from utils.trace_langsmith import rag_langsmith_span
except Exception:  # pragma: no cover - standalone app/rag script mode
    from utils.trace_langsmith import rag_langsmith_span


logger = logging.getLogger("ota.flow")
_rag_logger = logging.getLogger("ota.rag")


def _req_prefix() -> str:
    rid = ""
    try:
        rid = get_request_id()
    except Exception:
        rid = ""
    if not rid:
        return "[no-req]"
    return f"[{rid[:16]}]"


def _enabled() -> bool:
    # default on in debug/development; off in production unless explicitly enabled
    v = os.getenv("RAG_TRACE_ENABLED", "true").lower()
    return v in {"1", "true", "yes", "on"}


def _safe_preview(obj: Any, *, max_chars: int = 3000, max_items: int = 50) -> Any:
    """Return a JSON-friendly preview to avoid huge logs."""

    if obj is None:
        return None

    if isinstance(obj, str):
        if len(obj) <= max_chars:
            return obj
        return obj[:max_chars] + f"...[truncated {len(obj) - max_chars} chars]"

    if isinstance(obj, (int, float, bool)):
        return obj

    if isinstance(obj, list):
        out = []
        for i, it in enumerate(obj):
            if i >= max_items:
                out.append(f"...[truncated {len(obj) - max_items} items]")
                break
            out.append(_safe_preview(it, max_chars=max_chars, max_items=max_items))
        return out

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(obj.items()):
            if i >= max_items:
                out["__truncated__"] = f"truncated {len(obj) - max_items} keys"
                break
            ks = str(k)
            out[ks] = _safe_preview(v, max_chars=max_chars, max_items=max_items)
        return out

    # unknown types
    try:
        s = str(obj)
        return _safe_preview(s, max_chars=max_chars, max_items=max_items)
    except Exception:
        return repr(obj)


def rag_trace(
    *,
    step: str,
    input: Any = None,
    output: Any = None,
    meta: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """Emit a single RAG trace boundary.

    - always logs to ota.rag / ota.flow (existing behavior)
    - additionally emits a LangSmith boundary via rag_langsmith_span (best-effort)
    """

    if not _enabled():
        return

    p = _req_prefix()
    payload: dict[str, Any] = {"step": step}

    if input is not None:
        payload["input"] = _safe_preview(input)
    if output is not None:
        payload["output"] = _safe_preview(output)
    if meta:
        payload["meta"] = _safe_preview(meta, max_chars=2000, max_items=50)

    try:
        msg = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        msg = str(payload)

    span_inputs = {"input": payload["input"]} if "input" in payload else {}
    span_outputs = {"output": payload["output"]} if "output" in payload else {}
    span_metadata = {"level": level, **(payload.get("meta") or {})}

    with rag_langsmith_span(
        step,
        inputs=span_inputs,
        outputs=span_outputs,
        metadata=span_metadata,
    ):
        if level.lower() == "debug":
            _rag_logger.debug("%s %s", p, msg)
            return
        if level.lower() == "warning":
            _rag_logger.warning("%s %s", p, msg)
            return

        logger.info("%s [rag] %s", p, msg)


def rag_trace_error(
    *,
    step: str,
    error: BaseException,
    input: Any = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Emit a structured RAG error trace boundary."""

    err_payload = {
        "type": type(error).__name__,
        "message": str(error),
    }
    merged_meta = {
        **(meta or {}),
        "error_type": err_payload["type"],
        "error": err_payload["message"],
    }
    rag_trace(
        step=f"{step}:error",
        input=input,
        output={"error": err_payload},
        meta=merged_meta,
        level="warning",
    )

