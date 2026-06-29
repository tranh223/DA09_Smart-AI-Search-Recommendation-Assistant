"""
Flow-tracer cho OTA LangGraph workflow.

Trách nhiệm:
  1. Cung cấp hàm `log_flow_start` / `log_flow_end` dùng bởi chat.py
     (hai hàm này nay delegate sang FlowTrace).
  2. Cung cấp `extract_node_input`  — snapshot input state TRƯỚC khi node chạy.
  3. Cung cấp `extract_node_output` — snapshot output/patch SAU khi node chạy.
  4. Cung cấp `extract_node_context` — context summary cho console + JSON trace.

Quy ước:
  • input extractors  nhận (pre_state: dict) → dict
  • output extractors nhận (pre_state: dict, post_result: dict) → dict
  • context extractors nhận (pre_state, post_result) → dict gồm:
      - scalar fields  → hiển thị inline trên console (key=value)
      - nested dict/list → chỉ vào JSON trace file, không xuất console
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.trace import FlowTrace, current_trace

_RAG_INTENTS: frozenset[str] = frozenset({"information", "special_feature", "hotel_similar"})

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Per-node INPUT extractors
# Signature: (pre_state: dict) → dict[str, Any]
# Snapshot state fields BEFORE the node runs.
# Keep objects small — avoid copying large lists verbatim.
# ────────────────────────────────────────────────────────────────────────────

def _in_session(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": s.get("session_id"),
        "user_id": s.get("user_id"),
        "raw_query": s.get("raw_query"),
    }


def _in_intent(s: dict[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = s.get("user_profile") or {}
    sc = profile.get("session_context") if isinstance(profile, dict) else {}
    sc = sc or {}
    history = s.get("chat_history") or []
    lt = profile.get("long_term_profile") if isinstance(profile, dict) else {}
    return {
        "raw_query": s.get("raw_query"),
        "chat_history_turns": len(history),
        "conversation_summary_chars": len(s.get("conversation_summary") or ""),
        "session_context": {
            "destination": sc.get("destination"),
            "check_in": sc.get("check_in"),
            "check_out": sc.get("check_out"),
            "nearby_place": sc.get("nearby_place"),
            "number_of_guests": sc.get("number_of_guests"),
            "number_of_days": sc.get("number_of_days"),
            "number_of_nights": sc.get("number_of_nights"),
            "budget_type": sc.get("budget_type"),
            "raw_budget_min": sc.get("raw_budget_min"),
            "raw_budget_max": sc.get("raw_budget_max"),
        },
        "has_long_term_profile": bool(lt),
    }


def _in_slot_check(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": s.get("intent"),
        "slot_is_complete": s.get("slot_is_complete"),
        "slots": s.get("slots") or {},
        "needs_clarification": s.get("needs_clarification"),
    }


def _in_clarify(s: dict[str, Any]) -> dict[str, Any]:
    guardrail = (s.get("qu_trace") or {}).get("guardrail") or {}
    return {
        "needs_clarification": s.get("needs_clarification"),
        "clarification_question": s.get("clarification_question"),
        "clarification_missing_fields": s.get("clarification_missing_fields") or [],
        "guardrail_blocked": guardrail.get("allow") is False,
        "guardrail_category": guardrail.get("category"),
    }


def _in_rewrite(s: dict[str, Any]) -> dict[str, Any]:
    recommend_input = s.get("recommend_input")
    return {
        "raw_query": s.get("raw_query"),
        "intent": s.get("intent"),
        "slots": s.get("slots") or {},
        "has_recommend_input": recommend_input is not None,
    }


def _in_rag(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "rewritten_query": s.get("rewritten_query") or s.get("raw_query"),
        "intent": s.get("intent"),
        "slots": s.get("slots") or {},
        "chat_history_turns": len(s.get("chat_history") or []),
    }


def _in_recommend(s: dict[str, Any]) -> dict[str, Any]:
    ri = s.get("recommend_input")
    if ri is None:
        return {"recommend_input": None, "candidate_limit_per_source": s.get("candidate_limit_per_source")}
    try:
        sc = ri.session_context if hasattr(ri, "session_context") else {}
        profile = ri.profile if hasattr(ri, "profile") else {}
        return {
            "user_id": ri.user_id if hasattr(ri, "user_id") else None,
            "original_query": ri.original_query if hasattr(ri, "original_query") else None,
            "search_query_template": getattr(ri, "search_query_template", None),
            "limit_per_source": ri.limit_per_source if hasattr(ri, "limit_per_source") else None,
            "session_context": {
                "destination": getattr(sc, "destination", None),
                "check_in": getattr(sc, "check_in", None),
                "check_out": getattr(sc, "check_out", None),
                "nearby_place": getattr(sc, "nearby_place", None),
                "number_of_guests": getattr(sc, "number_of_guests", None),
                "number_of_days": getattr(sc, "number_of_days", None),
                "number_of_nights": getattr(sc, "number_of_nights", None),
                "budget_type": getattr(sc, "budget_type", None),
                "raw_budget_min": getattr(sc, "raw_budget_min", None),
                "raw_budget_max": getattr(sc, "raw_budget_max", None),
                "has_pet": getattr(sc, "has_pet", None),
                "has_children": getattr(sc, "has_children", None),
                "price_range": getattr(sc, "session_price_range", None) and {
                    "min": getattr(sc.session_price_range, "min", None),
                    "max": getattr(sc.session_price_range, "max", None),
                    "currency": getattr(sc.session_price_range, "currency", None),
                },
            },
            "profile_summary": {
                "nationality": getattr(profile, "nationality", None),
                "age_group": getattr(profile, "age_group", None),
                "trip_types": list(getattr(profile, "long_term_trip_types", {}).keys())[:5],
                "preference_habits": list(getattr(profile, "long_term_preference_habits", {}).keys())[:5],
                "amenities": list(getattr(profile, "long_term_amenities", {}).keys())[:5],
            },
        }
    except Exception:  # noqa: BLE001
        return {"recommend_input": "present", "parse_error": True}


def _in_rerank(s: dict[str, Any]) -> dict[str, Any]:
    merged = s.get("merged_candidates") or []
    ri = s.get("recommend_input")
    return {
        "merged_candidates_count": len(merged),
        "rerank_options": s.get("rerank_options") or {},
        "session_destination": (
            getattr(getattr(ri, "session_context", None), "destination", None)
            if ri is not None else None
        ),
    }


def _in_response_builder(s: dict[str, Any]) -> dict[str, Any]:
    ranked = s.get("ranked_recommendations") or []
    rag = s.get("rag_answer") or ""
    return {
        "ranked_count": len(ranked),
        "rag_answer_chars": len(rag),
        "intent": s.get("intent"),
        "destination": (s.get("slots") or {}).get("destination"),
        "top_hotels": [
            {"hotel_id": r.get("hotel_id"), "name": r.get("hotel_name"), "score": r.get("score")}
            for r in ranked[:5]
        ],
    }


def _in_explain(s: dict[str, Any]) -> dict[str, Any]:
    ranked = s.get("ranked_recommendations") or []
    reasons = s.get("hotel_reasons") or {}
    return {
        "ranked_count": len(ranked),
        "hotel_reasons_count": len(reasons),
        "synthesized_answer_chars": len(s.get("synthesized_answer") or ""),
    }


def _in_format_response(s: dict[str, Any]) -> dict[str, Any]:
    ranked = s.get("ranked_recommendations") or []
    return {
        "intent": s.get("intent"),
        "ranked_count": len(ranked),
        "synthesized_answer_chars": len(s.get("synthesized_answer") or ""),
        "rag_docs_count": len(s.get("rag_docs") or []),
        "needs_clarification": s.get("needs_clarification"),
    }


def _in_analytics(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": s.get("session_id"),
        "intent": s.get("intent"),
        "latency_trace": s.get("latency_trace") or {},
    }


_INPUT_EXTRACTORS: dict[str, Any] = {
    "session": _in_session,
    "intent": _in_intent,
    "slot_check": _in_slot_check,
    "clarify": _in_clarify,
    "rewrite": _in_rewrite,
    "rag": _in_rag,
    "recommend": _in_recommend,
    "rerank": _in_rerank,
    "response_builder": _in_response_builder,
    "explain": _in_explain,
    "format_response": _in_format_response,
    "analytics": _in_analytics,
}


def extract_node_input(node_name: str, state: dict[str, Any]) -> dict[str, Any]:
    """Snapshot input state TRƯỚC khi node chạy."""
    fn = _INPUT_EXTRACTORS.get(node_name)
    if fn is None:
        return {}
    try:
        return fn(state) or {}
    except Exception:  # noqa: BLE001
        return {}


# ────────────────────────────────────────────────────────────────────────────
# Per-node OUTPUT extractors
# Signature: (pre_state: dict, post_result: dict) → dict[str, Any]
# Snapshot what the node returned (the state delta).
# ────────────────────────────────────────────────────────────────────────────

def _out_session(s: dict, r: dict) -> dict:
    history = r.get("chat_history") or []
    profile = r.get("user_profile") or {}
    sc = profile.get("session_context") if isinstance(profile, dict) else {}
    sc = sc or {}
    return {
        "chat_history_turns": len(history),
        "conversation_summary_chars": len(r.get("conversation_summary") or ""),
        "session_context": {
            "destination": sc.get("destination"),
            "check_in": sc.get("check_in"),
            "check_out": sc.get("check_out"),
            "nearby_place": sc.get("nearby_place"),
            "number_of_guests": sc.get("number_of_guests"),
            "number_of_days": sc.get("number_of_days"),
            "number_of_nights": sc.get("number_of_nights"),
            "budget_type": sc.get("budget_type"),
            "raw_budget_min": sc.get("raw_budget_min"),
            "raw_budget_max": sc.get("raw_budget_max"),
        },
        "long_term_loaded": bool(
            profile.get("long_term_profile") if isinstance(profile, dict) else None
        ),
    }


def _out_intent(s: dict, r: dict) -> dict:
    qu = r.get("qu_trace") or {}
    timing = qu.get("timing") or {}
    guardrail = qu.get("guardrail") or {}
    checker = qu.get("checker") or {}
    plan_r = checker.get("plan_readiness") or checker.get("initial_plan_readiness") or {}
    router = qu.get("router") or {}
    ri = r.get("recommend_input")
    return {
        "intent": r.get("intent"),
        "slots": r.get("slots") or {},
        "slot_is_complete": r.get("slot_is_complete"),
        "needs_clarification": r.get("needs_clarification"),
        "clarification_question": r.get("clarification_question") or "",
        "clarification_missing_fields": r.get("clarification_missing_fields") or [],
        "recommend_input_built": ri is not None,
        "qu_pipeline": "fallback" if not qu else "qu_pipeline",
        "guardrail": {
            "allow": guardrail.get("allow"),
            "category": guardrail.get("category"),
            "reason": guardrail.get("reason"),
            "assistant_help_context_mode": guardrail.get("assistant_help_context_mode"),
        },
        "plan_readiness": {
            "can_build_plan": plan_r.get("can_build_plan"),
            "missing_fields": plan_r.get("missing_fields") or [],
        },
        "router_tasks": {
            "recommendation": [str(st.get("intent_type", "")) for st in (router.get("recommendation_plan") or [])],
            "rag": [str(st.get("intent_type", "")) for st in (router.get("rag_plan") or [])],
        },
        "qu_timing_ms": {k: v for k, v in timing.items() if isinstance(v, (int, float))},
    }


def _out_slot_check(s: dict, r: dict) -> dict:
    ok = r.get("slot_is_complete")
    return {
        "slot_is_complete": ok,
        "route": "complete" if ok else "incomplete → clarify",
    }


def _out_clarify(s: dict, r: dict) -> dict:
    fr = r.get("final_response") or {}
    return {
        "answer": (fr.get("answer") or "")[:300],
        "needs_clarification": fr.get("needs_clarification"),
        "missing_fields": fr.get("missing_fields") or [],
        "next_suggestions": fr.get("next_suggestions") or [],
    }


def _out_rewrite(s: dict, r: dict) -> dict:
    return {
        "rewritten_query": r.get("rewritten_query") or "",
        "search_query_template": r.get("search_query_template") or "",
    }


def _out_rag(s: dict, r: dict) -> dict:
    docs = r.get("rag_docs") or []
    answer = r.get("rag_answer") or ""
    by_src: dict[str, int] = {}
    for d in docs:
        src = d.get("source", "?")
        by_src[src] = by_src.get(src, 0) + 1
    return {
        "rag_docs_count": len(docs),
        "rag_answer_chars": len(answer),
        "rag_answer_preview": answer[:300],
        "rag_confidence": r.get("rag_confidence", 0.0),
        "docs_by_source": by_src,
    }


def _out_recommend(s: dict, r: dict) -> dict:
    merged = r.get("merged_candidates") or []
    raw_stats = r.get("_raw_source_stats") or {}
    src_breakdown: dict[str, int] = {}
    for m in merged:
        for src in getattr(m, "sources", []):
            src_breakdown[src] = src_breakdown.get(src, 0) + 1
    return {
        "merged_count": len(merged),
        "raw_source_stats": raw_stats,
        "merged_source_breakdown": src_breakdown,
        "top_candidates": [
            {
                "hotel_id": getattr(m, "hotel_id", "?"),
                "name": getattr(m, "hotel_name", "?"),
                "pre_rank_score": round(getattr(m, "pre_rank_score", 0.0), 4),
                "sources": getattr(m, "sources", []),
            }
            for m in merged[:10]
        ],
    }


def _out_rerank(s: dict, r: dict) -> dict:
    rr = r.get("rerank_result") or {}
    ranked = rr.get("ranked_hotels") or []
    debug = rr.get("debug") or {}
    filtered = debug.get("filtered_items") or []
    return {
        "ranked_count": len(ranked),
        "filtered_count": debug.get("filtered_count", len(filtered)),
        "llm_used": bool(rr.get("llm_used") or debug.get("llm_used")),
        "latency_breakdown_ms": rr.get("latency_breakdown") or {},
        "top_ranked": [
            {
                "rank": h.get("rank"),
                "hotel_id": h.get("hotel_id") or h.get("item_id"),
                "name": h.get("name"),
                "final_score": h.get("final_score"),
                "base_score": h.get("base_score"),
                "llm_score": h.get("llm_score"),
                "reasons": (h.get("reasons") or [])[:3],
            }
            for h in ranked[:10]
        ],
        "filtered_items": [
            {"hotel_id": f.get("item_id"), "name": f.get("name"), "reason": f.get("reason")}
            for f in filtered[:5]
        ],
    }


def _out_response_builder(s: dict, r: dict) -> dict:
    answer = r.get("synthesized_answer") or ""
    reasons = r.get("hotel_reasons") or {}
    sugg = r.get("next_suggestions") or []
    return {
        "synthesized_answer_chars": len(answer),
        "synthesized_answer_preview": answer[:400],
        "hotel_reasons_count": len(reasons),
        "hotel_reasons": {
            hid: (reason[:200] if isinstance(reason, str) else reason)
            for hid, reason in list(reasons.items())[:10]
        },
        "next_suggestions": sugg,
    }


def _out_explain(s: dict, r: dict) -> dict:
    recs = r.get("ranked_recommendations") or []
    with_reason = sum(1 for rc in recs if rc.get("ai_reason"))
    return {
        "ranked_recommendations_count": len(recs),
        "with_ai_reason": with_reason,
        "explanation": r.get("explanation") or "",
    }


def _out_format_response(s: dict, r: dict) -> dict:
    fr = r.get("final_response") or {}
    return {
        "answer_chars": len(fr.get("answer") or ""),
        "answer_preview": (fr.get("answer") or "")[:300],
        "intent": fr.get("intent"),
        "recommendations_count": len(fr.get("recommendations") or []),
        "sources_count": len(fr.get("sources") or []),
        "next_suggestions": fr.get("next_suggestions") or [],
        "needs_clarification": fr.get("needs_clarification"),
        "latency": fr.get("latency") or {},
    }


def _out_analytics(s: dict, r: dict) -> dict:
    lat = r.get("latency_summary") or {}
    return {
        "total_ms": lat.get("total_ms"),
        "critical_path_ms": lat.get("critical_path_ms"),
        "bottleneck_stage": lat.get("bottleneck_stage"),
        "bottleneck_ms": lat.get("bottleneck_ms"),
        "per_stage_ms": lat.get("per_stage_ms") or {},
    }


_OUTPUT_EXTRACTORS: dict[str, Any] = {
    "session": _out_session,
    "intent": _out_intent,
    "slot_check": _out_slot_check,
    "clarify": _out_clarify,
    "rewrite": _out_rewrite,
    "rag": _out_rag,
    "recommend": _out_recommend,
    "rerank": _out_rerank,
    "response_builder": _out_response_builder,
    "explain": _out_explain,
    "format_response": _out_format_response,
    "analytics": _out_analytics,
}


def extract_node_output(
    node_name: str,
    state: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Snapshot output/patch SAU khi node chạy."""
    fn = _OUTPUT_EXTRACTORS.get(node_name)
    if fn is None:
        return {}
    try:
        return fn(state, result) or {}
    except Exception:  # noqa: BLE001
        return {}


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
            "assistant_help_context_mode": guardrail.get("assistant_help_context_mode"),
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
