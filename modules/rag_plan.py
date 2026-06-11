"""Planning contract for multi-source RAG retrieval.

This module only builds a structured plan for downstream retrieval layers.
It does not execute SQL, vector search, graph search, ranking, or generation.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.rag_output import AnswerMode, QueryType


ImplementationStatus = Literal["ready", "planned", "disabled"]
SourceName = Literal[
    "hotel_sql",
    "vector_search",
    "graph_search",
    "user_profile",
    "short_term_memory",
    "fusion",
]


class PlanEntities(BaseModel):
    """Entities extracted or supplied for the query plan."""

    hotel_name: str | None = None
    hotel_ids: list[int] = Field(default_factory=list)
    destination: str | None = None
    activity_name: str | None = None
    amenities: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)


class PlanFilters(BaseModel):
    """Structured filters that retrieval tools may use."""

    amenities: list[str] = Field(default_factory=list)
    suitable_for: list[str] = Field(default_factory=list)
    expectations: list[str] = Field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    star_rating_min: float | None = None
    review_score_min: float | None = None
    destination: str | None = None


class UserContextPlan(BaseModel):
    """User-profile fields needed by retrieval."""

    needs_user_profile: bool = False
    profile_fields: list[str] = Field(default_factory=list)
    reason: str = ""


class SourcePlan(BaseModel):
    """Base plan for one retrieval source."""

    enabled: bool = False
    implementation_status: ImplementationStatus = "disabled"
    reason: str = ""
    input: dict[str, Any] = Field(default_factory=dict)


class HotelSqlSourcePlan(SourcePlan):
    """Plan for hotel SQL/API factual lookup."""

    implementation_status: ImplementationStatus = "ready"
    need: list[str] = Field(default_factory=list)


class VectorSearchSourcePlan(SourcePlan):
    """Plan for future vector retrieval."""

    implementation_status: ImplementationStatus = "planned"
    query: str = ""
    top_k: int = 10
    filters: dict[str, Any] = Field(default_factory=dict)
    use_user_profile: bool = False


class GraphSearchSourcePlan(SourcePlan):
    """Plan for future graph traversal."""

    implementation_status: ImplementationStatus = "planned"
    start_nodes: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    max_depth: int = 2


class ShortTermMemorySourcePlan(SourcePlan):
    """Plan for short-term memory retrieval."""

    implementation_status: ImplementationStatus = "ready"


class MultiSourceRetrievalPlan(BaseModel):
    """Retrieval source decisions for a RAG request."""

    hotel_sql: HotelSqlSourcePlan = Field(default_factory=HotelSqlSourcePlan)
    vector_search: VectorSearchSourcePlan = Field(default_factory=VectorSearchSourcePlan)
    graph_search: GraphSearchSourcePlan = Field(default_factory=GraphSearchSourcePlan)
    user_profile: SourcePlan = Field(default_factory=SourcePlan)
    short_term_memory: ShortTermMemorySourcePlan = Field(
        default_factory=ShortTermMemorySourcePlan
    )


class FusionStrategy(BaseModel):
    """Candidate fusion strategy for multi-source retrieval."""

    enabled: bool = False
    method: str = "none"
    weights: dict[str, float] = Field(default_factory=dict)
    reason: str = ""


class PlanStep(BaseModel):
    """Executable or future execution step planned by the planner."""

    order: int
    tool: SourceName
    action: str
    input: dict[str, Any] = Field(default_factory=dict)
    output_key: str
    depends_on: list[str] = Field(default_factory=list)
    implementation_status: ImplementationStatus = "ready"


class RAGPlan(BaseModel):
    """Top-level multi-source plan produced before retrieval."""

    query: str
    query_type: QueryType
    answer_mode: AnswerMode
    entities: PlanEntities = Field(default_factory=PlanEntities)
    filters: PlanFilters = Field(default_factory=PlanFilters)
    user_context: UserContextPlan = Field(default_factory=UserContextPlan)
    retrieval_plan: MultiSourceRetrievalPlan = Field(
        default_factory=MultiSourceRetrievalPlan
    )
    fusion_strategy: FusionStrategy = Field(default_factory=FusionStrategy)
    required_data: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


def build_rag_plan(
    query: str,
    *,
    features: dict[str, Any] | None = None,
    user_id: str = "current_user",
    vector_available: bool = False,
    graph_available: bool = False,
) -> RAGPlan:
    """Build a structured multi-source RAG plan from query and input features.

    Args:
        query: User query text.
        features: Optional normalized input features from rag_system input schema.
        user_id: User ID used by the future user profile retrieval step.
        vector_available: Whether vector search execution is available now.
        graph_available: Whether graph search execution is available now.

    Returns:
        RAGPlan that can be serialized with model_dump/model_dump_json.
    """

    clean_query = query.strip()
    normalized_query = _normalize_text(clean_query)
    features = features or {}

    entities = _build_entities(features)
    filters = _build_filters(features, entities)
    query_type = infer_query_type(normalized_query, entities, filters)
    answer_mode = _answer_mode_for(query_type)
    required_data = _required_data_for(query_type)
    user_context = _build_user_context(query_type, filters, user_id)
    retrieval_plan = _build_retrieval_plan(
        query=clean_query,
        normalized_query=normalized_query,
        query_type=query_type,
        entities=entities,
        filters=filters,
        user_context=user_context,
        user_id=user_id,
        vector_available=vector_available,
        graph_available=graph_available,
    )
    fusion_strategy = _build_fusion_strategy(query_type, retrieval_plan)
    steps = _build_steps(retrieval_plan, fusion_strategy)
    warnings = _build_warnings(query_type, entities, vector_available, graph_available)

    return RAGPlan(
        query=clean_query,
        query_type=query_type,
        answer_mode=answer_mode,
        entities=entities,
        filters=filters,
        user_context=user_context,
        retrieval_plan=retrieval_plan,
        fusion_strategy=fusion_strategy,
        required_data=required_data,
        steps=steps,
        confidence=_confidence_for(query_type, entities, filters),
        warnings=warnings,
    )


def build_rag_plan_from_input(
    rag_input: dict[str, Any],
    *,
    user_id: str = "current_user",
    vector_available: bool = False,
    graph_available: bool = False,
) -> RAGPlan:
    """Build RAGPlan from the existing DA09 input schema."""

    parameters = rag_input.get("parameters", {})
    query = parameters.get("query", "")
    features = parameters.get("features", {})
    return build_rag_plan(
        query,
        features=features,
        user_id=user_id,
        vector_available=vector_available,
        graph_available=graph_available,
    )


def infer_query_type(
    normalized_query: str,
    entities: PlanEntities,
    filters: PlanFilters,
) -> QueryType:
    """Infer the standardized query type using conservative rules."""

    if not normalized_query:
        return "unknown"

    has_hotel = bool(entities.hotel_name or entities.hotel_ids)
    has_search_filter = bool(
        filters.amenities
        or filters.expectations
        or filters.suitable_for
        or filters.destination
    )

    if _contains_any(normalized_query, ["so sanh", "compare", "vs", "khac nhau"]):
        return "hotel_compare"

    if _contains_any(
        normalized_query,
        [
            "check in",
            "check-in",
            "check out",
            "check-out",
            "chinh sach",
            "tre em",
            "thu cung",
            "pet",
            "huy phong",
            "hoan tien",
        ],
    ):
        return "policy_detail"

    if _contains_any(
        normalized_query,
        ["hoat dong", "activity", "activities", "co gi choi", "vui choi"],
    ):
        return "activities_detail" if has_hotel else "activity_search"

    if has_hotel and _contains_any(
        normalized_query,
        ["thong tin", "chi tiet", "gioi thieu", "overview", "detail"],
    ):
        return "hotel_detail"

    if has_hotel and not has_search_filter:
        return "hotel_detail"

    if has_search_filter or _contains_any(
        normalized_query,
        ["tim", "goi y", "phu hop", "gan bien", "resort", "khach san co"],
    ):
        return "hotel_search"

    return "unknown"


def _build_entities(features: dict[str, Any]) -> PlanEntities:
    """Build entity plan from normalized input features."""

    amenities = _as_string_list(features.get("amenities"))
    expectations = _as_string_list(features.get("expectations"))
    hotel_id = features.get("hotel_id")
    hotel_ids = []
    if isinstance(hotel_id, int):
        hotel_ids.append(hotel_id)
    elif isinstance(hotel_id, str) and hotel_id.isdigit():
        hotel_ids.append(int(hotel_id))

    return PlanEntities(
        hotel_name=_clean_optional_string(features.get("hotel_name")),
        hotel_ids=hotel_ids,
        destination=_clean_optional_string(
            features.get("destination") or features.get("city")
        ),
        activity_name=_clean_optional_string(features.get("activity_name")),
        amenities=amenities,
        policies=[
            item
            for item in expectations
            if _contains_any(_normalize_text(item), ["policy", "chinh sach"])
        ],
    )


def _build_filters(features: dict[str, Any], entities: PlanEntities) -> PlanFilters:
    """Build retrieval filters from features and entities."""

    expectations = _as_string_list(features.get("expectations"))
    amenities = entities.amenities
    return PlanFilters(
        amenities=amenities,
        suitable_for=[
            item
            for item in expectations
            if _contains_any(_normalize_text(item), ["family", "gia dinh", "couple"])
        ],
        expectations=expectations,
        price_min=_as_float(features.get("price_min")),
        price_max=_as_float(features.get("price_max")),
        star_rating_min=_as_float(features.get("star_rating_min")),
        review_score_min=_as_float(features.get("review_score_min")),
        destination=entities.destination,
    )


def _build_user_context(
    query_type: QueryType,
    filters: PlanFilters,
    user_id: str,
) -> UserContextPlan:
    """Decide whether user profile should be included in retrieval."""

    needs_user_profile = query_type in {"hotel_search", "activity_search"} or bool(
        filters.expectations
    )
    profile_fields = []
    if needs_user_profile:
        profile_fields = [
            "traveler_type",
            "budget_level",
            "preferred_amenities",
            "past_destinations",
        ]

    return UserContextPlan(
        needs_user_profile=needs_user_profile,
        profile_fields=profile_fields,
        reason=f"Use profile for personalized retrieval for user_id={user_id}."
        if needs_user_profile
        else "No personalization required for this query type.",
    )


def _build_retrieval_plan(
    *,
    query: str,
    normalized_query: str,
    query_type: QueryType,
    entities: PlanEntities,
    filters: PlanFilters,
    user_context: UserContextPlan,
    user_id: str,
    vector_available: bool,
    graph_available: bool,
) -> MultiSourceRetrievalPlan:
    """Build per-source retrieval decisions."""

    sql_need = _sql_need_for(query_type)
    has_hotel = bool(entities.hotel_name or entities.hotel_ids)
    use_sql = query_type in {
        "hotel_detail",
        "policy_detail",
        "activities_detail",
        "hotel_compare",
    } or query_type in {"hotel_search", "activity_search"}
    sql_is_direct_lookup = query_type not in {"hotel_search", "activity_search"} or has_hotel
    if not use_sql:
        sql_status: ImplementationStatus = "disabled"
        sql_reason = "No hotel facts required at planning time."
    elif sql_is_direct_lookup:
        sql_status = "ready"
        sql_reason = "Fetch factual hotel data from DA10 SQL/API."
    else:
        sql_status = "planned"
        sql_reason = "Hydrate candidate hotel facts after vector/graph candidate retrieval."

    vector_enabled = query_type in {"hotel_search", "activity_search", "hotel_compare"}
    graph_enabled = query_type in {
        "hotel_search",
        "activity_search",
        "activities_detail",
        "hotel_compare",
    }

    concepts = _graph_concepts(normalized_query, entities, filters)

    return MultiSourceRetrievalPlan(
        hotel_sql=HotelSqlSourcePlan(
            enabled=use_sql,
            implementation_status=sql_status,
            reason=sql_reason,
            need=sql_need,
            input={
                "hotel_name": entities.hotel_name,
                "hotel_id": entities.hotel_ids[0] if entities.hotel_ids else None,
                "hotel_ids_ref": None if sql_is_direct_lookup else "fused_candidates",
                "city": entities.destination,
                "need": sql_need,
            },
        ),
        vector_search=VectorSearchSourcePlan(
            enabled=vector_enabled,
            implementation_status="ready"
            if vector_enabled and vector_available
            else "planned"
            if vector_enabled
            else "disabled",
            reason="Semantic candidate retrieval from vector DB."
            if vector_enabled
            else "Vector retrieval not needed for this query type.",
            query=query,
            top_k=10,
            filters={
                "entity_type": "hotel"
                if query_type in {"hotel_search", "hotel_compare"}
                else "activity",
                "destination": filters.destination,
                "amenities": filters.amenities,
                "suitable_for": filters.suitable_for,
            },
            use_user_profile=user_context.needs_user_profile,
            input={
                "query": query,
                "top_k": 10,
                "filters": {
                    "destination": filters.destination,
                    "amenities": filters.amenities,
                    "suitable_for": filters.suitable_for,
                },
                "user_profile_ref": "user_profile"
                if user_context.needs_user_profile
                else None,
            },
        ),
        graph_search=GraphSearchSourcePlan(
            enabled=graph_enabled,
            implementation_status="ready"
            if graph_enabled and graph_available
            else "planned"
            if graph_enabled
            else "disabled",
            reason="Find relationships among hotels, amenities, activities, and places."
            if graph_enabled
            else "Graph traversal not needed for this query type.",
            start_nodes=concepts,
            relations=_graph_relations_for(query_type),
            max_depth=2,
            input={
                "concepts": concepts,
                "relations": _graph_relations_for(query_type),
                "max_depth": 2,
            },
        ),
        user_profile=SourcePlan(
            enabled=user_context.needs_user_profile,
            implementation_status="ready"
            if user_context.needs_user_profile
            else "disabled",
            reason=user_context.reason,
            input={
                "user_id": user_id,
                "fields": user_context.profile_fields,
            },
        ),
        short_term_memory=ShortTermMemorySourcePlan(
            enabled=True,
            implementation_status="ready",
            reason="Use conversation context to resolve omitted hotel or destination.",
            input={"query": query},
        ),
    )


def _build_fusion_strategy(
    query_type: QueryType,
    retrieval_plan: MultiSourceRetrievalPlan,
) -> FusionStrategy:
    """Build candidate fusion plan for multi-source search queries."""

    enabled_sources = [
        name
        for name, source in {
            "sql": retrieval_plan.hotel_sql,
            "vector": retrieval_plan.vector_search,
            "graph": retrieval_plan.graph_search,
            "user_profile": retrieval_plan.user_profile,
        }.items()
        if source.enabled
    ]

    if query_type not in {"hotel_search", "activity_search", "hotel_compare"}:
        return FusionStrategy(
            enabled=False,
            method="none",
            reason="Detail queries do not need candidate fusion.",
        )

    weights = {
        "vector": 0.55,
        "graph": 0.25,
        "sql": 0.10,
        "user_profile": 0.10,
    }
    return FusionStrategy(
        enabled=len(enabled_sources) > 1,
        method="weighted_merge",
        weights={key: value for key, value in weights.items() if key in enabled_sources},
        reason="Merge candidate evidence from all enabled retrieval sources.",
    )


def _build_steps(
    retrieval_plan: MultiSourceRetrievalPlan,
    fusion_strategy: FusionStrategy,
) -> list[PlanStep]:
    """Build ordered execution steps from source plans."""

    steps: list[PlanStep] = []
    order = 1

    if retrieval_plan.short_term_memory.enabled:
        steps.append(
            PlanStep(
                order=order,
                tool="short_term_memory",
                action="retrieve_context",
                input=retrieval_plan.short_term_memory.input,
                output_key="short_term_memory_context",
                implementation_status=retrieval_plan.short_term_memory.implementation_status,
            )
        )
        order += 1

    if retrieval_plan.user_profile.enabled:
        steps.append(
            PlanStep(
                order=order,
                tool="user_profile",
                action="get_preferences",
                input=retrieval_plan.user_profile.input,
                output_key="user_profile",
                implementation_status=retrieval_plan.user_profile.implementation_status,
            )
        )
        order += 1

    sql_hydrates_candidates = bool(retrieval_plan.hotel_sql.input.get("hotel_ids_ref"))

    if retrieval_plan.hotel_sql.enabled and not sql_hydrates_candidates:
        steps.append(
            PlanStep(
                order=order,
                tool="hotel_sql",
                action="lookup",
                input=retrieval_plan.hotel_sql.input,
                output_key="hotel_sql_data",
                depends_on=["short_term_memory_context"],
                implementation_status=retrieval_plan.hotel_sql.implementation_status,
            )
        )
        order += 1

    if retrieval_plan.vector_search.enabled:
        depends_on = ["short_term_memory_context"]
        if retrieval_plan.vector_search.use_user_profile:
            depends_on.append("user_profile")
        steps.append(
            PlanStep(
                order=order,
                tool="vector_search",
                action="semantic_search",
                input=retrieval_plan.vector_search.input,
                output_key="vector_candidates",
                depends_on=depends_on,
                implementation_status=retrieval_plan.vector_search.implementation_status,
            )
        )
        order += 1

    if retrieval_plan.graph_search.enabled:
        steps.append(
            PlanStep(
                order=order,
                tool="graph_search",
                action="find_related_entities",
                input=retrieval_plan.graph_search.input,
                output_key="graph_candidates",
                depends_on=["short_term_memory_context"],
                implementation_status=retrieval_plan.graph_search.implementation_status,
            )
        )
        order += 1

    if fusion_strategy.enabled:
        source_keys = [
            step.output_key
            for step in steps
            if step.output_key
            in {"hotel_sql_data", "vector_candidates", "graph_candidates", "user_profile"}
        ]
        steps.append(
            PlanStep(
                order=order,
                tool="fusion",
                action="merge_candidates",
                input={
                    "sources": source_keys,
                    "method": fusion_strategy.method,
                    "weights": fusion_strategy.weights,
                },
                output_key="fused_candidates",
                depends_on=source_keys,
                implementation_status="planned",
            )
        )
        order += 1

    if retrieval_plan.hotel_sql.enabled and sql_hydrates_candidates:
        depends_on = [retrieval_plan.hotel_sql.input["hotel_ids_ref"]]
        steps.append(
            PlanStep(
                order=order,
                tool="hotel_sql",
                action="hydrate_candidates",
                input=retrieval_plan.hotel_sql.input,
                output_key="hotel_sql_data",
                depends_on=depends_on,
                implementation_status=retrieval_plan.hotel_sql.implementation_status,
            )
        )

    return steps


def _required_data_for(query_type: QueryType) -> list[str]:
    """Return required factual data categories for a query type."""

    mapping = {
        "hotel_detail": ["detail", "policies", "activities"],
        "policy_detail": ["policies"],
        "activities_detail": ["activities"],
        "hotel_search": [
            "hotel_candidates",
            "matched_tags",
            "highlights",
            "user_preferences",
        ],
        "activity_search": ["activity_candidates", "related_hotel_ids"],
        "hotel_compare": ["detail", "policies", "activities", "comparison_fields"],
        "unknown": [],
    }
    return mapping[query_type]


def _sql_need_for(query_type: QueryType) -> list[str]:
    """Return HotelSqlTool need list for the query type."""

    mapping = {
        "hotel_detail": ["detail", "policies", "activities"],
        "policy_detail": ["policies"],
        "activities_detail": ["activities"],
        "hotel_search": ["detail"],
        "activity_search": ["activities"],
        "hotel_compare": ["detail", "policies", "activities"],
        "unknown": [],
    }
    return mapping[query_type]


def _answer_mode_for(query_type: QueryType) -> AnswerMode:
    """Return answer mode from query type."""

    if query_type in {"hotel_detail", "policy_detail", "activities_detail"}:
        return "detail"
    if query_type in {"hotel_search", "activity_search"}:
        return "list"
    if query_type == "hotel_compare":
        return "compare"
    return "fallback"


def _graph_relations_for(query_type: QueryType) -> list[str]:
    """Return graph relations that would be useful when graph DB exists."""

    if query_type == "activity_search":
        return ["NEAR", "HAS_ACTIVITY", "RELATED_TO"]
    if query_type == "activities_detail":
        return ["HAS_ACTIVITY", "NEAR"]
    if query_type == "hotel_compare":
        return ["HAS_AMENITY", "HAS_POLICY", "HAS_ACTIVITY", "LOCATED_IN"]
    if query_type == "hotel_search":
        return ["SUITABLE_FOR", "HAS_AMENITY", "NEAR", "HAS_ACTIVITY"]
    return []


def _graph_concepts(
    normalized_query: str,
    entities: PlanEntities,
    filters: PlanFilters,
) -> list[str]:
    """Build graph start concepts from query and extracted filters."""

    concepts = []
    for value in [
        entities.hotel_name,
        entities.destination,
        entities.activity_name,
        *filters.amenities,
        *filters.suitable_for,
        *filters.expectations,
    ]:
        if value:
            concepts.append(str(value))

    keyword_concepts = {
        "gan bien": "beach",
        "bien": "beach",
        "gia dinh": "family",
        "tre em": "kids",
        "ho boi": "pool",
        "spa": "spa",
        "hoat dong": "activity",
    }
    for keyword, concept in keyword_concepts.items():
        if keyword in normalized_query:
            concepts.append(concept)

    return _dedupe(concepts)


def _build_warnings(
    query_type: QueryType,
    entities: PlanEntities,
    vector_available: bool,
    graph_available: bool,
) -> list[str]:
    """Build planner warnings without blocking plan creation."""

    warnings = []
    if query_type == "unknown":
        warnings.append("Unable to determine intent")
    if query_type in {"hotel_detail", "policy_detail", "activities_detail"} and not (
        entities.hotel_name or entities.hotel_ids
    ):
        warnings.append("Hotel entity is missing; retrieval may need memory context")
    vector_planned = query_type in {"hotel_search", "activity_search", "hotel_compare"}
    graph_planned = query_type in {
        "hotel_search",
        "activity_search",
        "activities_detail",
        "hotel_compare",
    }
    if vector_planned and not vector_available:
        warnings.append("Vector search is planned but not executable yet")
    if graph_planned and not graph_available:
        warnings.append("Graph search is planned but not executable yet")
    return warnings


def _confidence_for(
    query_type: QueryType,
    entities: PlanEntities,
    filters: PlanFilters,
) -> float:
    """Return a simple confidence estimate for the rule-based planner."""

    if query_type == "unknown":
        return 0.0

    confidence = 0.65
    if entities.hotel_name or entities.hotel_ids:
        confidence += 0.15
    if filters.amenities or filters.expectations or filters.destination:
        confidence += 0.10
    if query_type in {"policy_detail", "activities_detail", "hotel_compare"}:
        confidence += 0.05
    return min(confidence, 0.9)


def _as_string_list(value: Any) -> list[str]:
    """Coerce a feature value into a clean string list."""

    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _clean_optional_string(value: Any) -> str | None:
    """Return a stripped string or None."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float | None:
    """Convert a value to float if possible."""

    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    """Return whether text contains any keyword."""

    return any(keyword in text for keyword in keywords)


def _dedupe(values: list[str]) -> list[str]:
    """Return values with duplicates removed while preserving order."""

    seen = set()
    result = []
    for value in values:
        key = _normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _normalize_text(value: str) -> str:
    """Normalize text for accent-insensitive rule matching."""

    normalized = unicodedata.normalize("NFD", value.strip().lower())
    ascii_text = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    return ascii_text.replace("đ", "d")


RAG_PLAN_EXAMPLES: dict[str, RAGPlan] = {
    "hotel_detail": build_rag_plan(
        "Show hotel details",
        features={"hotel_name": "Renaissance Riverside"},
    ),
    "hotel_search": build_rag_plan(
        "Find family beach resorts with pool",
        features={
            "amenities": ["pool", "beach"],
            "expectations": ["family"],
        },
    ),
    "activity_search": build_rag_plan(
        "What activities are near the hotel?",
        features={"destination": "Da Nang"},
    ),
    "hotel_compare": build_rag_plan(
        "Compare Hotel A and Hotel B",
    ),
    "unknown": build_rag_plan(""),
}
