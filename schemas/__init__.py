"""Schema models used across the DA09 RAG system."""

from schemas.rag_output import (
    RAG_OUTPUT_EXAMPLES,
    ActivityResult,
    ComparisonResult,
    HotelEntity,
    HotelSearchResult,
    RAGOutput,
    RetrievalMetadata,
    build_activities_detail,
    build_activity_search,
    build_hotel_compare,
    build_hotel_detail,
    build_hotel_search,
    build_policy_detail,
    build_unknown,
)

__all__ = [
    "ActivityResult",
    "ComparisonResult",
    "HotelEntity",
    "HotelSearchResult",
    "RAGOutput",
    "RAG_OUTPUT_EXAMPLES",
    "RetrievalMetadata",
    "build_activities_detail",
    "build_activity_search",
    "build_hotel_compare",
    "build_hotel_detail",
    "build_hotel_search",
    "build_policy_detail",
    "build_unknown",
]
