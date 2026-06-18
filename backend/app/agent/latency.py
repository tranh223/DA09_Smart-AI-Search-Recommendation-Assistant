"""Per-stage latency helpers for the LangGraph workflow."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.agent.tracer import extract_node_context, log_node_done

NodeFn = TypeVar("NodeFn", bound=Callable[[dict[str, Any]], dict[str, Any]])
logger = logging.getLogger(__name__)


def merge_latency_trace(
    left: dict[str, float] | None,
    right: dict[str, float] | None,
) -> dict[str, float]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def with_timing(node_name: str, node_fn: NodeFn) -> NodeFn:
    """Wrap a graph node to record wall-clock duration in ``latency_trace``.

    Tích lũy toàn bộ lịch sử timing (không overwrite) bằng cách merge với
    giá trị latency_trace đã có trong state từ các node trước đó.

    Mỗi node khi hoàn thành sẽ emit một log line qua ``ota.flow`` logger
    với timing và context cụ thể của node đó (intent, candidates count...).
    """

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        request_id = state.get("request_id") or state.get("session_id") or "-"
        logger.debug("[graph][%s] node=%s start", request_id, node_name)
        try:
            result = node_fn(state) or {}
        except Exception:
            ms = elapsed_ms(start)
            logger.exception(
                "[graph][%s] node=%s FAILED after %.2fms",
                request_id, node_name, ms,
            )
            raise

        # Accumulate: merge existing trace + result's trace (parallel nodes) + current node
        trace: dict[str, float] = dict(state.get("latency_trace") or {})
        if "latency_trace" in result:
            trace.update(result.pop("latency_trace"))
        node_ms = elapsed_ms(start)
        trace[node_name] = node_ms

        # Emit structured flow trace line (ota.flow logger)
        context = extract_node_context(node_name, state, result)
        log_node_done(request_id, node_name, node_ms, context)

        return {**result, "latency_trace": trace}

    wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    wrapped.__doc__ = node_fn.__doc__
    return wrapped  # type: ignore[return-value]


def build_latency_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate stage timings and identify the slowest stage on the critical path."""
    trace = dict(state.get("latency_trace") or {})
    started_at = state.get("request_started_at")

    total_ms = (
        elapsed_ms(started_at)
        if started_at is not None
        else round(sum(trace.values()), 2)
    )

    parallel_ms = max(
        trace.get("rag", 0.0),
        trace.get("recommend", 0.0) + trace.get("rerank", 0.0),
    )
    critical_path_ms = round(
        trace.get("session", 0.0)
        + trace.get("intent", 0.0)
        + trace.get("slot_check", 0.0)
        + trace.get("rewrite", 0.0)
        + parallel_ms
        + trace.get("response_builder", 0.0)
        + trace.get("explain", 0.0)
        + trace.get("format_response", 0.0),
        2,
    )

    bottleneck_stage = max(trace, key=trace.get) if trace else None
    qu_timing_raw = (state.get("qu_trace") or {}).get("timing") or {}
    qu_timing = {
        k: float(v)
        for k, v in qu_timing_raw.items()
        if isinstance(v, (int, float))
    }
    qu_bottleneck = max(qu_timing, key=qu_timing.get) if qu_timing else None

    rerank_result = state.get("rerank_result") or {}
    rerank_latency_ms = rerank_result.get("latency_ms")
    rerank_breakdown = rerank_result.get("latency_breakdown") or {}

    return {
        "total_ms": total_ms,
        "critical_path_ms": critical_path_ms,
        "stages_ms": trace,
        "parallel_section_ms": round(parallel_ms, 2),
        "bottleneck_stage": bottleneck_stage,
        "bottleneck_ms": trace.get(bottleneck_stage, 0.0) if bottleneck_stage else 0.0,
        "qu_pipeline_detail_ms": qu_timing_raw,
        "qu_bottleneck": qu_bottleneck,
        "qu_bottleneck_ms": qu_timing.get(qu_bottleneck) if qu_bottleneck else None,
        "rerank_reported_ms": rerank_latency_ms,
        "rerank_breakdown_ms": rerank_breakdown,
    }
