"""FastAPI backend cho frontend chat: POST /chat (SSE) -> gợi ý cá nhân hóa.

Hợp đồng SSE khớp frontend (frontend/src/api/chat.ts):
    event: step    data: {"name": str, "ms": int, "depth": int}   # bước reasoning (live)
    event: token   data: {"text": "..."}      # các mẩu chữ giới thiệu (tuỳ chọn)
    event: result  data: {"clarifying_question": str|null, "cards": [...]}
    (kết thúc stream = done)

Chạy:
    uvicorn app.api.server:app --port 8000 --reload
"""

from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.api.schemas import CTA, ChatRequest, Price, RecommendationCard
from app.core import trace
from app.services.chat import chat as chat_turn

app = FastAPI(title="OTA Travel Assistant API")

# Dev: cho phép frontend gọi trực tiếp (vite cũng đã proxy /api -> :8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _step_payload(event: dict) -> dict:
    """Rút gọn sự kiện trace cho frontend: tên bước + thời gian (ms) + độ sâu.
    (Các `notes` chi tiết kỹ thuật chỉ giữ ở terminal, không gửi ra UI.)"""
    return {
        "name": event["name"],
        "ms": round(event["seconds"] * 1000),
        "depth": event["depth"],
    }


def _to_card(rec: dict) -> RecommendationCard:
    """Map một gợi ý (recommend) -> RecommendationCard cho frontend."""
    star = int(rec["star_rating"]) if rec.get("star_rating") else None
    price = (
        Price(amount=float(rec["min_price"]), currency="VND", unit="đêm")
        if rec.get("min_price") is not None
        else None
    )
    chips = []
    if rec.get("city"):
        chips.append(rec["city"])
    if star:
        chips.append(f"{star}★")

    hid = rec["hotel_id"]
    return RecommendationCard(
        entity_id=str(hid),
        entity_type="hotel",
        title=rec["name"],
        subtitle=rec.get("city"),
        price=price,
        rating=rec.get("review_score"),
        review_count=int(rec["review_count"]) if rec.get("review_count") is not None else None,
        star=star,
        chips=chips,
        badges=[f"Top {rec['rank']}"] if rec.get("rank") else [],
        reasons=[rec["reason"]] if rec.get("reason") else [],
        cta=[CTA(label="Xem chi tiết", action="view_details", deep_link=f"/hotel/{hid}")],
    )


def _chat_stream(req: ChatRequest):
    user_id = (req.user_id or "").strip()
    if not user_id:
        yield _sse("result", {
            "clarifying_question": "Vui lòng nhập user_id để mình gợi ý phù hợp nhé.",
            "cards": [],
        })
        return

    message = req.message.strip()
    if not message:
        yield _sse("result", {
            "clarifying_question": "Bạn muốn tìm khách sạn như thế nào?",
            "cards": [],
        })
        return

    # chat_turn() chặn (blocking) và phát trace bên trong, nên chạy ở THREAD riêng và
    # đẩy từng sự kiện bước qua hàng đợi -> generator này stream `step` xuống frontend
    # NGAY khi mỗi bước xong (live), rồi mới gửi kết quả cuối.
    events: queue.Queue = queue.Queue()
    box: dict = {}

    def _sink(event: dict) -> None:
        trace.stdout_sink(event)  # vẫn in ra terminal server
        events.put(("step", event))

    def _worker() -> None:
        trace.set_sink(_sink)  # sink riêng cho thread/request này (ContextVar)
        try:
            box["result"] = chat_turn(req.session_id, user_id, message, top_k=5)
        except ValueError as exc:
            box["clarify"] = str(exc)
        except Exception:  # noqa: BLE001
            box["clarify"] = "Xin lỗi, có lỗi khi tạo gợi ý. Bạn thử lại nhé."
        finally:
            events.put(("done", None))

    threading.Thread(target=_worker, daemon=True).start()

    # Bơm các bước reasoning ra frontend cho tới khi worker báo xong.
    while True:
        kind, payload = events.get()
        if kind == "done":
            break
        yield _sse("step", _step_payload(payload))

    if "clarify" in box:
        yield _sse("result", {"clarifying_question": box["clarify"], "cards": []})
        return
    result = box["result"]

    # Hỏi đáp / chitchat: trả lời trực tiếp bằng văn bản, không có thẻ khách sạn.
    reply = result.get("reply")
    if reply:
        for word in reply.split(" "):
            yield _sse("token", {"text": word + " "})
        yield _sse("result", {"clarifying_question": None, "cards": []})
        return

    cards = [_to_card(r) for r in result["recommendations"]]
    if not cards:
        yield _sse("result", {
            "clarifying_question": "Mình chưa tìm được gợi ý phù hợp. Bạn thử yêu cầu khác nhé.",
            "cards": [],
        })
        return

    # Câu mở đầu do LLM sinh (concierge nói chuyện tự nhiên), không hardcode.
    intro = result.get("intro") or "Đây là một vài gợi ý mình đã chọn lọc cho bạn:"
    for word in intro.split(" "):
        yield _sse("token", {"text": word + " "})

    yield _sse("result", {
        "clarifying_question": None,
        "cards": [c.model_dump() for c in cards],
    })


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_chat_stream(req), media_type="text/event-stream")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
