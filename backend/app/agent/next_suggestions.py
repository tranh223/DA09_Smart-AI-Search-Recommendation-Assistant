"""Generate stable next-suggestion buttons for the chat UI.

This module keeps the public API unchanged: callers still receive
``next_suggestions: list[str]``. Internally it separates suggestions into
three UX modes:

- init: search-starting actions for a cold / low-context session.
- missing_info: quick answers to the assistant's clarification question.
- related_info: follow-up needs after a recommendation answer.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import unicodedata
from typing import Any, Literal

logger = logging.getLogger(__name__)

SuggestionType = Literal["init", "missing_info", "related_info"]

SUGGESTION_COUNT = 4
MAX_SUGGESTION_CHARS = 56

_SUGGESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "description": "Exactly 4 short Vietnamese chat button labels.",
            "items": {"type": "string"},
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

_SYSTEM_INSTRUCTIONS = (
    "You generate short Vietnamese quick-reply buttons for a hotel booking chat. "
    "Return exactly 4 useful items. Keep each item concise and directly sendable "
    "as the user's next chat message. Do not include numbering or quotation marks."
)

_client_lock = threading.Lock()
_client: Any = None
_client_init_failed = False

_INIT_FALLBACKS = [
    "Tìm resort gần biển",
    "Khách sạn cho gia đình",
    "Gần trung tâm",
    "Có hồ bơi",
]

_MISSING_INFO_FALLBACKS = [
    "2 người - 2 ngày 1 đêm",
    "4 người - 1 ngày 1 đêm",
    "Gia đình 4 người - 3 ngày 2 đêm",
    "Ngân sách 1-2 triệu/đêm",
]

_DEFAULT_BUDGET_SUGGESTIONS = [
    "Dưới 2 triệu",
    "2-4 triệu",
    "4-8 triệu",
    "Trên 8 triệu",
]

_BUDGET_SUGGESTIONS_BY_LEVEL = {
    "low": [
        "Dưới 1 triệu",
        "1-2 triệu",
        "2-4 triệu",
        "Dưới 2 triệu",
    ],
    "medium": [
        "Dưới 2 triệu",
        "2-4 triệu",
        "4-8 triệu",
        "Trên 8 triệu",
    ],
    "high": [
        "4-8 triệu",
        "8-12 triệu",
        "12-20 triệu",
        "Trên 20 triệu",
    ],
}

_RELATED_INFO_FALLBACKS = [
    "Giá phòng khoảng bao nhiêu?",
    "Có những loại phòng nào?",
    "Gần điểm tham quan nào?",
    "Chính sách nhận trả phòng?",
]

_QUESTION_PREFIXES = (
    "bạn có muốn",
    "bạn muốn",
    "anh/chị có muốn",
    "anh chị có muốn",
    "quý khách có muốn",
)


def determine_suggestion_type(
    *,
    user_profile: dict[str, Any] | None,
    llm_answer: str,
    needs_clarification: bool = False,
    ranked_recommendations: list[dict[str, Any]] | None = None,
) -> SuggestionType:
    """Choose the suggestion mode from current backend state.

    The content for missing_info is still generated from llm_answer. This
    function only decides which validation and fallback policy to apply.
    """
    if needs_clarification or _looks_like_clarification(llm_answer):
        return "missing_info"
    if ranked_recommendations:
        return "related_info"
    if _profile_has_meaningful_context(user_profile):
        return "related_info"
    return "init"


def build_next_suggestions(
    *,
    client: Any | None,
    suggestion_type: SuggestionType,
    llm_answer: str,
    user_profile: dict[str, Any] | None = None,
    ranked_recommendations: list[dict[str, Any]] | None = None,
    graph_related_info: list[dict[str, Any]] | None = None,
    fallback_items: list[str] | None = None,
) -> list[str]:
    """Generate and validate 4 button labels.

    The caller can pass an existing LLM client from response_builder. When the
    client or graph is unavailable, deterministic fallbacks keep the UI stable.
    """
    if suggestion_type == "missing_info":
        if _looks_like_date_clarification(llm_answer):
            return []
        budget_suggestions = _budget_suggestions_for_clarification(
            user_profile=user_profile or {},
            llm_answer=llm_answer,
        )
        if budget_suggestions:
            return _validate_items(
                budget_suggestions,
                suggestion_type=suggestion_type,
                allow_fill=True,
            )

    local_related_info = (
        build_recommendation_related_info(ranked_recommendations or [])
        if suggestion_type == "related_info"
        else []
    )
    related_info = list(graph_related_info or [])
    if suggestion_type == "related_info":
        related_info = local_related_info + related_info
        if graph_related_info is None and len(local_related_info) < 2:
            related_info.extend(retrieve_graph_related_info(ranked_recommendations or []))
        return _validate_items(
            _post_answer_suggestions(llm_answer, related_info),
            suggestion_type=suggestion_type,
            allow_fill=True,
        )

    fallback = _validate_items(
        fallback_items or _fallback_for_type(suggestion_type),
        suggestion_type=suggestion_type,
        allow_fill=True,
    )

    if client is None:
        client = _get_llm_client()
    if client is None:
        return fallback

    prompt = _build_prompt(
        suggestion_type=suggestion_type,
        llm_answer=llm_answer,
        user_profile=user_profile or {},
        ranked_recommendations=ranked_recommendations or [],
        graph_related_info=related_info or [],
    )
    try:
        raw = client.create_structured_output(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            instructions=_SYSTEM_INSTRUCTIONS,
            input_text=prompt,
            schema_name=f"ota_next_suggestions_{suggestion_type}",
            schema=_SUGGESTION_SCHEMA,
        )
        validated = _validate_items(raw.get("items") or [], suggestion_type=suggestion_type)
        return validated or fallback
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[next_suggestions] generation failed; using fallback. type=%s error=%s: %s",
            suggestion_type,
            type(exc).__name__,
            exc,
        )
        return fallback


def build_recommendation_related_info(
    ranked_recommendations: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Extract compact facts from the recommendation engine output.

    This keeps next_suggestions grounded even when Neo4j is unavailable or the
    reranker already enriched candidates from Postgres / search API.
    """
    facts: list[dict[str, Any]] = []
    for rec in ranked_recommendations[:limit]:
        if not isinstance(rec, dict):
            continue
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        source = {**meta, **rec}
        hotel_id = source.get("hotel_id") or source.get("item_id") or source.get("id")
        name = source.get("hotel_name") or source.get("name") or hotel_id
        tags = _pick_list(source, "tags", "amenities", "location_tags", "room_views", "preference_habits")
        nearby = _pick_list(source, "nearby_places")
        suitable_for = _pick_list(source, "suitable_for")
        facts.append(
            {
                "source": "recommendation_engine",
                "hotel_id": hotel_id,
                "hotel_name": name,
                "rank": source.get("rank"),
                "city": source.get("city") or source.get("destination"),
                "area": source.get("area"),
                "property_type": source.get("property_type") or source.get("accommodation_type") or source.get("hotel_type"),
                "star_rating": source.get("star_rating"),
                "review_score": source.get("review_score"),
                "price_min": source.get("price_min") or source.get("min_price"),
                "price_max": source.get("price_max"),
                "currency": source.get("currency"),
                "tags": tags[:8],
                "nearby": nearby[:5],
                "suitable_for": suitable_for[:5],
                "reasons": _pick_list(source, "reasons")[:5],
                "warnings": _pick_list(source, "warnings")[:3],
            }
        )
    return facts


def _get_llm_client() -> Any:
    global _client, _client_init_failed
    if _client_init_failed:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        try:
            from app.query_understanding.llm.openai_client import OpenAIResponsesClient

            _client = OpenAIResponsesClient(
                timeout_seconds=float(os.getenv("NEXT_SUGGESTIONS_TIMEOUT_SECONDS", "12") or "12"),
                max_retries=int(os.getenv("NEXT_SUGGESTIONS_MAX_RETRIES", "1") or "1"),
            )
        except Exception as exc:  # noqa: BLE001
            _client_init_failed = True
            logger.warning(
                "[next_suggestions] LLM client init failed; using fallback. error=%s: %s",
                type(exc).__name__,
                exc,
            )
    return _client


def retrieve_graph_related_info(
    ranked_recommendations: list[dict[str, Any]],
    *,
    top_hotels: int = 3,
    limit: int = 18,
) -> list[dict[str, Any]]:
    """Read lightweight related facts for top hotels from Neo4j.

    This is intentionally optional and non-fatal. It supports related_info
    suggestions without changing the existing recommendation pipeline.
    """
    hotel_ids = _top_hotel_ids(ranked_recommendations, top_hotels)
    if not hotel_ids:
        return []

    try:
        from neo4j_client import run_read_query  # noqa: PLC0415

        query = """
        UNWIND $hotel_ids AS hotel_id
        MATCH (h:Hotel)
        WHERE h.hotel_id = hotel_id
        OPTIONAL MATCH (h)-[tag_rel:HAS_TAG]->(tag:Tag)
        OPTIONAL MATCH (h)-[near_rel:NEAR]->(place:Place)
        OPTIONAL MATCH (h)-[:LOCATED_IN]->(city:City)
        WITH h, city,
             collect(DISTINCT {
               relation: 'HAS_TAG',
               value: tag.name,
               category: tag.category,
               weight: tag_rel.weight
             }) AS tag_facts,
             collect(DISTINCT {
               relation: 'NEAR',
               value: place.name,
               category: place.type,
               distance_km: near_rel.distance_km
             }) AS near_facts
        RETURN
          h.hotel_id AS hotel_id,
          h.name AS hotel_name,
          city.name AS city,
          [fact IN tag_facts WHERE fact.value IS NOT NULL][..6] AS tags,
          [fact IN near_facts WHERE fact.value IS NOT NULL][..4] AS nearby
        LIMIT $limit
        """
        rows = run_read_query(query, {"hotel_ids": hotel_ids, "limit": limit})
        return [_compact_graph_row(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[next_suggestions] graph related info unavailable; continuing without it. error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return []


def _build_prompt(
    *,
    suggestion_type: SuggestionType,
    llm_answer: str,
    user_profile: dict[str, Any],
    ranked_recommendations: list[dict[str, Any]],
    graph_related_info: list[dict[str, Any]],
) -> str:
    if suggestion_type == "init":
        rule = (
            "Mode init: buttons are search-starting actions, not questions. "
            "Use user profile or long-term memory if available."
        )
    elif suggestion_type == "missing_info":
        rule = (
            "Mode missing_info: the assistant asked for missing information. "
            "Buttons must be answers to that question, not questions. "
            "Do not end any button with a question mark."
        )
    else:
        rule = (
            "Mode related_info: the assistant already answered or recommended hotels. "
            "Buttons are useful follow-up questions or refinement needs, grounded in "
            "the recommended hotels and graph facts."
        )

    profile_summary = _summarize_profile(user_profile)
    hotel_summary = _summarize_hotels(ranked_recommendations)
    graph_summary = _summarize_graph_info(graph_related_info)
    return (
        f"{rule}\n\n"
        f"Assistant answer:\n{llm_answer.strip() or '(empty)'}\n\n"
        f"User profile / long-term memory:\n{profile_summary}\n\n"
        f"Recommended hotels:\n{hotel_summary}\n\n"
        f"Graph related facts:\n{graph_summary}\n\n"
        "Return exactly 4 button labels."
    )


def _validate_items(
    items: list[Any],
    *,
    suggestion_type: SuggestionType,
    allow_fill: bool = False,
) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for raw in items:
        item = _clean_item(str(raw or ""))
        if not item:
            continue
        if suggestion_type == "missing_info" and _is_question_like(item):
            continue
        if suggestion_type == "init" and item.endswith("?"):
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append(item)
        if len(clean) >= SUGGESTION_COUNT:
            break

    if allow_fill and len(clean) < SUGGESTION_COUNT:
        for fallback in _fallback_for_type(suggestion_type):
            item = _clean_item(fallback)
            key = item.casefold()
            if key not in seen:
                clean.append(item)
                seen.add(key)
            if len(clean) >= SUGGESTION_COUNT:
                break
    return clean[:SUGGESTION_COUNT]


def _clean_item(item: str) -> str:
    item = re.sub(r"^\s*[-*]\s*", "", item.strip())
    item = re.sub(r"^\s*\d+[.)]\s*", "", item)
    item = item.strip(" \"'")
    item = re.sub(r"\s+", " ", item)
    if len(item) > MAX_SUGGESTION_CHARS:
        item = item[:MAX_SUGGESTION_CHARS].rstrip(" ,.;:-")
    return item


def _is_question_like(item: str) -> bool:
    lowered = item.casefold().strip()
    return item.endswith("?") or any(lowered.startswith(prefix) for prefix in _QUESTION_PREFIXES)


def _hotel_detail_followup_suggestions(answer: str) -> list[str]:
    if not answer or not answer.strip():
        return []
    hotel_name = _extract_focus_hotel_name(answer)
    if not hotel_name:
        return []

    normalized = _normalize_text_for_matching(answer)
    detail_markers = (
        "thong tin chi tiet",
        "thong tin ve khach san",
        "kham pha",
        "gioi thieu",
        "ma khach san",
        "dia chi",
        "tien nghi",
        "nam xay dung",
        "so phong",
        "nhan phong",
        "tra phong",
    )
    if not any(marker in normalized for marker in detail_markers):
        return []

    covered = {
        "price": _contains_any(normalized, ("gia phong", "gia dao dong", "vnd", "usd", "muc gia", "chi phi")),
        "room": _contains_any(normalized, ("loai phong", "phong nghi", "so phong", "dien tich", "giuong")),
        "amenity": _contains_any(normalized, ("tien nghi", "ho boi", "be boi", "wifi", "spa", "gym", "dich vu")),
        "location": _contains_any(normalized, ("vi tri", "dia chi", "gan", "trung tam", "diem tham quan")),
        "policy": _contains_any(normalized, ("chinh sach", "nhan phong", "tra phong", "check-in", "check-out", "tre em")),
        "review": _contains_any(normalized, ("danh gia", "review", "diem", "nhan xet", "khach luu tru")),
        "food": _contains_any(normalized, ("bua sang", "nha hang", "am thuc", "an uong")),
        "transport": _contains_any(normalized, ("san bay", "dua don", "taxi", "di chuyen", "xe dua don")),
        "family": _contains_any(normalized, ("gia dinh", "tre em", "cap doi", "nhom ban")),
    }

    missing_first = [
        ("price", "Giá phòng khoảng bao nhiêu?"),
        ("room", "Có những loại phòng nào?"),
        ("amenity", "Khách sạn có tiện nghi gì?"),
        ("location", "Gần điểm tham quan nào?"),
        ("policy", "Chính sách nhận trả phòng?"),
        ("review", "Đánh giá khách lưu trú ra sao?"),
        ("food", "Có bao gồm bữa sáng không?"),
        ("transport", "Di chuyển từ sân bay thế nào?"),
        ("family", "Có phù hợp gia đình không?"),
    ]
    deeper_followups = [
        "Phòng nào đáng chọn nhất?",
        "Có phụ thu trẻ em không?",
        "Có hồ bơi hoặc bãi biển không?",
        "Khu vực xung quanh có gì?",
        "Có chính sách hủy phòng không?",
        "Có dịch vụ đưa đón không?",
    ]

    suggestions: list[str] = []
    for aspect, suggestion in missing_first:
        if not covered[aspect]:
            suggestions.append(suggestion)
        if len(suggestions) >= SUGGESTION_COUNT:
            return suggestions

    for suggestion in deeper_followups:
        suggestions.append(suggestion)
        if len(suggestions) >= SUGGESTION_COUNT:
            return suggestions
    return suggestions[:SUGGESTION_COUNT]


def _post_answer_suggestions(answer: str, related_info: list[dict[str, Any]]) -> list[str]:
    return [
        "Tôi muốn đặt phòng",
        "So sánh với khách sạn khác",
        "Tôi muốn tham khảo thêm khách sạn khác",
        _dynamic_hotel_followup_question(answer, related_info),
    ]


def _dynamic_hotel_followup_question(answer: str, related_info: list[dict[str, Any]]) -> str:
    normalized_answer = _normalize_text_for_matching(answer)
    all_tags = {
        _normalize_text_for_matching(_fact_value(tag))
        for row in related_info
        for tag in (row.get("tags") or [])
        if _fact_value(tag)
    }
    all_nearby = {
        _normalize_text_for_matching(_fact_value(place))
        for row in related_info
        for place in (row.get("nearby") or row.get("nearby_places") or [])
        if _fact_value(place)
    }
    all_suitable = {
        _normalize_text_for_matching(_fact_value(item))
        for row in related_info
        for item in (row.get("suitable_for") or [])
        if _fact_value(item)
    }

    has_pool_fact = any("ho boi" in tag or "be boi" in tag or "pool" in tag for tag in all_tags)
    has_beach_fact = any("bien" in item or "beach" in item for item in all_tags | all_nearby)
    has_family_fact = any("gia dinh" in item or "tre" in item or "family" in item for item in all_suitable | all_tags)
    has_center_fact = any("trung tam" in item or "center" in item for item in all_tags | all_nearby)

    answer_mentions_price = _contains_any(normalized_answer, ("gia phong", "gia dao dong", "vnd", "usd", "chi phi"))
    answer_mentions_room = _contains_any(normalized_answer, ("loai phong", "phong nghi", "giuong", "dien tich"))
    answer_mentions_amenity = _contains_any(normalized_answer, ("tien nghi", "ho boi", "be boi", "wifi", "spa", "gym"))
    answer_mentions_location = _contains_any(normalized_answer, ("vi tri", "dia chi", "gan", "trung tam", "diem tham quan"))
    answer_mentions_policy = _contains_any(normalized_answer, ("chinh sach", "nhan phong", "tra phong", "check in", "check out", "tre em"))
    answer_mentions_review = _contains_any(normalized_answer, ("danh gia", "review", "nhan xet", "diem so", "khach luu tru"))

    if has_pool_fact and "ho boi" not in normalized_answer and "be boi" not in normalized_answer:
        return "Khách sạn này có hồ bơi không?"
    if has_beach_fact and "bien" not in normalized_answer:
        return "Khách sạn này cách biển bao xa?"
    if has_family_fact and "gia dinh" not in normalized_answer:
        return "Khách sạn này có phù hợp gia đình không?"
    if has_center_fact and "trung tam" not in normalized_answer:
        return "Di chuyển vào trung tâm thế nào?"
    if all_nearby and not answer_mentions_location:
        return "Khách sạn này gần điểm tham quan nào?"
    if not answer_mentions_price:
        return "Giá phòng khách sạn này bao nhiêu?"
    if not answer_mentions_room:
        return "Khách sạn này có những loại phòng nào?"
    if not answer_mentions_policy:
        return "Chính sách nhận trả phòng thế nào?"
    if not answer_mentions_review:
        return "Đánh giá khách lưu trú ra sao?"
    if not answer_mentions_amenity:
        return "Khách sạn này có tiện nghi gì nổi bật?"
    return "Tôi muốn biết thêm về khách sạn này"


def _extract_focus_hotel_name(answer: str) -> str | None:
    patterns = (
        r"#+\s*(?:thông tin(?: chi tiết)?(?: về)?|giới thiệu|khám phá)\s+(?:khách sạn\s+)?\*\*([^*\n]{3,90})\*\*",
        r"#+\s*(?:thông tin(?: chi tiết)?(?: về)?|giới thiệu|khám phá)\s+(?:khách sạn\s+)?([^\n]{3,90})",
        r"(?:thông tin(?: chi tiết)?(?: về)?|giới thiệu|khám phá)\s+(?:khách sạn\s+)?\*\*([^*\n]{3,90})\*\*",
        r"(?:tên khách sạn|khách sạn)\s*:\s*\*\*?([^*\n]{3,90})\*\*?",
        r"\*\*((?=[^*\n]*(?:Hotel|Resort|Villa|Homestay|Khách sạn|Hội An|Hà Nội|Quy Nhơn))[^*\n]{3,90})\*\*",
    )
    for pattern in patterns:
        match = re.search(pattern, answer, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = _clean_hotel_name(match.group(1))
        if candidate:
            return candidate
    return None


def _clean_hotel_name(name: str) -> str:
    name = re.sub(r"\s+", " ", str(name or "")).strip(" :-–—*`")
    name = re.sub(r"^(khách sạn|hotel)\s+", "", name, flags=re.IGNORECASE).strip()
    if len(name) < 3:
        return ""
    if _normalize_text_for_matching(name) in {"tai ha noi", "tai hoi an", "tai quy nhon"}:
        return ""
    return name[:80]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalize_text_for_matching(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_clarification(answer: str) -> bool:
    text = answer.casefold()
    if "?" not in text:
        return False
    markers = (
        "mấy người",
        "bao nhiêu",
        "ngân sách",
        "ngày",
        "đêm",
        "điểm đến",
        "thành phố",
        "khi nào",
        "check-in",
        "check out",
        "check-out",
    )
    return any(marker in text for marker in markers)


def _looks_like_date_clarification(answer: str) -> bool:
    text = answer.casefold()
    if "?" not in text:
        return False
    markers = (
        "nhận/trả phòng",
        "nhận trả phòng",
        "nhận phòng",
        "trả phòng",
        "ngày nhận",
        "ngày trả",
        "ngày nào",
        "khi nào",
        "check-in",
        "check in",
        "check-out",
        "check out",
    )
    return any(marker in text for marker in markers)


def _looks_like_budget_clarification(answer: str) -> bool:
    text = answer.casefold()
    if "?" not in text:
        return False
    markers = (
        "ngân sách",
        "mức giá",
        "khoảng giá",
        "giá phòng",
        "giá khoảng",
        "chi phí",
        "budget",
    )
    return any(marker in text for marker in markers)


def _budget_suggestions_for_clarification(
    *,
    user_profile: dict[str, Any],
    llm_answer: str,
) -> list[str] | None:
    if not _looks_like_budget_clarification(llm_answer):
        return None
    budget_level = _extract_budget_level(user_profile)
    return list(_BUDGET_SUGGESTIONS_BY_LEVEL.get(budget_level or "", _DEFAULT_BUDGET_SUGGESTIONS))


def _extract_budget_level(profile: dict[str, Any] | None) -> str | None:
    if not isinstance(profile, dict):
        return None
    long_term = profile.get("long_term_profile")
    long_term = long_term if isinstance(long_term, dict) else {}

    direct_candidates = (
        profile.get("long_term_burget_level"),
        profile.get("long_term_budget_level"),
        profile.get("budget_level"),
        long_term.get("long_term_burget_level"),
        long_term.get("long_term_budget_level"),
        long_term.get("budget_level"),
    )
    for candidate in direct_candidates:
        level = _normalize_budget_level(candidate)
        if level:
            return level

    scored_candidates = (
        profile.get("long_term_burget_levels"),
        profile.get("long_term_budget_levels"),
        long_term.get("long_term_burget_levels"),
        long_term.get("long_term_budget_levels"),
    )
    for candidate in scored_candidates:
        level = _dominant_budget_level(candidate)
        if level:
            return level
    return None


def _dominant_budget_level(value: Any) -> str | None:
    if isinstance(value, str):
        return _normalize_budget_level(value)
    if isinstance(value, list):
        for item in value:
            level = _normalize_budget_level(item)
            if level:
                return level
        return None
    if not isinstance(value, dict):
        return None

    best_level: str | None = None
    best_score = 0.0
    for key, raw_score in value.items():
        level = _normalize_budget_level(key)
        if not level:
            level = _normalize_budget_level(raw_score)
        if not level:
            continue
        score = _budget_level_score(raw_score)
        if score > best_score:
            best_level = level
            best_score = score
    return best_level


def _budget_level_score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("count", "score", "weight", "value"):
            raw = value.get(key)
            if isinstance(raw, (int, float)):
                return float(raw)
        return 1.0 if _has_value(value) else 0.0
    return 1.0 if value not in (None, "", [], {}) else 0.0


def _normalize_budget_level(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("level", "name", "value", "label"):
            level = _normalize_budget_level(value.get(key))
            if level:
                return level
        return None
    text = str(value or "").casefold().strip()
    text = text.replace("-", "_").replace(" ", "_")
    if not text or text in {"none", "null"}:
        return None
    if text in {"low", "budget", "cheap", "economy", "thap", "thấp", "gia_re", "giá_rẻ"}:
        return "low"
    if text in {"medium", "mid", "mid_range", "moderate", "trung_binh", "trung_bình", "vua"}:
        return "medium"
    if text in {"high", "premium", "luxury", "expensive", "cao", "sang_trong", "sang_trọng"}:
        return "high"
    return None


def _profile_has_meaningful_context(profile: dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict):
        return False
    long_term = profile.get("long_term_profile")
    if isinstance(long_term, dict) and any(_has_value(value) for value in long_term.values()):
        return True
    return False


def _has_value(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    return True


def _fallback_for_type(suggestion_type: SuggestionType) -> list[str]:
    if suggestion_type == "init":
        return list(_INIT_FALLBACKS)
    if suggestion_type == "missing_info":
        return list(_MISSING_INFO_FALLBACKS)
    return list(_RELATED_INFO_FALLBACKS)


def _fallback_for_related_recommendations(related_info: list[dict[str, Any]]) -> list[str]:
    if not related_info:
        return []
    all_tags = {
        _fact_value(tag).casefold()
        for row in related_info
        for tag in (row.get("tags") or [])
        if _fact_value(tag)
    }
    all_nearby = {
        _fact_value(place).casefold()
        for row in related_info
        for place in (row.get("nearby") or [])
        if _fact_value(place)
    }
    all_suitable = {
        _fact_value(item).casefold()
        for row in related_info
        for item in (row.get("suitable_for") or [])
        if _fact_value(item)
    }

    suggestions = ["Giá phòng khoảng bao nhiêu?"]
    if any("biển" in tag or "beach" in tag for tag in all_tags | all_nearby):
        suggestions.append("Khách sạn gần biển đến đâu?")
    if any("hồ bơi" in tag or "bể bơi" in tag or "pool" in tag for tag in all_tags):
        suggestions.append("Hồ bơi có phù hợp trẻ em không?")
    if any("gia đình" in item or "trẻ" in item or "family" in item for item in all_suitable | all_tags):
        suggestions.append("Có phù hợp gia đình không?")
    if any("trung tâm" in tag or "center" in tag for tag in all_tags | all_nearby):
        suggestions.append("Di chuyển vào trung tâm thế nào?")
    if len(suggestions) < SUGGESTION_COUNT:
        suggestions.extend(_RELATED_INFO_FALLBACKS)
    return suggestions


def _top_hotel_ids(ranked_recommendations: list[dict[str, Any]], limit: int) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for item in ranked_recommendations:
        raw_id = item.get("hotel_id") or item.get("item_id") or item.get("id")
        try:
            hotel_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if hotel_id in seen:
            continue
        ids.append(hotel_id)
        seen.add(hotel_id)
        if len(ids) >= limit:
            break
    return ids


def _compact_graph_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": row.get("hotel_id"),
        "hotel_name": row.get("hotel_name"),
        "city": row.get("city"),
        "tags": _compact_fact_list(row.get("tags") or []),
        "nearby": _compact_fact_list(row.get("nearby") or []),
    }


def _compact_fact_list(items: list[Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not value:
            continue
        compacted.append({key: value for key, value in item.items() if value not in (None, "")})
    return compacted


def _summarize_profile(profile: dict[str, Any]) -> str:
    long_term = profile.get("long_term_profile") if isinstance(profile, dict) else {}
    if not isinstance(long_term, dict) or not long_term:
        return "(empty)"
    parts: list[str] = []
    for key, value in long_term.items():
        if not _has_value(value):
            continue
        parts.append(f"- {key}: {_short_repr(value)}")
        if len(parts) >= 8:
            break
    return "\n".join(parts) if parts else "(empty)"


def _summarize_hotels(hotels: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for hotel in hotels[:5]:
        meta = hotel.get("metadata") if isinstance(hotel.get("metadata"), dict) else {}
        source = {**meta, **hotel}
        tags = _join_values(_pick_list(source, "amenities", "tags", "location_tags", "room_views")[:8])
        nearby = _join_values(_pick_list(source, "nearby_places")[:4])
        suitable = _join_values(_pick_list(source, "suitable_for")[:4])
        price = _format_price(source.get("price_min") or source.get("min_price"), source.get("price_max"), source.get("currency"))
        lines.append(
            "- "
            + " | ".join(
                part
                for part in (
                    f"ID={source.get('hotel_id') or source.get('item_id')}",
                    f"name={source.get('hotel_name') or source.get('name')}",
                    f"rank={source.get('rank')}",
                    f"score={source.get('score')}",
                    f"city={source.get('city') or source.get('destination')}",
                    f"area={source.get('area')}",
                    f"type={source.get('property_type') or source.get('accommodation_type') or source.get('hotel_type')}",
                    f"price={price}" if price else "",
                    f"tags={tags}" if tags else "",
                    f"nearby={nearby}" if nearby else "",
                    f"suitable_for={suitable}" if suitable else "",
                    f"reasons={_short_repr(source.get('reasons') or [])}",
                )
                if part and not part.endswith("=None")
            )
        )
    return "\n".join(lines) if lines else "(empty)"


def _summarize_graph_info(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows[:5]:
        tags = _join_fact_values((row.get("tags") or [])[:6])
        nearby = _join_fact_values((row.get("nearby") or [])[:4])
        suitable = _join_fact_values((row.get("suitable_for") or [])[:4])
        price = _format_price(row.get("price_min"), row.get("price_max"), row.get("currency"))
        lines.append(
            "- "
            + " | ".join(
                part
                for part in (
                    f"hotel={row.get('hotel_name') or row.get('hotel_id')}",
                    f"rank={row.get('rank')}",
                    f"city={row.get('city')}",
                    f"area={row.get('area')}",
                    f"type={row.get('property_type')}",
                    f"price={price}" if price else "",
                    f"tags={tags}" if tags else "",
                    f"nearby={nearby}" if nearby else "",
                    f"suitable_for={suitable}" if suitable else "",
                )
                if part and not part.endswith("=None")
            )
        )
    return "\n".join(lines) if lines else "(empty)"


def _pick_list(source: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in keys:
        raw = source.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            candidates = [raw]
        elif isinstance(raw, dict):
            candidates = [str(k) for k, value in raw.items() if value]
        elif isinstance(raw, list):
            candidates = raw
        else:
            candidates = [raw]
        for candidate in candidates:
            value = _fact_value(candidate)
            if not value:
                continue
            folded = value.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            values.append(value)
    return values


def _join_values(values: list[str]) -> str:
    return ", ".join(values)


def _join_fact_values(items: list[Any]) -> str:
    return ", ".join(value for value in (_fact_value(item) for item in items) if value)


def _fact_value(item: Any) -> str:
    if isinstance(item, dict):
        value = item.get("value") or item.get("name") or item.get("tag") or item.get("title")
        return str(value).strip() if value else ""
    value = str(item).strip()
    return value if value and value.lower() not in {"none", "null"} else ""


def _format_price(price_min: Any, price_max: Any, currency: Any = None) -> str:
    if price_min in (None, "") and price_max in (None, ""):
        return ""
    unit = str(currency or "VND")
    try:
        min_text = f"{int(float(price_min)):,}" if price_min not in (None, "") else ""
        max_text = f"{int(float(price_max)):,}" if price_max not in (None, "") else ""
    except (TypeError, ValueError):
        min_text = str(price_min or "")
        max_text = str(price_max or "")
    if min_text and max_text:
        return f"{min_text}-{max_text} {unit}"
    return f"{min_text or max_text} {unit}".strip()


def _short_repr(value: Any, max_chars: int = 160) -> str:
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip(" ,.;:-") + "..."
    return text
