"""
Response Builder — tổng hợp kết quả RAG + recommendation bằng LLM.

Nhận: rag_answer, ranked_recommendations, intent, slots, raw_query
Trả: synthesized_answer, hotel_reasons, next_suggestions

Dùng cùng OpenAIResponsesClient với query_understanding để tận dụng
retry logic và structured-output schema đã có sẵn.

Fallback: nếu LLM không khởi tạo được hoặc timeout, trả về plain-text
tĩnh để luồng không bị block.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Lazy singleton cho OpenAIResponsesClient ─────────────────────────────────
_llm_lock = threading.Lock()
_llm_client: Any = None
_llm_init_failed = False


def _get_llm_client() -> Any:
    """Trả về singleton OpenAIResponsesClient, hoặc None nếu không khả dụng."""
    global _llm_client, _llm_init_failed
    if _llm_init_failed:
        return None
    if _llm_client is not None:
        return _llm_client
    with _llm_lock:
        if _llm_client is not None:
            return _llm_client
        try:
            from app.query_understanding.llm.openai_client import OpenAIResponsesClient
            _llm_client = OpenAIResponsesClient(
                timeout_seconds=float(os.getenv("RESPONSE_BUILDER_TIMEOUT_SECONDS", "25") or "25"),
                max_retries=int(os.getenv("RESPONSE_BUILDER_MAX_RETRIES", "1") or "1"),
            )
            logger.info("[response_builder] OpenAIResponsesClient initialized.")
        except Exception as exc:  # noqa: BLE001
            _llm_init_failed = True
            logger.warning(
                "[response_builder] LLM client init failed — fallback active. "
                "error=%s: %s",
                type(exc).__name__,
                exc,
            )
    return _llm_client


# ── JSON schema cho structured output (strict-mode compatible) ────────────────
# hotel_reasons dùng array of objects thay vì additionalProperties để tương
# thích với strict=True của OpenAI Responses API.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "Câu trả lời tổng hợp ngắn gọn bằng tiếng Việt (2-3 câu)",
        },
        "hotel_reasons": {
            "type": "array",
            "description": "Lý do cụ thể tại sao mỗi khách sạn phù hợp",
            "items": {
                "type": "object",
                "properties": {
                    "hotel_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["hotel_id", "reason"],
                "additionalProperties": False,
            },
        },
        "next_suggestions": {
            "type": "array",
            "description": "2-3 câu hỏi gợi ý ngắn để người dùng tinh chỉnh",
            "items": {"type": "string"},
        },
    },
    "required": ["answer", "hotel_reasons", "next_suggestions"],
    "additionalProperties": False,
}

_SYSTEM_INSTRUCTIONS = (
    "Bạn là trợ lý AI của nền tảng đặt phòng OTA tại Việt Nam. "
    "Nhiệm vụ: tổng hợp kết quả tìm kiếm thành câu trả lời thân thiện, "
    "giải thích lý do gợi ý cụ thể cho từng khách sạn và đề xuất câu hỏi "
    "tiếp theo giúp người dùng tinh chỉnh. "
    "Viết bằng tiếng Việt, ngắn gọn và thực tế. "
    "Lý do phải cụ thể: đề cập giá, tiện nghi nổi bật, vị trí hoặc điểm đặc trưng."
)


def _build_prompt(
    *,
    query: str,
    intent: str,
    destination: str,
    rag_answer: str,
    hotels: list[dict[str, Any]],
) -> str:
    hotel_lines: list[str] = []
    for h in hotels[:6]:
        hotel_id = str(h.get("hotel_id") or h.get("item_id") or "?")
        name = h.get("hotel_name") or h.get("name") or hotel_id
        score = h.get("score", 0.0)
        reasons = ", ".join(h.get("reasons") or [])
        warnings = ", ".join(h.get("warnings") or [])
        meta = h.get("metadata") or {}
        price_min = meta.get("price_min")
        price_max = meta.get("price_max")
        price_str = (
            f"{int(price_min):,}–{int(price_max):,} VNĐ"
            if price_min and price_max
            else ""
        )
        parts = [f"ID={hotel_id}", f"Tên={name}", f"Điểm={score:.2f}"]
        if price_str:
            parts.append(f"Giá={price_str}")
        if reasons:
            parts.append(f"Điểm mạnh={reasons}")
        if warnings:
            parts.append(f"Lưu ý={warnings}")
        hotel_lines.append("- " + " | ".join(parts))

    rag_section = (
        f"\nThông tin tra cứu (RAG):\n{rag_answer.strip()}\n"
        if rag_answer.strip()
        else ""
    )

    hotels_section = "\n".join(hotel_lines) if hotel_lines else "(chưa có gợi ý)"

    return (
        f"Truy vấn người dùng: {query}\n"
        f"Intent: {intent}\n"
        f"Điểm đến: {destination or 'chưa xác định'}"
        f"{rag_section}"
        f"\nDanh sách khách sạn gợi ý:\n{hotels_section}"
    )


def _fallback_response(
    ranked_recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fallback plain-text khi LLM không khả dụng."""
    count = len(ranked_recommendations)
    answer = (
        f"Tìm thấy {count} khách sạn phù hợp với yêu cầu của bạn."
        if count > 0
        else "Hiện chưa tìm thấy khách sạn phù hợp, vui lòng thử với tiêu chí khác."
    )
    return {
        "synthesized_answer": answer,
        "hotel_reasons": {},
        "next_suggestions": [
            "Bạn muốn lọc thêm theo mức giá không?",
            "Bạn có yêu cầu đặc biệt về tiện nghi không?",
            "Bạn cần phòng cho bao nhiêu người?",
        ],
    }

def build_response_with_llm(
    *,
    query: str,
    intent: str,
    destination: str,
    rag_answer: str,
    ranked_recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Tổng hợp kết quả RAG + recommendation bằng LLM.

    Returns:
        Dict với 3 key:
        - synthesized_answer (str): câu trả lời tổng hợp
        - hotel_reasons (dict[str, str]): {hotel_id → lý do}
        - next_suggestions (list[str]): gợi ý câu hỏi tiếp theo
    """
    client = _get_llm_client()
    if client is None:
        return _fallback_response(ranked_recommendations)

    prompt = _build_prompt(
        query=query,
        intent=intent,
        destination=destination,
        rag_answer=rag_answer,
        hotels=ranked_recommendations,
    )

    try:
        raw = client.create_structured_output(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            instructions=_SYSTEM_INSTRUCTIONS,
            input_text=prompt,
            schema_name="ota_response_builder",
            schema=_RESPONSE_SCHEMA,
        )
        hotel_reasons: dict[str, str] = {
            str(item["hotel_id"]): str(item["reason"])
            for item in (raw.get("hotel_reasons") or [])
            if item.get("hotel_id") and item.get("reason")
        }
        return {
            "synthesized_answer": raw.get("answer") or "",
            "hotel_reasons": hotel_reasons,
            "next_suggestions": [
                str(s) for s in (raw.get("next_suggestions") or []) if s
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[response_builder] LLM call failed — fallback. error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return _fallback_response(ranked_recommendations)
