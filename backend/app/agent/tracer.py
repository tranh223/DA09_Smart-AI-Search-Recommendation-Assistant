"""Structured flow tracer for the OTA LangGraph workflow.

Emits clean, scannable log lines to the ``ota.flow`` logger so you can
follow the entire pipeline at a glance while the backend is running.

Each line is prefixed with ``[<req_id_short>]`` — grep this to isolate
a single request across interleaved concurrent log output.

Typical console output
----------------------
::

    INFO:ota.flow: [abc123def456] ══════════════════════════════════════════════════
    INFO:ota.flow: [abc123def456] ► POST /chat  user=u001  session=s001
    INFO:ota.flow: [abc123def456]   query="tìm khách sạn biển Đà Nẵng 2 người"
    INFO:ota.flow: [abc123def456] ─ session           42.1ms  history=3t  summary=yes
    INFO:ota.flow: [abc123def456] ─ intent          1234.5ms  intent=hotel_search  dst=Đà Nẵng  slots_ok=True
    INFO:ota.flow: [abc123def456] ─ slot_check          1.2ms  route=complete
    INFO:ota.flow: [abc123def456] ─ rewrite              0.3ms
    INFO:ota.flow: [abc123def456] ─ rag                  0.1ms  status=SKIP(hotel_search)
    INFO:ota.flow: [abc123def456] ─ recommend          456.8ms  candidates=15
    INFO:ota.flow: [abc123def456] ─ rerank             234.2ms  ranked=10  llm=no
    INFO:ota.flow: [abc123def456] ─ response_builder   890.0ms  answer_len=342  reasons=10  sugg=3
    INFO:ota.flow: [abc123def456] ─ explain              2.1ms  recs=10  with_reason=10
    INFO:ota.flow: [abc123def456] ─ format_response       1.0ms
    INFO:ota.flow: [abc123def456] ─ analytics            4.9ms
    INFO:ota.flow: [abc123def456] ◆ DONE 2867ms  intent=hotel_search  recs=10  srcs=0  critical=2854ms  bottleneck=intent(1234ms)
    INFO:ota.flow: [abc123def456] ══════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from typing import Any

flow_logger = logging.getLogger("ota.flow")

_SEP = "═" * 54
_RAG_INTENTS: frozenset[str] = frozenset({"information", "special_feature", "hotel_similar"})


def _p(request_id: str) -> str:
    """Short request-id prefix for log lines."""
    return f"[{request_id[:16]}]"


# ── Per-node context extractors ───────────────────────────────────────────────
# Signature: (pre_state: dict, post_result: dict) -> dict[str, Any]
# Keep values short — they are printed inline.


def _ctx_session(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    history = result.get("chat_history") or state.get("chat_history") or []
    summary = bool(result.get("conversation_summary") or state.get("conversation_summary"))
    return {"history": f"{len(history)}t", "summary": "yes" if summary else "no"}


def _ctx_intent(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    intent = result.get("intent") or state.get("intent") or "?"
    slots = result.get("slots") or state.get("slots") or {}
    dst = slots.get("destination") or "?"
    ok = result.get("slot_is_complete")
    if ok is None:
        ok = state.get("slot_is_complete")
    ctx: dict[str, Any] = {"intent": intent, "dst": dst, "slots_ok": ok}
    # Show which path QU took (pipeline vs fallback)
    qu = result.get("qu_trace") or {}
    if qu.get("path"):
        ctx["qu_path"] = qu["path"]
    return ctx


def _ctx_slot_check(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    ok = result.get("slot_is_complete")
    if ok is None:
        ok = state.get("slot_is_complete")
    return {"route": "complete" if ok else "→CLARIFY"}


def _ctx_clarify(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    missing = (
        result.get("clarification_missing_fields")
        or state.get("clarification_missing_fields")
        or []
    )
    question = (result.get("clarification_question") or state.get("clarification_question") or "")[:60]
    return {
        "missing": ",".join(missing) if missing else "?",
        "question": repr(question),
    }


def _ctx_rag(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    rag_answer = result.get("rag_answer") or ""
    rag_docs = result.get("rag_docs") or []
    intent = state.get("intent") or ""
    if not rag_answer and not rag_docs:
        if intent and intent not in _RAG_INTENTS:
            return {"status": f"SKIP({intent})"}
        return {"status": "empty"}
    return {"docs": len(rag_docs), "answer_len": len(rag_answer)}


def _ctx_recommend(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    merged = result.get("merged_candidates") or []
    ri = result.get("recommend_input") or state.get("recommend_input")
    dst = ""
    if ri is not None:
        try:
            dst = (ri.session_context.destination or "") if hasattr(ri, "session_context") else ""
        except Exception:  # noqa: BLE001
            dst = ""
    ctx: dict[str, Any] = {"candidates": len(merged)}
    if dst:
        ctx["dst"] = dst
    return ctx


def _ctx_rerank(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    rerank_result = result.get("rerank_result") or {}
    ranked = rerank_result.get("ranked_hotels") or []
    debug = rerank_result.get("debug") or {}
    llm = "yes" if debug.get("llm_rerank_used") else "no"
    latency_ms = debug.get("latency_ms")
    ctx: dict[str, Any] = {"ranked": len(ranked), "llm": llm}
    if latency_ms is not None:
        ctx["reranker_ms"] = round(latency_ms, 1)
    return ctx


def _ctx_response_builder(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("synthesized_answer") or ""
    reasons = result.get("hotel_reasons") or {}
    sugg = result.get("next_suggestions") or []
    return {"answer_len": len(answer), "reasons": len(reasons), "sugg": len(sugg)}


def _ctx_explain(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    recs = result.get("ranked_recommendations") or state.get("ranked_recommendations") or []
    with_reason = sum(1 for r in recs if r.get("ai_reason"))
    return {"recs": len(recs), "with_reason": with_reason}


def _ctx_analytics(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    session_id = state.get("session_id") or ""
    return {"kafka": "queued" if session_id else "skip"}


_EXTRACTORS: dict[str, Any] = {
    "session": _ctx_session,
    "intent": _ctx_intent,
    "slot_check": _ctx_slot_check,
    "clarify": _ctx_clarify,
    "rag": _ctx_rag,
    "recommend": _ctx_recommend,
    "rerank": _ctx_rerank,
    "response_builder": _ctx_response_builder,
    "explain": _ctx_explain,
    "analytics": _ctx_analytics,
}


def extract_node_context(
    node_name: str,
    state: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Return a dict of key/value pairs for the given node, or {} if no extractor."""
    extractor = _EXTRACTORS.get(node_name)
    if extractor is None:
        return {}
    try:
        return extractor(state, result) or {}
    except Exception:  # noqa: BLE001
        return {}


# ── Flow-level logging ────────────────────────────────────────────────────────

def log_flow_start(
    request_id: str,
    user_id: str,
    session_id: str,
    query: str,
) -> None:
    """Log the beginning of a /chat request."""
    p = _p(request_id)
    flow_logger.info("%s %s", p, _SEP)
    flow_logger.info("%s ► POST /chat  user=%s  session=%s", p, user_id, session_id)
    flow_logger.info("%s   query=%r", p, query[:120])


def log_node_done(
    request_id: str,
    node_name: str,
    elapsed_ms: float,
    context: dict[str, Any],
) -> None:
    """Log one line per completed node with timing and key context values."""
    p = _p(request_id)
    ctx_str = "  ".join(f"{k}={v}" for k, v in context.items()) if context else ""
    if ctx_str:
        flow_logger.info("%s ─ %-18s %7.1fms  %s", p, node_name, elapsed_ms, ctx_str)
    else:
        flow_logger.info("%s ─ %-18s %7.1fms", p, node_name, elapsed_ms)


def log_flow_end(
    request_id: str,
    total_ms: int,
    final_state: dict[str, Any],
) -> None:
    """Log the final summary line after the full graph completes."""
    p = _p(request_id)
    fr = final_state.get("final_response") or {}
    intent = fr.get("intent") or final_state.get("intent") or "?"
    n_recs = len(fr.get("recommendations") or [])
    n_srcs = len(fr.get("sources") or [])
    needs_clarify = fr.get("needs_clarification") or final_state.get("needs_clarification")

    lat = final_state.get("latency_summary") or {}
    bottleneck = lat.get("bottleneck_stage") or "?"
    bottleneck_ms = lat.get("bottleneck_ms") or 0
    critical_ms = lat.get("critical_path_ms") or 0

    if needs_clarify:
        flow_logger.info(
            "%s ◆ DONE %dms  → CLARIFICATION REQUESTED  intent=%s",
            p, total_ms, intent,
        )
    else:
        flow_logger.info(
            "%s ◆ DONE %dms  intent=%s  recs=%d  srcs=%d  critical=%dms  bottleneck=%s(%.0fms)",
            p, total_ms, intent, n_recs, n_srcs, critical_ms, bottleneck, bottleneck_ms,
        )
    flow_logger.info("%s %s", p, _SEP)
