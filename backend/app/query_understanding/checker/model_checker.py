from dataclasses import dataclass, field
from datetime import date

from query_understanding.llm import OpenAIResponsesClient
from query_understanding.models.planner import CountInteractionValue
from query_understanding.models.planner import SessionContext, UserProfile

RECOMMENDATION_CHECK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["requires_recommendation"],
    "properties": {
        "requires_recommendation": {
            "type": "boolean",
        }
    },
}

RECOMMENDATION_CHECK_INSTRUCTIONS = """
Decide whether a hotel travel query needs recommendation flow or only RAG flow.

Return requires_recommendation = true when the answer needs recommendation/search/ranking behavior,
including hotel search, hotel suggestion, trending hotels, or personalization.

Return requires_recommendation = false when the answer is only factual knowledge lookup,
including policy, special feature explanation, or hotel similar information that does not require
recommendation context checks.
""".strip()


@dataclass(slots=True)
class ProfileCheckResult:
    is_complete: bool
    missing_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlanReadinessResult:
    can_build_plan: bool
    requires_recommendation: bool
    is_enough_recommend: bool
    missing_fields: list[str] = field(default_factory=list)


class ModelChecker:
    def __init__(
        self,
        recommendation_client: OpenAIResponsesClient | None = None,
        recommendation_model: str = "gpt-4o-mini",
    ) -> None:
        self.recommendation_client = recommendation_client or OpenAIResponsesClient()
        self.recommendation_model = recommendation_model

    def check_current_profile(self, current_profile: UserProfile) -> ProfileCheckResult:
        return ProfileCheckResult(
            is_complete=True,
            missing_fields=[],
        )

    def check_plan_readiness(
        self,
        query: str,
        current_profile: UserProfile,
        requires_recommendation: bool | None = None,
    ) -> PlanReadinessResult:
        session = current_profile.session_context
        if session.is_enough_recommend is True:
            return PlanReadinessResult(
                can_build_plan=True,
                requires_recommendation=True,
                is_enough_recommend=True,
            )

        if requires_recommendation is None:
            requires_recommendation = self._requires_recommendation(
                query=query,
                user_id=current_profile.user_id,
            )

        if not requires_recommendation:
            return PlanReadinessResult(
                can_build_plan=True,
                requires_recommendation=False,
                is_enough_recommend=bool(session.is_enough_recommend),
            )

        missing_fields: list[str] = []
        if not session.destination:
            missing_fields.append("destination")
        if not session.check_in:
            missing_fields.append("check_in")
        if not session.check_out:
            missing_fields.append("check_out")
        if not self._has_budget_context(session):
            missing_fields.append("budget_level")

        is_enough_recommend = not missing_fields
        session.is_enough_recommend = is_enough_recommend
        return PlanReadinessResult(
            can_build_plan=is_enough_recommend,
            requires_recommendation=True,
            is_enough_recommend=is_enough_recommend,
            missing_fields=missing_fields,
        )

    def _requires_recommendation(self, query: str, user_id: str | None) -> bool:
        payload = self.recommendation_client.create_structured_output(
            model=self.recommendation_model,
            instructions=RECOMMENDATION_CHECK_INSTRUCTIONS,
            input_text=query,
            schema_name="recommendation_check",
            schema=RECOMMENDATION_CHECK_SCHEMA,
            safety_identifier=user_id,
        )
        return bool(payload["requires_recommendation"])

    @staticmethod
    def _top_count_key(values: dict[str, object]) -> str | None:
        if not values:
            return None
        valid_items: list[tuple[str, int]] = []
        for key, value in values.items():
            count, last_interaction = ModelChecker._extract_count_interaction(value)
            if count is None or last_interaction is None:
                continue
            valid_items.append((key, count))
        if not valid_items:
            return None
        return max(valid_items, key=lambda item: item[1])[0]

    @staticmethod
    def _has_budget_context(session: SessionContext) -> bool:
        if ModelChecker._top_count_key(session.session_budget_levels):
            return True
        return session.session_price_range.min is not None or session.session_price_range.max is not None

    @staticmethod
    def _extract_count_interaction(value: object) -> tuple[int | None, str | None]:
        if isinstance(value, CountInteractionValue):
            return value.count, value.last_interaction
        if isinstance(value, dict):
            count = value.get("count")
            last_interaction = value.get("last_interaction")
            if count is not None and last_interaction is not None:
                return int(count), str(last_interaction)
        return None, None
