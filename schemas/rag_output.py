"""Standardized output schema for the RAG Layer.

This module defines only the RAG Layer output contract and helper builders.
It does not implement retrieval, ranking, recommendation, or response generation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QueryType = Literal[
    "hotel_detail",
    "policy_detail",
    "activities_detail",
    "hotel_search",
    "activity_search",
    "hotel_compare",
    "unknown",
]
AnswerMode = Literal["detail", "list", "compare", "fallback"]


class RetrievalMetadata(BaseModel):
    """Metadata attached to every standardized RAG Layer output."""

    sources_used: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    total_found: int = 0
    retrieval_time_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


class HotelEntity(BaseModel):
    """Hotel entity with optional factual data sections."""

    hotel_id: int
    hotel_name: str
    data: dict[str, Any] = Field(default_factory=dict)


class HotelSearchResult(BaseModel):
    """Single hotel result for list-style retrieval outputs."""

    hotel_id: int
    hotel_name: str
    rank: int
    score: float
    matched_tags: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class ActivityResult(BaseModel):
    """Single activity result for activity retrieval outputs."""

    activity_id: int
    title: str
    description: str = ""
    related_hotel_ids: list[int] = Field(default_factory=list)
    score: float = 0.0


class ComparisonResult(BaseModel):
    """Comparison payload returned by the RAG Layer."""

    fields: list[str] = Field(default_factory=list)


class RAGOutput(BaseModel):
    """Top-level standardized output contract for the RAG Layer."""

    query: str = ""
    query_type: QueryType
    answer_mode: AnswerMode
    entities: list[HotelEntity] = Field(default_factory=list)
    results: list[HotelSearchResult] = Field(default_factory=list)
    activities: list[ActivityResult] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    metadata: RetrievalMetadata = Field(default_factory=RetrievalMetadata)


def _build_metadata(
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
    *,
    sources_used: list[str] | None = None,
    confidence: float | None = None,
    total_found: int | None = None,
    retrieval_time_ms: int | None = None,
    warnings: list[str] | None = None,
) -> RetrievalMetadata:
    """Create RetrievalMetadata while allowing helper-level overrides."""

    if isinstance(metadata, RetrievalMetadata):
        data = metadata.model_dump()
    else:
        data = dict(metadata or {})

    if sources_used is not None:
        data["sources_used"] = sources_used
    if confidence is not None:
        data["confidence"] = confidence
    if total_found is not None:
        data["total_found"] = total_found
    if retrieval_time_ms is not None:
        data["retrieval_time_ms"] = retrieval_time_ms
    if warnings is not None:
        data["warnings"] = warnings

    return RetrievalMetadata(**data)


def _coerce_hotel_entity(entity: HotelEntity | dict[str, Any]) -> HotelEntity:
    """Convert a dict or HotelEntity into HotelEntity."""

    return entity if isinstance(entity, HotelEntity) else HotelEntity(**entity)


def _coerce_hotel_result(
    result: HotelSearchResult | dict[str, Any],
) -> HotelSearchResult:
    """Convert a dict or HotelSearchResult into HotelSearchResult."""

    return result if isinstance(result, HotelSearchResult) else HotelSearchResult(**result)


def _coerce_activity_result(
    activity: ActivityResult | dict[str, Any],
) -> ActivityResult:
    """Convert a dict or ActivityResult into ActivityResult."""

    return activity if isinstance(activity, ActivityResult) else ActivityResult(**activity)


def build_hotel_detail(
    query: str,
    hotel_id: int,
    hotel_name: str,
    *,
    overview: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    activities: list[dict[str, Any]] | None = None,
    amenities: list[Any] | None = None,
    location: dict[str, Any] | None = None,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build a hotel_detail RAG output."""

    entity = HotelEntity(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        data={
            "overview": overview or {},
            "policy": policy or {},
            "activities": activities or [],
            "amenities": amenities or [],
            "location": location or {},
        },
    )
    return RAGOutput(
        query=query,
        query_type="hotel_detail",
        answer_mode="detail",
        entities=[entity],
        metadata=_build_metadata(metadata, total_found=1),
    )


def build_policy_detail(
    query: str,
    hotel_id: int,
    hotel_name: str,
    *,
    policy: dict[str, Any] | None = None,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build a policy_detail RAG output."""

    entity = HotelEntity(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        data={
            "policy": policy
            or {
                "check_in": "",
                "check_out": "",
                "child_policy": "",
                "pet_policy": "",
            }
        },
    )
    return RAGOutput(
        query=query,
        query_type="policy_detail",
        answer_mode="detail",
        entities=[entity],
        metadata=_build_metadata(metadata, total_found=1),
    )


def build_activities_detail(
    query: str,
    hotel_id: int,
    hotel_name: str,
    *,
    activities: dict[str, Any] | list[dict[str, Any]] | None = None,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build an activities_detail RAG output."""

    entity = HotelEntity(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        data={
            "activities": activities
            or {
                "name_activity": "",
                "description": "",
            }
        },
    )
    return RAGOutput(
        query=query,
        query_type="activities_detail",
        answer_mode="detail",
        entities=[entity],
        metadata=_build_metadata(metadata, total_found=1),
    )


def build_hotel_search(
    query: str,
    results: list[HotelSearchResult | dict[str, Any]],
    *,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build a hotel_search RAG output."""

    hotel_results = [_coerce_hotel_result(result) for result in results]
    return RAGOutput(
        query=query,
        query_type="hotel_search",
        answer_mode="list",
        results=hotel_results,
        metadata=_build_metadata(metadata, total_found=len(hotel_results)),
    )


def build_activity_search(
    query: str,
    activities: list[ActivityResult | dict[str, Any]],
    *,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build an activity_search RAG output."""

    activity_results = [_coerce_activity_result(activity) for activity in activities]
    return RAGOutput(
        query=query,
        query_type="activity_search",
        answer_mode="list",
        activities=activity_results,
        metadata=_build_metadata(metadata, total_found=len(activity_results)),
    )


def build_hotel_compare(
    query: str,
    entities: list[HotelEntity | dict[str, Any]],
    *,
    fields: list[str] | None = None,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build a hotel_compare RAG output."""

    hotel_entities = [_coerce_hotel_entity(entity) for entity in entities]
    return RAGOutput(
        query=query,
        query_type="hotel_compare",
        answer_mode="compare",
        entities=hotel_entities,
        comparison=ComparisonResult(fields=fields or ["overview", "policy", "activities"]),
        metadata=_build_metadata(metadata, total_found=len(hotel_entities)),
    )


def build_unknown(
    query: str,
    *,
    warnings: list[str] | None = None,
    metadata: RetrievalMetadata | dict[str, Any] | None = None,
) -> RAGOutput:
    """Build an unknown/fallback RAG output."""

    fallback_warnings = warnings or ["Unable to determine intent"]
    return RAGOutput(
        query=query,
        query_type="unknown",
        answer_mode="fallback",
        metadata=_build_metadata(
            metadata,
            confidence=0.0,
            total_found=0,
            warnings=fallback_warnings,
        ),
    )


RAG_OUTPUT_EXAMPLES: dict[str, RAGOutput] = {
    "hotel_detail": build_hotel_detail(
        "Cho tôi thông tin chi tiết khách sạn Mường Thanh",
        hotel_id=149036,
        hotel_name="Mường Thanh Luxury Đà Nẵng",
        overview={},
        policy={},
        activities=[],
        amenities=[],
        location={},
    ),
    "policy_detail": build_policy_detail(
        "Check-in mấy giờ?",
        hotel_id=149036,
        hotel_name="Mường Thanh Luxury Đà Nẵng",
        policy={
            "check_in": "",
            "check_out": "",
            "child_policy": "",
            "pet_policy": "",
        },
    ),
    "activities_detail": build_activities_detail(
        "Khách sạn A có những hoạt động gì?",
        hotel_id=149036,
        hotel_name="Mường Thanh Luxury Đà Nẵng",
        activities={
            "name_activity": "",
            "description": "",
        },
    ),
    "hotel_search": build_hotel_search(
        "Khách sạn phù hợp gia đình",
        [
            {
                "hotel_id": 149036,
                "hotel_name": "InterContinental Danang",
                "rank": 1,
                "score": 0.91,
                "matched_tags": ["kids_family", "pool"],
                "highlights": ["Kids Club", "Family Room"],
            }
        ],
    ),
    "activity_search": build_activity_search(
        "Có gì chơi gần khách sạn?",
        [
            {
                "activity_id": 1,
                "title": "VinWonders",
                "description": "...",
                "related_hotel_ids": [149036],
                "score": 0.88,
            }
        ],
    ),
    "hotel_compare": build_hotel_compare(
        "So sánh khách sạn A và B",
        [
            {"hotel_id": 1, "hotel_name": "Hotel A"},
            {"hotel_id": 2, "hotel_name": "Hotel B"},
        ],
        fields=["overview", "policy", "activities"],
    ),
    "unknown": build_unknown(
        "Không xác định được yêu cầu",
        warnings=["Unable to determine intent"],
    ),
}
