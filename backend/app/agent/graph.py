"""LangGraph workflow definition for OTA assistant."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

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

    graph.add_node("session", session_node)
    graph.add_node("intent", intent_node)
    graph.add_node("slot_check", slot_check_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("rag", rag_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("response_builder", response_builder_node)
    graph.add_node("explain", explain_node)
    graph.add_node("format_response", format_response_node)
    graph.add_node("analytics", analytics_node)

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

    # rewrite fan-out → RAG và Recommend chạy song song
    graph.add_edge("clarify", END)
    graph.add_edge("rewrite", "rag")
    graph.add_edge("rewrite", "recommend")
    graph.add_edge("recommend", "rerank")

    # response_builder chờ cả rag và rerank hoàn thành (LangGraph fan-in tự động)
    graph.add_edge("rag", "response_builder")
    graph.add_edge("rerank", "response_builder")

    graph.add_edge("response_builder", "explain")
    graph.add_edge("explain", "format_response")
    graph.add_edge("format_response", "analytics")
    graph.add_edge("analytics", END)

    return graph.compile()

