"""Router helpers for conditional edges."""

from __future__ import annotations

from app.agent.state import AgentState


def route_slot_check(state: AgentState) -> str:
    """Return routing key based on slot completeness."""
    return "complete" if state.get("slot_is_complete") else "incomplete"

