"""
Flow-tracer cho OTA LangGraph workflow.

Trách nhiệm:
  1. Cung cấp hàm `log_flow_start` / `log_flow_end` dùng bởi chat.py
     (hai hàm này nay delegate sang FlowTrace).
  2. Cung cấp `extract_node_context` — trả dict chi tiết cho mỗi node,
     dùng bởi `with_timing` trong latency.py để populate FlowTrace span.

Mỗi extractor nhận (pre_state, post_result) và trả dict gồm hai loại:
  • scalar fields  → hiển thị inline trên console (key=value)
  • nested dict/list → chỉ vào JSON trace file, không xuất console
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.trace import FlowTrace, current_trace

_RAG_INTENTS: frozenset[str] = frozenset({"information", "special_feature", "hotel_similar"})

logger = logging.getLogger(__name__)


# ── Per-node context extractors ───────────────────────────────────────────────
# Signature: (pre_state: dict, post_result: dict) -> dict[str, Any]
# Scalar values → console line; dicts/lists → JSON trace only.


def _ctx_session(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    history = result.get("chat_history") or state.get("chat_history") or []
    summary = bool(result.get("conversation_summary") or state.get("conversation_summary"))
    profile = result.get("user_profile") or {}
    sc = profile.get("session_context") if isinstance(profile, dict) else {}
    sc = sc or {}
    return {
        # scalar — console
        "history": f"{len(history)}t",
        "summary": "yes" if summary else "no",
        "dst": sc.get("destination") or "?",
        # detail — JSON only
        "session_context": {
            "destination": sc.get("destination"),
            "check_in": sc.get("check_in"),
            "check_out": sc.get("check_out"),
            "nearby_place": sc.get("nearby_place"),
            "number_of_guests": sc.get("number_of_guests"),
            "has_pet": sc.get("has_pet"),
            "has_children": sc.get("has_children"),
        },
        "long_term_loaded": bool(
            (profile.get("long_term_profile") if isinstance(profile, dict) else None)
        ),
        "history_turns": len(history),
    }


def _ctx_intent(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    intent = result.get("intent") or "?"
    slots = result.get("slots") or {}
    dst = slots.get("destination") or "?"
    ok = result.get("slot_is_complete")
    qu: dict[str, Any] = result.get("qu_trace") or {}
    timing: dict[str, Any] = qu.get("timing") or {}

    # Guardrail
    guardrail = qu.get("guardrail") or {}
    # Intent entities
    intent_data = qu.get("intent") or {}
    entities = intent_data.get("entities") or {}
    sem_prefs = intent_data.get("semantic_preferences") or {}
    items_count = len((sem_prefs.get("items") or []))

    # Session profile update
    spupdate = qu.get("session_profile_update") or {}
    applied_updates = list((spupdate.get("applied_updates") or {}).keys())

    # Router
    router = qu.get("router") or {}
    rec_tasks = [str(s.get("intent_type", "")) for s in (router.get("recommendation_plan") or [])]
    rag_tasks = [str(s.get("intent_type", "")) for s in (router.get("rag_plan") or [])]

    # Checker / plan_readiness
    checker = qu.get("checker") or {}
    plan_r = checker.get("plan_readiness") or checker.get("initial_plan_readiness") or {}
    missing = plan_r.get("missing_fields") or []

    pipeline_used = "fallback" if not qu else "qu_pipeline"

    return {
        # scalar — console
        "pipeline": pipeline_used,
        "intent": intent,
        "dst": dst,
        "slots_ok": ok,
        "missing": ",".join(missing) if missing else "-",
        # detail — JSON only
        "guardrail": {
            "allow": guardrail.get("allow"),
            "category": guardrail.get("category"),
            "reason": guardrail.get("reason"),
        },
        "plan_readiness": {
            "can_build_plan": plan_r.get("can_build_plan"),
            "missing_fields": missing,
            "requires_recommendation": plan_r.get("requires_recommendation"),
        },
        "entities": {
            "destination": entities.get("destination"),
            "check_in": entities.get("check_in"),
            "check_out": entities.get("check_out"),
            "trip_type": entities.get("trip_type"),
            "nearby_place": entities.get("nearby_place"),
        },
        "semantic_preferences_count": items_count,
        "session_updates_applied": applied_updates,
        "router_tasks": {"recommendation": rec_tasks, "rag": rag_tasks},
        "slots": slots,
        "qu_timing_ms": {k: v for k, v in timing.items() if isinstance(v, (int, float))},
    }


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
    question = (
        result.get("clarification_question")
        or state.get("clarification_question")
        or ""
    )
    return {
        # scalar
        "missing": ",".join(missing) if missing else "?",
        "question": repr(question[:80]),
    }


def _ctx_rag(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    rag_answer = result.get("rag_answer") or ""
    rag_docs = result.get("rag_docs") or []
    intent = state.get("intent") or ""

    if not rag_answer and not rag_docs:
        if intent and intent not in _RAG_INTENTS:
            return {"status": f"SKIP({intent})"}
        return {"status": "empty"}

    by_source: dict[str, int] = {}
    for d in rag_docs:
        src = d.get("source", "?")
        by_source[src] = by_source.get(src, 0) + 1

    return {
        # scalar
        "docs": len(rag_docs),
        "answer_len": len(rag_answer),
        "confidence": result.get("rag_confidence", 0.0),
        # detail
        "docs_by_source": by_source,
        "answer_preview": rag_answer[:200],
    }


def _ctx_recommend(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    merged = result.get("merged_candidates") or []
    raw_stats: dict[str, int] = result.get("_raw_source_stats") or {}
    ri = result.get("recommend_input") or state.get("recommend_input")
    dst = ""
    if ri is not None:
        try:
            dst = (ri.session_context.destination or "") if hasattr(ri, "session_context") else ""
        except Exception:  # noqa: BLE001
            dst = ""

    # Per-source breakdown từ merged (post-dedup)
    src_breakdown: dict[str, int] = {}
    multi_src_count = 0
    for m in merged:
        for s in (m.sources if hasattr(m, "sources") else []):
            src_breakdown[s] = src_breakdown.get(s, 0) + 1
        if len(getattr(m, "sources", [])) > 1:
            multi_src_count += 1

    top_merged = [
        {
            "hotel_id": getattr(m, "hotel_id", "?"),
            "name": getattr(m, "hotel_name", "?"),
            "pre_rank": round(getattr(m, "pre_rank_score", 0.0), 4),
            "sources": getattr(m, "sources", []),
        }
        for m in merged[:8]
    ]

    raw_total = sum(raw_stats.values()) if raw_stats else None

    ctx: dict[str, Any] = {
        # scalar
        "candidates": len(merged),
    }
    if dst:
        ctx["dst"] = dst
    if multi_src_count:
        ctx["multi_src"] = multi_src_count

    ctx.update({
        # detail
        "raw_source_stats": raw_stats,
        "raw_total": raw_total,
        "merged_source_breakdown": src_breakdown,
        "multi_source_hotels": multi_src_count,
        "top_merged": top_merged,
    })
    return ctx


def _ctx_rerank(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    rr = result.get("rerank_result") or {}
    ranked_hotels = rr.get("ranked_hotels") or []
    debug = rr.get("debug") or {}
    breakdown = rr.get("latency_breakdown") or {}
    llm_used = bool(rr.get("llm_used") or debug.get("llm_used"))

    top_ranked = [
        {
            "rank": h.get("rank"),
            "hotel_id": h.get("hotel_id") or h.get("item_id"),
            "name": h.get("name"),
            "final_score": h.get("final_score"),
            "base_score": h.get("base_score"),
            "llm_score": h.get("llm_score"),
            "reasons": (h.get("reasons") or [])[:3],
        }
        for h in ranked_hotels[:8]
    ]

    filtered_items = debug.get("filtered_items") or []

    return {
        # scalar
        "ranked": len(ranked_hotels),
        "filtered": debug.get("filtered_count", len(filtered_items)),
        "llm": "yes" if llm_used else "no",
        # detail
        "top_ranked": top_ranked,
        "filtered_items": [
            {"hotel_id": f.get("item_id"), "name": f.get("name"), "reason": f.get("reason")}
            for f in filtered_items[:5]
        ],
        "latency_breakdown_ms": breakdown,
        "candidate_source": rr.get("candidate_source"),
        "diversity": debug.get("diversified", False),
    }


def _ctx_response_builder(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("synthesized_answer") or ""
    reasons = result.get("hotel_reasons") or {}
    sugg = result.get("next_suggestions") or []
    return {
        # scalar
        "answer_len": len(answer),
        "reasons": len(reasons),
        "sugg": len(sugg),
        # detail
        "answer_preview": answer[:300],
        "next_suggestions": sugg,
    }


def _ctx_explain(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    recs = result.get("ranked_recommendations") or state.get("ranked_recommendations") or []
    with_reason = sum(1 for r in recs if r.get("ai_reason"))
    return {"recs": len(recs), "with_reason": with_reason}


def _ctx_analytics(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    session_id = state.get("session_id") or ""
    lat = result.get("latency_summary") or {}
    return {
        "kafka": "queued" if session_id else "skip",
        "total_ms": lat.get("total_ms"),
        "bottleneck": lat.get("bottleneck_stage"),
    }


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
    extractor = _EXTRACTORS.get(node_name)
    if extractor is None:
        return {}
    try:
        return extractor(state, result) or {}
    except Exception:  # noqa: BLE001
        return {}


# ── Flow-level helpers (backward-compat, delegate sang FlowTrace) ─────────────

def log_flow_start(
    request_id: str,
    user_id: str,
    session_id: str,
    query: str,
) -> None:
    """Gọi bởi chat.py — nay FlowTrace.log_start() làm việc chính."""
    trace = current_trace()
    if trace:
        trace.log_start()


def log_flow_end(
    request_id: str,
    total_ms: int,
    final_state: dict[str, Any],
) -> None:
    """Gọi bởi chat.py — nay FlowTrace.log_end() làm việc chính."""
    trace = current_trace()
    if not trace:
        return
    fr = final_state.get("final_response") or {}
    intent = fr.get("intent") or final_state.get("intent") or "?"
    n_recs = len(fr.get("recommendations") or [])
    n_srcs = len(fr.get("sources") or [])
    needs_clarify = bool(fr.get("needs_clarification") or final_state.get("needs_clarification"))
    trace.log_end(needs_clarify=needs_clarify, intent=intent, n_recs=n_recs, n_srcs=n_srcs)
    trace.finalize()
