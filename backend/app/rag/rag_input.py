"""Structured input contract and deterministic routing for the RAG pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


IntentType = Literal[
    "HOTEL_FEATURE_QA",
    "HOTEL_POLICY_QA",
    "HOTEL_COMPARISON_QA",
]


class RAGFeatures(BaseModel):
    """Structured features extracted from user input."""

    model_config = ConfigDict(str_strip_whitespace=True)

    hotel_name: str | None = None
    destination: str | None = None
    amenities: list[str] = Field(default_factory=list)
    expectations: list[str] = Field(default_factory=list)


class RAGParameters(BaseModel):
    """Parameters for RAG request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1)
    features: RAGFeatures = Field(default_factory=RAGFeatures)


class RAGRequest(BaseModel):
    """Structured RAG request contract."""

    model_config = ConfigDict(str_strip_whitespace=True)

    intent_type: IntentType
    source: Literal["RAG_SERVICE"] = "RAG_SERVICE"
    parameters: RAGParameters


INTENT_ROUTES: dict[IntentType, dict[str, Any]] = {
    "HOTEL_FEATURE_QA": {
        "needs_rag": True,
        "needs_graph": False,
        "rag_sections": ["description", "overview", "semantic_profile", "faq"],
    },
    "HOTEL_POLICY_QA": {
        "needs_rag": True,
        "needs_graph": False,
        "rag_sections": ["faq", "description", "semantic_profile"],
    },
    "HOTEL_COMPARISON_QA": {
        "needs_rag": True,
        "needs_graph": True,
        "rag_sections": ["description", "overview", "semantic_profile", "faq"],
    },
}


def parse_rag_request(payload: RAGRequest | dict[str, Any]) -> RAGRequest:
    if isinstance(payload, RAGRequest):
        return payload
    return RAGRequest.model_validate(payload)


def build_retrieval_query(request: RAGRequest) -> str:
    """Enrich the natural query with already-extracted structured features."""

    features = request.parameters.features
    parts = [request.parameters.query]
    if features.hotel_name:
        parts.append(f"Hotel: {features.hotel_name}")
    if features.destination:
        parts.append(f"Destination: {features.destination}")
    if features.amenities:
        parts.append(f"Amenities: {', '.join(features.amenities)}")
    if features.expectations:
        parts.append(f"Expectations: {', '.join(features.expectations)}")
    return "\n".join(parts)


def build_structured_plan(request: RAGRequest) -> dict[str, Any]:
    """Build a deterministic plan without spending an LLM call."""

    features = request.parameters.features
    route = INTENT_ROUTES[request.intent_type]
    known_features = [
        value
        for value in [
            features.hotel_name,
            features.destination,
            *features.amenities,
            *features.expectations,
        ]
        if value
    ]
    return {
        "query_type": request.intent_type,
        "main_object": features.hotel_name or features.destination or "hotel",
        "sub_objects": [*features.amenities, *features.expectations],
        "hotel_name": features.hotel_name,
        "destination": features.destination,
        "needs_rag": route["needs_rag"],
        "needs_graph": route["needs_graph"],
        "rag_sections": list(route["rag_sections"]),
        "tool_inputs": {
            "rag": {
                "query": build_retrieval_query(request),
                "top_k": 3,
                "hotel_ids": [],
                "sections": list(route["rag_sections"]),
            }
        },
        "required_steps": [
            "Retrieve evidence using the provided intent and features",
            "Cross-check evidence from selected sources",
            "Answer the original query",
        ],
        "context": f"Structured input supplied known fields: {known_features}",
    }
