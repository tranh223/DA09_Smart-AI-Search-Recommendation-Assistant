from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from query_understanding.contracts import UserProfile
from query_understanding.enums import GraphOperation, SearchSource, SearchTask
from query_understanding.planner.schema import SearchIntent


@dataclass(slots=True)
class ExecutionStep:
    step: int
    intent_type: SearchTask
    source: SearchSource
    parameters: dict[str, Any] = field(default_factory=dict)
    graph_operation: GraphOperation | None = None
    input_from: str | None = None
    depends_on: list[int] = field(default_factory=list)


@dataclass(slots=True)
class RouterRequest:
    query: str
    current_profile: UserProfile
    intents: list[SearchIntent] = field(default_factory=list)


@dataclass(slots=True)
class RouterResponse:
    rag_plan: list[ExecutionStep] = field(default_factory=list)
    recommendation_plan: list[ExecutionStep] = field(default_factory=list)
