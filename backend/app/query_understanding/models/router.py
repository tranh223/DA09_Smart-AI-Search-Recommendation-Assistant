from dataclasses import dataclass, field
from typing import Any

from query_understanding.enums import GraphOperation, SearchSource, SearchTask


@dataclass(slots=True)
class ToolCall:
    tool: str
    graph_operation: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RagExecutionStep:
    step: int
    intent_type: SearchTask | str
    source: SearchSource | str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionStep:
    step: int
    intent_type: SearchTask | str
    source: SearchSource | str
    parameters: dict[str, Any] = field(default_factory=dict)
    graph_operation: GraphOperation | str | None = None
    input_from: str | None = None
    depends_on: list[int] = field(default_factory=list)


@dataclass(slots=True)
class RouterResult:
    execution_mode: str = "parallel"
    rag_plan: list[RagExecutionStep] = field(default_factory=list)
    recommendation_plan: list[ExecutionStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
