"""Chat route scaffold wired to LangGraph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.graph import build_graph

router = APIRouter(prefix="/chat", tags=["chat"])
graph = build_graph()


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    query: str
    slots: dict[str, Any] = Field(default_factory=dict)
    rerank_options: dict[str, Any] = Field(default_factory=dict)


@router.post("")
async def chat(req: ChatRequest):
    state = {
        "user_id": req.user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        "slots": req.slots,
        "rerank_options": req.rerank_options,
    }
    result = await graph.ainvoke(state)
    return result.get("final_response", result)

