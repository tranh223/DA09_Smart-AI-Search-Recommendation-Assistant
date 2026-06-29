from dataclasses import dataclass, field

from query_understanding.contracts import UserProfile
from query_understanding.enums import SearchTask


@dataclass(slots=True)
class SearchPlanCheckRequest:
    query: str
    current_profile: UserProfile


@dataclass(slots=True)
class SearchPlanCheckResponse:
    can_build_plan: bool
    reason: str
    missing_information: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchIntent:
    intent_type: SearchTask
    confidence: float
    rationale: str


@dataclass(slots=True)
class SearchPlannerRequest:
    query: str
    current_profile: UserProfile


@dataclass(slots=True)
class SearchPlannerResponse:
    intents: list[SearchIntent] = field(default_factory=list)
