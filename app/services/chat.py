"""Tầng hội thoại: giữ lịch sử theo session + hiểu ngữ cảnh câu nối tiếp.

Vì mỗi lần gợi ý vẫn chạy qua recommend()/search() (stateless), ta xử lý ngữ cảnh
bằng kỹ thuật "condense": dựa trên lịch sử hội thoại, VIẾT LẠI câu mới nhất thành một
yêu cầu ĐỘC LẬP, đầy đủ (vd "rẻ hơn nữa" -> "... ở Đà Nẵng có view biển, giá rẻ hơn"),
rồi mới đưa vào recommend(). Nhờ đó câu nối tiếp được hiểu đúng ngữ cảnh.

Lịch sử lưu trong RAM theo session_id (demo). Production nên thay bằng store bền vững.
"""

from __future__ import annotations

from app.core.llm_client import OPENAI_MODEL, get_openai
from app.services.recommender import recommend

# session_id -> list[{"role": "user"|"assistant", "content": str}]
_SESSIONS: dict[str, list[dict]] = {}

# Số lượt (user+assistant) tối đa giữ lại để tránh prompt phình to.
_MAX_TURNS = 8

_CONDENSE_SYSTEM = """\
Bạn nhận LỊCH SỬ hội thoại và CÂU MỚI của người dùng (về tìm/gợi ý khách sạn).
Nhiệm vụ: viết lại CÂU MỚI thành MỘT yêu cầu ĐỘC LẬP, đầy đủ ngữ cảnh bằng tiếng Việt.

Quy tắc:
- Nếu câu mới THAM CHIẾU ngữ cảnh trước (vd "rẻ hơn nữa", "thế còn ở Nha Trang", "khách sạn
  đó", "cái số 2", "gần biển hơn"), hãy BỔ SUNG thông tin từ lịch sử để câu trở nên đầy đủ,
  giữ lại các ràng buộc trước đó vẫn còn hiệu lực.
- Nếu câu mới ĐÃ là một yêu cầu độc lập / đổi chủ đề, GIỮ NGUYÊN, không ghép ngữ cảnh cũ.
- Chỉ trả về DUY NHẤT câu yêu cầu, không giải thích, không thêm tiền tố.
"""


def _condense(history: list[dict], message: str) -> str:
    """Viết lại câu mới thành yêu cầu độc lập dựa trên lịch sử. Không history -> giữ nguyên."""
    if not history:
        return message

    convo = "\n".join(
        f"{'Người dùng' if t['role'] == 'user' else 'Trợ lý'}: {t['content']}"
        for t in history
    )
    client = get_openai()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _CONDENSE_SYSTEM},
            {"role": "user", "content": f"LỊCH SỬ:\n{convo}\n\nCÂU MỚI: {message}"},
        ],
    )
    return (response.choices[0].message.content or message).strip()


def chat(session_id: str, user_id: str, message: str, top_k: int = 5) -> dict:
    """Xử lý một lượt chat có ngữ cảnh -> kết quả gợi ý (như recommend()).

    Thêm khoá "resolved_query": yêu cầu độc lập đã được suy ra từ ngữ cảnh.
    Raise ValueError nếu user không hợp lệ / không có gợi ý (server xử lý hiển thị).
    """
    history = _SESSIONS.setdefault(session_id, [])
    standalone = _condense(history, message)

    result = recommend(user_id, query=standalone, top_k=top_k)

    # Ghi lại lượt: lưu câu GỐC của user + tóm tắt gợi ý (để hiểu "cái số 2"...).
    history.append({"role": "user", "content": message})
    summary = "Đã gợi ý: " + "; ".join(
        f"{r['rank']}. {r['name']}" for r in result["recommendations"]
    )
    history.append({"role": "assistant", "content": summary})
    del history[:-_MAX_TURNS]  # chỉ giữ _MAX_TURNS lượt gần nhất

    result["resolved_query"] = standalone
    return result


def reset_session(session_id: str) -> None:
    """Xoá lịch sử một session (bắt đầu hội thoại mới)."""
    _SESSIONS.pop(session_id, None)
