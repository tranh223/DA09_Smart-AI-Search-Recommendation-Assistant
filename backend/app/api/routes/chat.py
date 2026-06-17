"""Chat route wired to LangGraph + QueryUnderstandingPipeline."""

from __future__ import annotations

import time
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

    # Profile người dùng — được QueryUnderstandingPipeline coerce sang UserProfile.
    # Tối thiểu cần {} (pipeline sẽ tạo profile rỗng với user_id bên dưới).
    # Format đầy đủ:
    # {
    #   "long_term_profile": {"nationality": "VN", "long_term_amenities": {...}},
    #   "session_context": {"destination": "Hà Nội", "check_in": "2026-07-01", ...}
    # }
    user_profile: dict[str, Any] = Field(default_factory=dict)

    # slots: backward compat với client cũ chưa gửi user_profile.
    # Các giá trị trong slots sẽ được inject vào session_context khi user_profile
    # chưa có destination. Khi user_profile đã đầy đủ, slots bị bỏ qua.
    slots: dict[str, Any] = Field(default_factory=dict)
    rerank_options: dict[str, Any] = Field(default_factory=dict)


def _merge_slots_into_profile(
    user_profile: dict[str, Any],
    slots: dict[str, Any],
) -> dict[str, Any]:
    """Inject slots vào session_context khi client dùng format cũ.

    Tạo bản copy mới của session_context để không mutate dict gốc từ Pydantic.
    Chỉ điền các field chưa có trong session_context (slots không overwrite).
    """
    session = dict(user_profile.get("session_context") or {})

    for key in ("destination", "check_in", "check_out", "number_of_guests",
                "has_pet", "has_children", "nearby_place"):
        if key not in session and slots.get(key) is not None:
            session[key] = slots[key]

    price = dict(session.get("session_price_range") or {})
    if "min" not in price and slots.get("budget_min") is not None:
        price["min"] = slots["budget_min"]
    if "max" not in price and slots.get("budget_max") is not None:
        price["max"] = slots["budget_max"]
    if price:
        session["session_price_range"] = price

    return {**user_profile, "session_context": session}


@router.post("")
async def chat(req: ChatRequest):
    user_profile: dict[str, Any] = {**req.user_profile, "user_id": req.user_id}

    if req.slots:
        user_profile = _merge_slots_into_profile(user_profile, req.slots)

    state = {
        "user_id": req.user_id,
        "session_id": req.session_id,
        "raw_query": req.query,
        "user_profile": user_profile,
        "slots": req.slots,
        "rerank_options": req.rerank_options,
        "request_started_at": time.perf_counter(),
    }
    result = await graph.ainvoke(state)
    response = result.get("final_response", result)
    latency = result.get("latency_summary")
    if latency and isinstance(response, dict):
        return {**response, "latency": latency}
    return response
