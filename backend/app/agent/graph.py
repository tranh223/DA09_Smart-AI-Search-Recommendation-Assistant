"""LangGraph workflow definition for OTA assistant."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.latency import with_timing
from app.agent.nodes import (
    analytics_node,
    clarify_node,
    explain_node,
    format_response_node,
    intent_node,
    rag_node,
    recommend_node,
    rerank_node,
    response_builder_node,
    rewrite_node,
    session_node,
    slot_check_node,
)
from app.agent.router import route_slot_check
from app.agent.state import AgentState


def build_graph():
    """Compile and return OTA LangGraph app."""
    graph = StateGraph(AgentState)

    graph.add_node("session", with_timing("session", session_node))
    graph.add_node("intent", with_timing("intent", intent_node))
    graph.add_node("slot_check", with_timing("slot_check", slot_check_node))
    graph.add_node("clarify", with_timing("clarify", clarify_node))
    graph.add_node("rewrite", with_timing("rewrite", rewrite_node))
    graph.add_node("rag", with_timing("rag", rag_node))
    graph.add_node("recommend", with_timing("recommend", recommend_node))
    graph.add_node("rerank", with_timing("rerank", rerank_node))
    graph.add_node("response_builder", with_timing("response_builder", response_builder_node))
    graph.add_node("explain", with_timing("explain", explain_node))
    graph.add_node("format_response", with_timing("format_response", format_response_node))
    graph.add_node("analytics", with_timing("analytics", analytics_node))

    graph.add_edge(START, "session")
    graph.add_edge("session", "intent")
    graph.add_edge("intent", "slot_check")

    graph.add_conditional_edges(
        "slot_check",
        route_slot_check,
        {
            "complete": "rewrite",
            "incomplete": "clarify",
        },
    )

    # rewrite fan-out → RAG và Recommend chạy song song (cùng độ sâu 1 từ rewrite)
    graph.add_edge("clarify", "analytics")
    graph.add_edge("rewrite", "rag")
    graph.add_edge("rewrite", "recommend")

    # Fan-in tại rerank: cả rag và recommend đều là 1 hop từ rewrite (equal depth).
    # LangGraph chờ CẢ HAI hoàn thành trước khi chạy rerank → rerank chạy đúng 1 lần.
    # rag_answer đã có trong state khi rerank kích hoạt response_builder.
    graph.add_edge("rag", "rerank")
    graph.add_edge("recommend", "rerank")

    # response_builder chỉ có 1 predecessor (rerank) → không bao giờ chạy 2 lần.
    graph.add_edge("rerank", "response_builder")

    graph.add_edge("response_builder", "explain")
    graph.add_edge("explain", "format_response")
    graph.add_edge("format_response", "analytics")
    graph.add_edge("analytics", END)

    return graph.compile()

