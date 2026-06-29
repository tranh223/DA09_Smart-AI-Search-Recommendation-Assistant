"""Per-stage latency helpers for the LangGraph workflow.

`with_timing` bao bọc mỗi node, ghi timing + context vào:
  • latency_trace  — dict accumulated trong AgentState (backward-compat)
  • FlowTrace span — chi tiết đầy đủ qua core.trace contextvar, bao gồm:
      - input_snapshot: state snapshot TRƯỚC khi node chạy
      - output_patch:   output node TRẢ VỀ (delta state)
      - data (context): scalars + detail dicts (log console + JSON)
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.agent.tracer import extract_node_context, extract_node_input, extract_node_output
from app.core.trace import current_trace

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
    """
    Bao bọc một graph node để:
      1. Snapshot input state TRƯỚC khi node chạy.
      2. Chạy node, đo wall-clock elapsed_ms.
      3. Snapshot output patch (result) SAU khi node chạy.
      4. Tích lũy vào latency_trace trong AgentState.
      5. Tạo Span đầy đủ trong FlowTrace contextvar (input + output + context).
      6. Log một dòng tóm tắt lên ota.flow (console).
    """

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        request_id = state.get("request_id") or state.get("session_id") or "-"
        logger.debug("[graph][%s] node=%s start", request_id, node_name)

        # ── 1. Snapshot input TRƯỚC khi node chạy ────────────────────────────
        input_snap = extract_node_input(node_name, state)

        # ── 2. Chạy node thực sự ─────────────────────────────────────────────
        node_error: str | None = None
        node_status = "ok"
        try:
            result = node_fn(state) or {}
        except Exception as exc:
            ms = elapsed_ms(start)
            node_error = f"{type(exc).__name__}: {exc}"
            node_status = "error"
            logger.exception(
                "[graph][%s] node=%s FAILED after %.2fms", request_id, node_name, ms,
            )
            raise
        finally:
            # Đảm bảo luôn tính elapsed kể cả khi lỗi
            node_ms = elapsed_ms(start)

        # ── 3. Snapshot output PATCH node trả về ─────────────────────────────
        output_snap = extract_node_output(node_name, state, result)

        # ── 4. Tích lũy latency_trace (backward-compat cho build_latency_summary) ──
        trace_dict: dict[str, float] = dict(state.get("latency_trace") or {})
        if "latency_trace" in result:
            trace_dict.update(result.pop("latency_trace"))
        trace_dict[node_name] = node_ms

        # ── 5. Extract context cho cả console và FlowTrace ───────────────────
        context = extract_node_context(node_name, state, result)

        # ── 6. Populate FlowTrace span (input + output + context) ─────────────
        flow_trace = current_trace()
        if flow_trace is not None:
            span = flow_trace.begin(node_name)
            span.elapsed_ms = node_ms
            span.status = node_status
            if node_error:
                span.error = node_error
            span.input_snapshot = input_snap
            span.output_patch = output_snap
            span.data.update(context)
            flow_trace.log_span(span)
        else:
            # Fallback: log trực tiếp qua ota.flow nếu chưa có FlowTrace
            from app.core.trace import FLOW_LOG
            scalar_pairs = [
                f"{k}={v}"
                for k, v in context.items()
                if not isinstance(v, (dict, list))
            ]
            data_str = "  ".join(scalar_pairs)
            p = f"[{request_id[:16]}]"
            if data_str:
                FLOW_LOG.info("%s ─ %-22s %8.1fms  %s", p, node_name, node_ms, data_str)
            else:
                FLOW_LOG.info("%s ─ %-22s %8.1fms", p, node_name, node_ms)

        return {**result, "latency_trace": trace_dict}

    wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    wrapped.__doc__ = node_fn.__doc__
    return wrapped  # type: ignore[return-value]


def build_latency_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Tổng hợp timing các stage, tìm bottleneck trên critical path."""
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
        k: float(v) for k, v in qu_timing_raw.items() if isinstance(v, (int, float))
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
