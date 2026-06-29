from dataclasses import dataclass, field

from query_understanding.contracts import UserProfile
from query_understanding.planner.schema import SearchIntent
from query_understanding.router.schema import ExecutionStep


@dataclass(slots=True)
class WorkflowResponse:
    current_profile: UserProfile
    intents: list[SearchIntent] = field(default_factory=list)
    rag_plan: list[ExecutionStep] = field(default_factory=list)
    recommendation_plan: list[ExecutionStep] = field(default_factory=list)


class Phase1Workflow:
    def run(self) -> WorkflowResponse:
        raise NotImplementedError("Phase1Workflow is a Phase 1 orchestration stub.")
