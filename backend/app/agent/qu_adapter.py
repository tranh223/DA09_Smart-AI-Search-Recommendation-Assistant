"""
Adapter: QueryUnderstandingPipeline output → Agent state fields.

Trách nhiệm duy nhất của module này là type-mapping:
  QU dataclasses (CountInteractionValue, ActiveProfile, SessionContext...)
    → Pydantic models của recommendation (InteractionScore, Profile, SessionContext...)
    → partial AgentState dict để intent_node trả về

Không chứa business logic — chỉ coerce kiểu dữ liệu và trích xuất field.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.query_understanding.enums import SearchTask
from app.query_understanding.pipeline import PipelineResult, PipelineTrace

from app.recommendation.models import (
    InteractionScore,
    NegativePreferences,
    Profile,
    PriceRange,
    RecommendInput,
    SessionContext,
)


# ── ScoreMap helpers ─────────────────────────────────────────────────────────
# asdict() trên ActiveProfile biến mọi nested dataclass thành dict,
# nên các hàm dưới luôn nhận dict[str, dict].

def _to_interaction(score_map: dict[str, Any]) -> dict[str, InteractionScore]:
    """ScoreMap {tag: {"count", "last_interaction"}} → dict[str, InteractionScore]."""
    result: dict[str, InteractionScore] = {}
    for key, val in (score_map or {}).items():
        if isinstance(val, dict):
            result[str(key)] = InteractionScore(
                count=int(val.get("count", 1)),
                last_interaction=val.get("last_interaction"),
            )
    return result


def _neg_to_float(score_map: dict[str, Any]) -> dict[str, float]:
    """NegativeScoreMap → dict[str, float].

    recommendation.NegativePreferences dùng float; QU dùng count-based.
    Quy ước: count / 10, capped 1.0  (count=10 → max signal).
    """
    result: dict[str, float] = {}
    for key, val in (score_map or {}).items():
        count = int(val.get("count", 1)) if isinstance(val, dict) else 1
        result[str(key)] = min(count / 10.0, 1.0)
    return result


# ── ActiveProfile → Profile ──────────────────────────────────────────────────

def _to_profile(active_profile: Any) -> Profile:
    """QU ActiveProfile dataclass → recommendation Profile Pydantic model."""
    ap: dict[str, Any] = asdict(active_profile)
    price = ap.get("long_term_price_range") or {}
    neg = ap.get("long_term_negative_preferences") or {}
    clicks = ap.get("recommendation_clicks") or {}

    return Profile(
        nationality=ap.get("nationality"),
        age_group=ap.get("age_group"),
        current_workplace=ap.get("current_workplace"),
        is_enough=bool(ap.get("is_enough") or False),
        long_term_preference_habits=_to_interaction(ap.get("long_term_preference_habits", {})),
        long_term_trip_types=_to_interaction(ap.get("long_term_trip_types", {})),
        long_term_budget_levels=_to_interaction(ap.get("long_term_budget_levels", {})),
        long_term_price_range=PriceRange(
            min=price.get("min"),
            max=price.get("max"),
            currency=price.get("currency") or "VND",
        ),
        long_term_hotel_types=_to_interaction(ap.get("long_term_hotel_types", {})),
        long_term_room_views=_to_interaction(ap.get("long_term_room_views", {})),
        long_term_amenities=_to_interaction(ap.get("long_term_amenities", {})),
        long_term_negative_preferences=NegativePreferences(
            avoid_hotel_types=_neg_to_float(neg.get("avoid_hotel_types", {})),
            avoid_amenities=_neg_to_float(neg.get("avoid_amenities", {})),
            avoid_preference_habits=_neg_to_float(neg.get("avoid_preference_habits", {})),
            avoid_nearby_places=_neg_to_float(neg.get("avoid_nearby_places", {})),
            avoid_locations=_neg_to_float(neg.get("avoid_locations", {})),
        ),
        recommendation_clicks={"hotel": list(clicks.get("hotel") or [])},
    )


# ── QU SessionContext → recommendation SessionContext ────────────────────────

def _to_session_context(sc_dict: dict[str, Any]) -> SessionContext:
    """Serialised QU SessionContext dict → recommendation SessionContext Pydantic.

    Các trường session_* và runtime_tag_expansion được giữ qua Config.extra="allow"
    để profile_normalizer trong reranker có thể đọc khi cần.
    """
    price = sc_dict.get("session_price_range") or {}
    return SessionContext(
        destination=sc_dict.get("destination"),
        current_location=sc_dict.get("current_location"),
        nearby_place=sc_dict.get("nearby_place"),
        number_of_guests=sc_dict.get("number_of_guests"),
        has_pet=sc_dict.get("has_pet"),
        has_children=sc_dict.get("has_children"),
        check_in=sc_dict.get("check_in"),
        check_out=sc_dict.get("check_out"),
        session_price_range=PriceRange(
            min=price.get("min"),
            max=price.get("max"),
            currency=price.get("currency") or "VND",
        ),
        # Extra session fields preserved via Config.extra = "allow"
        note_amenities=sc_dict.get("note_amenities"),
        session_trip_types=sc_dict.get("session_trip_types", {}),
        session_budget_levels=sc_dict.get("session_budget_levels", {}),
        session_preference_habits=sc_dict.get("session_preference_habits", {}),
        session_hotel_types=sc_dict.get("session_hotel_types", {}),
        session_room_views=sc_dict.get("session_room_views", {}),
        session_amenities=sc_dict.get("session_amenities", {}),
        session_negative_preferences=sc_dict.get("session_negative_preferences", {}),
        runtime_tag_expansion=sc_dict.get("runtime_tag_expansion", {}),
    )


# ── Derive intent string ──────────────────────────────────────────────────────

# Ưu tiên: recommendation tasks trước (có impact cao hơn), RAG tasks sau.
_PRIORITY: list[SearchTask] = [
    SearchTask.PERSONALIZATION,
    SearchTask.HOTEL_SEARCH,
    SearchTask.HOTEL_SIMILAR,
    SearchTask.INFORMATION,
    SearchTask.SPECIAL_FEATURE,
]

_TASK_TO_INTENT: dict[str, str] = {
    SearchTask.PERSONALIZATION: "personalization",
    SearchTask.HOTEL_SEARCH: "hotel_search",
    SearchTask.HOTEL_SIMILAR: "hotel_similar",
    SearchTask.INFORMATION: "information",
    SearchTask.SPECIAL_FEATURE: "special_feature",
}


def _derive_intent(pipeline_result: PipelineResult) -> str:
    checker = pipeline_result.trace.checker or {}
    if checker.get("assistant_help"):
        return "assistant_help"
    if checker.get("assistant_capability"):
        return "assistant_capability"
    rr = pipeline_result.router_result
    if rr is None:
        return "clarification_needed"
    all_tasks = {
        str(step.intent_type)
        for step in list(rr.recommendation_plan) + list(rr.rag_plan)
    }
    for task in _PRIORITY:
        if task.value in all_tasks:
            return _TASK_TO_INTENT[task]
    return "hotel_search"


# ── Clarification helpers ─────────────────────────────────────────────────────

_FIELD_QUESTIONS: dict[str, str] = {
    "destination": "Anh/chị muốn đặt phòng tại thành phố hoặc điểm đến nào?",
    "check_in": "Anh/chị dự định nhận phòng vào ngày nào?",
    "check_out": "Anh/chị dự định trả phòng vào ngày nào?",
    "budget_level": "Mức ngân sách của anh/chị cho chuyến đi này là bao nhiêu?",
}

_GUARDRAIL_MESSAGES: dict[str, str] = {
    "OUT_OF_SCOPE": (
        "Mình chưa có dữ liệu hoặc chuyên môn để hỗ trợ nội dung này. "
        "Hiện tại VinBot hỗ trợ tìm kiếm, hỏi đáp và gợi ý khách sạn/lưu trú."
    ),
}

_ASSISTANT_CAPABILITY_MESSAGE = (
    "Mình có thể giúp bạn tìm kiếm và gợi ý khách sạn theo điểm đến, "
    "ngày nhận/trả phòng, ngân sách, số khách và các tiêu chí như view, "
    "tiện nghi, vị trí, loại chuyến đi hoặc mức độ phù hợp với bạn. "
    "Nếu bạn đã có kế hoạch, hãy cho mình biết điểm đến và thời gian đi."
)


def _build_clarification(trace: PipelineTrace) -> tuple[str, list[str]]:
    """Trả về (câu hỏi làm rõ, danh sách field còn thiếu) từ pipeline trace."""
    checker: dict[str, Any] = trace.checker
    if checker.get("assistant_help"):
        return "Mình sẽ kiểm tra lại ngữ cảnh cuộc trò chuyện để trả lời bạn.", []
    if checker.get("assistant_capability"):
        return _ASSISTANT_CAPABILITY_MESSAGE, []

    # Guardrail chặn — đọc trực tiếp từ PipelineTrace dataclass
    guardrail: dict[str, Any] = trace.guardrail
    if not guardrail.get("allow", True):
        category = guardrail.get("category", "")
        return _GUARDRAIL_MESSAGES.get(category, "Câu hỏi không hợp lệ."), []

    # Thiếu thông tin recommend
    plan_readiness: dict[str, Any] = checker.get("plan_readiness") or {}
    missing: list[str] = plan_readiness.get("missing_fields") or []
    if missing:
        question = _FIELD_QUESTIONS.get(
            missing[0],
            f"Vui lòng cung cấp thêm thông tin: {', '.join(missing)}.",
        )
        return question, missing

    return "Vui lòng cung cấp thêm thông tin để mình gợi ý chính xác hơn.", []


# ── Public entry point ────────────────────────────────────────────────────────

def pipeline_result_to_state(
    pipeline_result: PipelineResult,
    *,
    query: str,
    limit_per_source: int = 10,
) -> dict[str, Any]:
    """Chuyển đổi PipelineResult → partial AgentState dict.

    Trả về tất cả field mà intent_node cần write vào state, bao gồm
    recommend_input đã build sẵn để recommend_node dùng ngay mà không
    phải build lại từ slots thủ công.

    Args:
        pipeline_result: Output từ QueryUnderstandingPipeline.run().
        query: Câu hỏi gốc — dùng làm original_query cho RecommendInput.
        limit_per_source: Số candidate mỗi nguồn (default 10).

    Returns:
        Partial AgentState dict với các key:
        intent, slots, slot_is_complete, needs_clarification,
        clarification_question, clarification_missing_fields,
        recommend_input, qu_trace.
    """
    router_result = pipeline_result.router_result
    active_profile = pipeline_result.active_profile
    updated_profile = pipeline_result.updated_user_profile
    has_plan = router_result is not None

    # Pre-compute sc_dict once — dùng cho cả _extract_slots và _to_session_context
    sc_dict: dict[str, Any] = asdict(updated_profile.session_context)
    price = sc_dict.get("session_price_range") or {}

    slots: dict[str, Any] = {
        "destination": sc_dict.get("destination"),
        "check_in": sc_dict.get("check_in"),
        "check_out": sc_dict.get("check_out"),
        "number_of_guests": sc_dict.get("number_of_guests"),
        "has_pet": sc_dict.get("has_pet"),
        "has_children": sc_dict.get("has_children"),
        "nearby_place": sc_dict.get("nearby_place"),
        "budget_min": price.get("min"),
        "budget_max": price.get("max"),
        "currency": price.get("currency") or "VND",
    }

    recommend_input: RecommendInput | None = None
    if has_plan and active_profile is not None:
        recommend_input = RecommendInput(
            user_id=updated_profile.user_id,
            profile=_to_profile(active_profile),
            session_context=_to_session_context(sc_dict),
            original_query=query,
            limit_per_source=limit_per_source,
        )

    clarification_question = ""
    missing_fields: list[str] = []
    if not has_plan:
        clarification_question, missing_fields = _build_clarification(pipeline_result.trace)

    return {
        "intent": _derive_intent(pipeline_result),
        "user_profile": asdict(updated_profile),
        "updated_user_profile": asdict(updated_profile),
        "slots": slots,
        "slot_is_complete": has_plan,
        "needs_clarification": not has_plan,
        "clarification_question": clarification_question,
        "clarification_missing_fields": missing_fields,
        "recommend_input": recommend_input,
        "qu_trace": asdict(pipeline_result.trace),
    }
