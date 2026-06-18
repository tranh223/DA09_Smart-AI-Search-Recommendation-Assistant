"""Tầng hội thoại: giữ lịch sử theo session + HIỂU NGỮ CẢNH và Ý ĐỊNH của người dùng.

Vì mỗi lần gợi ý vẫn chạy qua recommend()/search() (stateless), ta dùng một LLM
"understanding" nhận LỊCH SỬ + CÂU MỚI để trả về:
    · intent           — recommend | refine | question | chitchat
    · standalone_query — câu yêu cầu ĐỘC LẬP đã ghép ngữ cảnh (cho recommend/refine)
    · is_general       — true khi muốn gợi ý nhưng KHÔNG nêu ràng buộc nào (-> nhánh CF+interest)

Từ đó chat() ĐỊNH TUYẾN: chỉ chạy retrieval khi cần (recommend/refine), còn
question/chitchat thì trả lời trực tiếp bằng LLM dựa trên các gợi ý gần nhất.

Lịch sử + gợi ý gần nhất lưu trong RAM theo session_id (demo). Production nên thay
bằng store bền vững.
"""

from __future__ import annotations

import json

from app.core import trace
from app.core.llm_client import OPENAI_MODEL, get_openai
from app.services.recommender import get_hotel_facts, recommend

# session_id -> list[{"role": "user"|"assistant", "content": str}]
_SESSIONS: dict[str, list[dict]] = {}
# session_id -> danh sách gợi ý gần nhất (đầy đủ field) để trả lời câu hỏi tiếp theo.
_LAST_RECS: dict[str, list[dict]] = {}

# Số lượt (user+assistant) tối đa giữ lại để tránh prompt phình to.
_MAX_TURNS = 8

# --------------------------------------------------------------------------- #
# 1. LLM hiểu ngữ cảnh + ý định
# --------------------------------------------------------------------------- #
_UNDERSTAND_SYSTEM = """\
Bạn là bộ PHÂN TÍCH Ý ĐỊNH cho một trợ lý gợi ý khách sạn. Nhận LỊCH SỬ hội thoại và
CÂU MỚI của người dùng, trả về JSON mô tả ý định. Chỉ trả JSON đúng schema, không giải thích.

intent — chọn MỘT:
- "recommend": muốn tìm/gợi ý khách sạn, là yêu cầu MỚI (vd "tìm khách sạn ở Đà Nẵng có hồ bơi").
- "refine": ĐIỀU CHỈNH yêu cầu trước đó, có tham chiếu ngữ cảnh (vd "rẻ hơn nữa", "gần biển hơn",
  "thế còn ở Nha Trang", "loại khách sạn vừa rồi").
- "question": HỎI về một khách sạn/đề xuất ĐÃ được giới thiệu (vd "cái số 2 có hồ bơi không",
  "giá phòng khách sạn đầu tiên", "chỗ đó cách biển bao xa").
- "chitchat": chào hỏi, cảm ơn, hoặc nội dung KHÔNG liên quan tới việc tìm khách sạn.

standalone_query:
- Với recommend/refine: VIẾT LẠI câu mới thành MỘT yêu cầu ĐỘC LẬP, đầy đủ ngữ cảnh bằng tiếng
  Việt; giữ lại các ràng buộc trước đó vẫn còn hiệu lực. Nếu là recommend/refine nhưng người dùng
  KHÔNG nêu ràng buộc nào, để null.
- Với question/chitchat: để null.

is_general:
- true khi người dùng muốn được GỢI Ý nhưng KHÔNG nêu ràng buộc cụ thể nào (không địa điểm,
  không ngân sách, không tiện nghi — vd "gợi ý cho tôi vài chỗ đi", "có gì hay không").
- false trong mọi trường hợp còn lại (có ít nhất một ràng buộc, hoặc intent là question/chitchat).
"""

_UNDERSTAND_SCHEMA = {
    "name": "understanding",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["recommend", "refine", "question", "chitchat"],
            },
            "standalone_query": {"type": ["string", "null"]},
            "is_general": {"type": "boolean"},
        },
        "required": ["intent", "standalone_query", "is_general"],
        "additionalProperties": False,
    },
}


def _format_history(history: list[dict]) -> str:
    return "\n".join(
        f"{'Người dùng' if t['role'] == 'user' else 'Trợ lý'}: {t['content']}"
        for t in history
    )


def understand(history: list[dict], message: str) -> dict:
    """Phân tích câu mới (+ lịch sử) -> {intent, standalone_query, is_general}.

    Không history và câu có vẻ là yêu cầu tìm KS -> vẫn để LLM quyết; rỗng lịch sử thì
    refine hiếm khi xảy ra. Lỗi/parse hỏng -> mặc định coi là recommend với chính câu đó.
    """
    convo = _format_history(history)
    user_content = (
        (f"LỊCH SỬ:\n{convo}\n\n" if convo else "") + f"CÂU MỚI: {message}"
    )
    client = get_openai()
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": _UNDERSTAND_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_schema", "json_schema": _UNDERSTAND_SCHEMA},
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:  # noqa: BLE001 — hỏng thì fallback an toàn về recommend.
        return {"intent": "recommend", "standalone_query": message, "is_general": False}
    return data


# --------------------------------------------------------------------------- #
# 2. LLM trả lời trực tiếp (question / chitchat)
# --------------------------------------------------------------------------- #
_ANSWER_SYSTEM = """\
Bạn là trợ lý tư vấn khách sạn thân thiện, xưng "bạn". Trả lời NGẮN GỌN, tự nhiên câu hỏi
hoặc lời nhắn của người dùng dựa trên NGỮ CẢNH hội thoại và các khách sạn đã gợi ý.

- Khi người dùng hỏi CHI TIẾT một khách sạn (vd có view biển không, có hồ bơi không, giá phòng,
  hạng phòng...) mà bạn CHƯA có dữ liệu đó, hãy GỌI TOOL get_hotel_details để tra cứu trong cơ
  sở dữ liệu rồi mới trả lời. Ưu tiên truyền hotel_id lấy từ danh sách đã gợi ý; nếu không có thì
  truyền name (tên khách sạn người dùng nhắc).
- Chỉ khẳng định những gì CÓ trong dữ liệu trả về. Nếu tra cứu xong vẫn không thấy thông tin đó,
  thành thật nói chưa có và mời người dùng xem chi tiết trực tiếp — TUYỆT ĐỐI không bịa tiện nghi,
  giá, khoảng cách.
- Nếu chỉ là chào hỏi/cảm ơn, đáp lại lịch sự, ấm áp, ngắn gọn và ngỏ ý sẵn sàng giúp tìm khách sạn
  (KHÔNG cần gọi tool).
- Không emoji, không markdown. Xưng hô DUY NHẤT bằng "bạn".
"""

_ANSWER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_hotel_details",
            "description": (
                "Tra cứu chi tiết một khách sạn trong cơ sở dữ liệu: tiện nghi/đặc điểm "
                "(tag theo nhóm như view, hồ bơi, vị trí...), các hạng phòng và giá, hạng sao, "
                "điểm đánh giá. Dùng khi người dùng hỏi thông tin một khách sạn cụ thể."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hotel_id": {
                        "type": "integer",
                        "description": "ID khách sạn (ưu tiên — lấy từ danh sách đã gợi ý).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Tên (một phần) khách sạn, dùng khi không có hotel_id.",
                    },
                },
                "additionalProperties": False,
            },
        },
    }
]

# Số vòng tool tối đa để tránh lặp vô hạn.
_MAX_TOOL_HOPS = 3


def _format_recs(recs: list[dict]) -> str:
    if not recs:
        return "(chưa gợi ý khách sạn nào)"
    lines = []
    for r in recs:
        price = f"{int(r['min_price']):,}".replace(",", ".") + "đ" if r.get("min_price") else "?"
        lines.append(
            f"id={r.get('hotel_id')} | {r.get('rank')}. {r.get('name')} | {r.get('city')} | "
            f"{r.get('star_rating')}★ | điểm {r.get('review_score')} | giá từ {price}"
        )
    return "\n".join(lines)


def _run_answer_tool(name: str, args: dict) -> str:
    """Thực thi tool do LLM gọi -> trả JSON chuỗi để đưa lại cho model."""
    if name == "get_hotel_details":
        rows = get_hotel_facts(hotel_id=args.get("hotel_id"), name=args.get("name"))
        return json.dumps(rows, ensure_ascii=False, default=str)
    return json.dumps({"error": f"tool không tồn tại: {name}"}, ensure_ascii=False)


def _answer(history: list[dict], message: str, last_recs: list[dict]) -> str:
    """Trả lời question/chitchat. Cho phép LLM GỌI TOOL tự truy vấn graph khi cần
    chi tiết khách sạn (agentic loop), tối đa _MAX_TOOL_HOPS vòng."""
    convo = _format_history(history)
    user_content = (
        (f"LỊCH SỬ:\n{convo}\n\n" if convo else "")
        + f"CÁC KHÁCH SẠN ĐÃ GỢI Ý GẦN NHẤT:\n{_format_recs(last_recs)}\n\n"
        + f"CÂU MỚI: {message}"
    )
    messages: list[dict] = [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    client = get_openai()
    for _ in range(_MAX_TOOL_HOPS):
        with trace.step("Soạn câu trả lời") as s:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.4,
                messages=messages,
                tools=_ANSWER_TOOLS,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                s.note("trả lời trực tiếp (không gọi tool)")
                return (msg.content or "").strip()
            s.note(f"gọi {len(msg.tool_calls)} tool")

        # Ghi lại lượt gọi tool của assistant rồi nạp kết quả từng tool.
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            with trace.step("Tra cứu thông tin khách sạn") as s:
                result = _run_answer_tool(call.function.name, args)
                s.note(f"{call.function.name} args={args}")
                s.note(f"-> {len(result)} ký tự dữ liệu")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

    # Hết hạn mức tool -> ép model chốt câu trả lời từ dữ liệu đã có.
    final = client.chat.completions.create(
        model=OPENAI_MODEL, temperature=0.4, messages=messages
    )
    return (final.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- #
# 3. Điều phối một lượt chat
# --------------------------------------------------------------------------- #
def _remember(history: list[dict], message: str, assistant_summary: str) -> None:
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": assistant_summary})
    del history[:-_MAX_TURNS]  # chỉ giữ _MAX_TURNS lượt gần nhất


def chat(session_id: str, user_id: str, message: str, top_k: int = 5) -> dict:
    """Xử lý một lượt chat có ngữ cảnh + định tuyến theo ý định.

    Trả về dict gồm "intent" và:
    - recommend/refine -> như recommend(): {profile, query, intro, recommendations, ...}
      kèm "resolved_query" (yêu cầu độc lập đã suy ra).
    - question/chitchat -> {"reply": <câu trả lời trực tiếp>, "recommendations": []}.

    Raise ValueError nếu user không hợp lệ / không có gợi ý (server xử lý hiển thị).
    """
    history = _SESSIONS.setdefault(session_id, [])
    with trace.step("Hiểu yêu cầu của bạn") as s:
        intent_info = understand(history, message)
        intent = intent_info.get("intent", "recommend")
        s.note(
            f"intent={intent} · general={intent_info.get('is_general')} · "
            f"query={intent_info.get('standalone_query')!r}"
        )

    if intent in ("recommend", "refine"):
        standalone = intent_info.get("standalone_query") or message
        # Không ràng buộc -> query=None để kích hoạt nhánh gợi ý chung (interest + CF).
        query = None if intent_info.get("is_general") else standalone

        result = recommend(user_id, query=query, top_k=top_k)
        result["intent"] = intent
        result["resolved_query"] = standalone

        _LAST_RECS[session_id] = result["recommendations"]
        summary = "Đã gợi ý: " + "; ".join(
            f"{r['rank']}. {r['name']}" for r in result["recommendations"]
        )
        _remember(history, message, summary)
        return result

    # question / chitchat -> trả lời trực tiếp, không chạy retrieval.
    reply = _answer(history, message, _LAST_RECS.get(session_id, []))
    _remember(history, message, reply)
    return {
        "intent": intent,
        "reply": reply,
        "resolved_query": message,
        "recommendations": [],
    }


def reset_session(session_id: str) -> None:
    """Xoá lịch sử + gợi ý gần nhất của một session (bắt đầu hội thoại mới)."""
    _SESSIONS.pop(session_id, None)
    _LAST_RECS.pop(session_id, None)
