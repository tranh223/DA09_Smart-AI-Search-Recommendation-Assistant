from dataclasses import dataclass, field
from typing import Any

from query_understanding.enums import GraphOperation


@dataclass(slots=True)
class RagSearchRequest:
    query: str
    top_k: int = 10


@dataclass(slots=True)
class RagSearchResponse:
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class HotelEmbeddingSearchRequest:
    destination: str | None = None
    tags: list[str] = field(default_factory=list)
    top_k: int = 20


@dataclass(slots=True)
class HotelEmbeddingSearchResponse:
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class UnifiedGraphSearchRequest:
    graph_operation: GraphOperation
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UnifiedGraphSearchResponse:
    items: list[dict[str, Any]] = field(default_factory=list)
