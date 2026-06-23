import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from query_understanding.checker import ModelChecker
from query_understanding.guardrail.classifier import OTAGuardrailClassifier
from query_understanding.intent import LLMIntentExtractor, SemanticTagMapper, TagGraphExpansionService
from query_understanding.merger import CurrentProfileMerger
from query_understanding.models.intent import MappedSemanticItem, SemanticMappingResult
from query_understanding.models.planner import (
    ActiveProfile,
    CountInteractionValue,
    LongTermProfile,
    NegativePreferences,
    PriceRange,
    RecommendationClicks,
    RuntimeTag,
    RuntimeTagExpansion,
    SessionContext,
    SessionProfileUpdateResult,
    UserProfile,
)
from query_understanding.models.router import RouterResult
from query_understanding.planner.planner import SearchPlanner
from query_understanding.router.router import Router
from query_understanding.session_profile import (
    GRAPH_EXPANSION_SEED_CATEGORIES,
    SessionProfileUpdater,
    normalize_long_term_trip_type_value,
)

logger = logging.getLogger(__name__)
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_QU_TRACE_DIR = Path(os.getenv("QU_TRACE_LOG_DIR", str(_BACKEND_DIR / "logs")))
JSON_TRACE_FILES = {
    "user_profile": Path(
        os.getenv("QU_USER_PROFILE_LOG_FILE", str(_QU_TRACE_DIR / "qu_user_profile.json"))
    ),
    "active_user_profile": Path(
        os.getenv("QU_ACTIVE_USER_PROFILE_LOG_FILE", str(_QU_TRACE_DIR / "qu_active_user_profile.json"))
    ),
    "current_active_profile": Path(
        os.getenv(
            "QU_CURRENT_ACTIVE_PROFILE_LOG_FILE",
            str(_QU_TRACE_DIR / "qu_current_active_profile.json"),
        )
    ),
    "tag_mapping": Path(
        os.getenv("QU_TAG_MAPPING_LOG_FILE", str(_QU_TRACE_DIR / "qu_tag_mapping.json"))
    ),
    "query_classification": Path(
        os.getenv("QU_QUERY_CLASSIFICATION_LOG_FILE", str(_QU_TRACE_DIR / "qu_query_classification.json"))
    ),
    "profile_retention": Path(
        os.getenv("QU_PROFILE_RETENTION_LOG_FILE", str(_QU_TRACE_DIR / "qu_profile_retention.json"))
    ),
}
_JSON_TRACE_LOCK = threading.Lock()


@dataclass(slots=True)
class PipelineTrace:
    query: str
    guardrail: dict[str, Any]
    checker: dict[str, Any]
    intent: dict[str, Any]
    llm_traces: dict[str, Any]
    user_profile: dict[str, Any]
    session_profile_update: dict[str, Any]
    active_profile: dict[str, Any]
    search_plan: dict[str, Any]
    router: dict[str, Any]
    timing: dict[str, Any]


@dataclass(slots=True)
class PipelineResult:
    trace: PipelineTrace
    router_result: RouterResult | None
    updated_user_profile: UserProfile
    active_profile: ActiveProfile | None


class QueryUnderstandingPipeline:
    def __init__(
        self,
        guardrail: OTAGuardrailClassifier | None = None,
        checker: ModelChecker | None = None,
        intent_extractor: LLMIntentExtractor | None = None,
        semantic_mapper: SemanticTagMapper | None = None,
        tag_graph_expander: TagGraphExpansionService | None = None,
        search_planner: SearchPlanner | None = None,
        router: Router | None = None,
        current_profile_merger: CurrentProfileMerger | None = None,
    ) -> None:
        self.guardrail = guardrail or OTAGuardrailClassifier()
        self.checker = checker or ModelChecker()
        self.intent_extractor = intent_extractor or LLMIntentExtractor()
        self.semantic_mapper = semantic_mapper or SemanticTagMapper()
        self.tag_graph_expander = tag_graph_expander or TagGraphExpansionService()
        self.search_planner = search_planner or SearchPlanner()
        self.router = router or Router()
        self.current_profile_merger = current_profile_merger or CurrentProfileMerger()
        self._parallel_executor = ThreadPoolExecutor(max_workers=2)

    def run(
        self,
        query: str,
        user_profile_input: UserProfile | dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> PipelineResult:
        pipeline_start = time.perf_counter()
        timing: dict[str, Any] = {}
        coerce_start = time.perf_counter()
        user_profile = self._coerce_user_profile(user_profile_input)
        timing["user_profile_coerce_ms"] = _elapsed_ms(coerce_start)
        _log_qu_trace(
            "user_profile_coerced",
            {
                "user_id": user_profile.user_id,
                "user_profile": asdict(user_profile),
                "session_context": asdict(user_profile.session_context),
            },
        )
        _log_qu_json(
            "user_profile",
            "user_profile_coerced",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "long_term_profile": asdict(user_profile.long_term_profile),
                "tagremoved_profile": asdict(user_profile.tagremoved_profile),
                "session_context": asdict(user_profile.session_context),
            },
        )
        self._log_current_active_profile_snapshot(
            query=query,
            user_profile=user_profile,
            stage="request_state_loaded",
        )
        recent_user_queries = self._recent_user_queries(conversation_history)
        guardrail_start = time.perf_counter()
        guardrail_result = self.guardrail.classify(
            query,
            user_id=user_profile.user_id,
            recent_user_queries=recent_user_queries,
            session_context=asdict(user_profile.session_context),
        )
        timing["guardrail_ms"] = _elapsed_ms(guardrail_start)
        _log_qu_json(
            "query_classification",
            "guardrail_classified",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "guardrail": asdict(guardrail_result),
                "guardrail_trace": dict(self.guardrail.last_trace),
            },
        )
        if not guardrail_result.allow:
            timing["total_pipeline_ms"] = _elapsed_ms(pipeline_start)
            _log_qu_json(
                "query_classification",
                "query_classified",
                {
                    "user_id": user_profile.user_id,
                    "query": query,
                    "classification": "blocked_by_guardrail",
                    "can_build_plan": False,
                    "guardrail": asdict(guardrail_result),
                    "missing_fields": [],
                    "search_plan": {},
                    "router": {},
                },
            )
            return PipelineResult(
                trace=PipelineTrace(
                    query=query,
                    guardrail=asdict(guardrail_result),
                    checker={},
                    intent={},
                    llm_traces={
                        "guardrail": dict(self.guardrail.last_trace),
                        "intent": {},
                        "semantic_mapping": {},
                        "tag_graph_expansion": {},
                    },
                    user_profile=asdict(user_profile),
                    session_profile_update={},
                    active_profile={},
                    search_plan={},
                    router={},
                    timing=timing,
                ),
                router_result=None,
                updated_user_profile=user_profile,
                active_profile=None,
            )

        # P1: check current profile right after guardrail, before extraction.
        initial_profile_check_start = time.perf_counter()
        initial_profile_check = self.checker.check_current_profile(user_profile)
        timing["initial_profile_check_ms"] = _elapsed_ms(initial_profile_check_start)
        # P3: decide whether query + session context are sufficient before Parallel Execution.
        initial_plan_readiness_start = time.perf_counter()
        plan_readiness = self.checker.check_plan_readiness(query=query, current_profile=user_profile)
        timing["initial_plan_readiness_ms"] = _elapsed_ms(initial_plan_readiness_start)
        initial_plan_readiness = plan_readiness
        precheck_intent_result = None
        precheck_session_update = None
        precheck_active_profile = None
        post_extract_plan_readiness = None

        if plan_readiness.requires_recommendation and not plan_readiness.can_build_plan:
            precheck_extract_start = time.perf_counter()
            (
                precheck_intent_result,
                precheck_session_update,
                precheck_active_profile,
            ), precheck_extract_detail = self._extract_merge_current_profile_with_timing(
                query,
                user_profile,
                conversation_history=conversation_history or [],
            )
            timing["precheck_extract_merge_ms"] = _elapsed_ms(precheck_extract_start)
            timing["precheck_extract_merge_detail"] = precheck_extract_detail
            post_extract_plan_readiness_start = time.perf_counter()
            post_extract_plan_readiness = self.checker.check_plan_readiness(
                query=query,
                current_profile=user_profile,
                requires_recommendation=initial_plan_readiness.requires_recommendation,
            )
            timing["post_extract_plan_readiness_ms"] = _elapsed_ms(post_extract_plan_readiness_start)
            timing["post_extract_plan_readiness_reused_requires_recommendation"] = True
            plan_readiness = post_extract_plan_readiness

        if not plan_readiness.can_build_plan:
            timing["total_pipeline_ms"] = _elapsed_ms(pipeline_start)
            _log_qu_json(
                "query_classification",
                "query_classified",
                {
                    "user_id": user_profile.user_id,
                    "query": query,
                    "classification": "clarification_needed",
                    "can_build_plan": False,
                    "guardrail": asdict(guardrail_result),
                    "initial_plan_readiness": asdict(initial_plan_readiness),
                    "plan_readiness": asdict(plan_readiness),
                    "post_extract_plan_readiness": (
                        asdict(post_extract_plan_readiness) if post_extract_plan_readiness else {}
                    ),
                    "intent": asdict(precheck_intent_result) if precheck_intent_result else {},
                    "conversation_history": (
                        dict(self.intent_extractor.last_trace).get("conversation_history", [])
                        if precheck_intent_result
                        else []
                    ),
                    "missing_fields": getattr(plan_readiness, "missing_fields", []),
                    "search_plan": {},
                    "router": {},
                },
            )
            return PipelineResult(
                trace=PipelineTrace(
                    query=query,
                    guardrail=asdict(guardrail_result),
                    checker={
                        "initial_profile_check": asdict(initial_profile_check),
                        "initial_plan_readiness": asdict(initial_plan_readiness),
                        "plan_readiness": asdict(plan_readiness),
                        "post_extract_plan_readiness": (
                            asdict(post_extract_plan_readiness) if post_extract_plan_readiness else {}
                        ),
                    },
                    intent=asdict(precheck_intent_result) if precheck_intent_result else {},
                    llm_traces={
                        "guardrail": dict(self.guardrail.last_trace),
                        "intent": dict(self.intent_extractor.last_trace) if precheck_intent_result else {},
                        "semantic_mapping": dict(self.semantic_mapper.last_trace) if precheck_intent_result else {},
                        "tag_graph_expansion": (
                            dict(self.tag_graph_expander.last_trace) if precheck_intent_result else {}
                        ),
                    },
                    user_profile=asdict(user_profile),
                    session_profile_update=asdict(precheck_session_update) if precheck_session_update else {},
                    active_profile=asdict(precheck_active_profile) if precheck_active_profile else {},
                    search_plan={},
                    router={},
                    timing=timing,
                ),
                router_result=None,
                updated_user_profile=user_profile,
                active_profile=precheck_active_profile,
            )

        if precheck_intent_result is not None and precheck_active_profile is not None and precheck_session_update is not None:
            search_plan_start = time.perf_counter()
            search_plan_result = self.search_planner.run(
                query,
                conversation_history or [],
            )
            timing["search_plan_ms"] = _elapsed_ms(search_plan_start)
            intent_result = precheck_intent_result
            session_update = precheck_session_update
            active_profile = precheck_active_profile
        else:
            parallel_start = time.perf_counter()
            search_plan_future = self._parallel_executor.submit(
                self._timed_search_plan_run,
                query,
                conversation_history or [],
            )
            profile_branch_future = self._parallel_executor.submit(
                self._timed_extract_merge_current_profile,
                query,
                user_profile,
                conversation_history or [],
            )
            search_plan_result, search_plan_ms = search_plan_future.result()
            (intent_result, session_update, active_profile), extract_merge_ms, extract_merge_detail = (
                profile_branch_future.result()
            )
            timing["parallel_execution_ms"] = _elapsed_ms(parallel_start)
            timing["search_plan_ms"] = search_plan_ms
            timing["extract_merge_ms"] = extract_merge_ms
            timing["extract_merge_detail"] = extract_merge_detail

        router_start = time.perf_counter()
        router_result = self.router.run(
            query=query,
            search_plan=search_plan_result,
            intent=intent_result,
            active_profile=active_profile,
            session_context=user_profile.session_context,
            user_id=user_profile.user_id,
        )
        timing["router_ms"] = _elapsed_ms(router_start)
        timing["total_pipeline_ms"] = _elapsed_ms(pipeline_start)
        _log_qu_json(
            "query_classification",
            "query_classified",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "classification": "plan_ready",
                "can_build_plan": True,
                "guardrail": asdict(guardrail_result),
                "initial_plan_readiness": asdict(initial_plan_readiness),
                "plan_readiness": asdict(plan_readiness),
                "intent": asdict(intent_result),
                "conversation_history": dict(self.intent_extractor.last_trace).get("conversation_history", []),
                "search_plan": asdict(search_plan_result),
                "router": asdict(router_result),
                "recommendation_intent_types": [
                    str(step.intent_type) for step in router_result.recommendation_plan
                ],
                "rag_intent_types": [
                    str(step.intent_type) for step in router_result.rag_plan
                ],
            },
        )

        return PipelineResult(
            trace=PipelineTrace(
                query=query,
                guardrail=asdict(guardrail_result),
                checker={
                    "initial_profile_check": asdict(initial_profile_check),
                    "initial_plan_readiness": asdict(initial_plan_readiness),
                    "plan_readiness": asdict(plan_readiness),
                    "post_extract_plan_readiness": (
                        asdict(post_extract_plan_readiness) if post_extract_plan_readiness else {}
                    ),
                },
                intent=asdict(intent_result),
                llm_traces={
                    "guardrail": dict(self.guardrail.last_trace),
                    "intent": dict(self.intent_extractor.last_trace),
                    "semantic_mapping": dict(self.semantic_mapper.last_trace),
                    "tag_graph_expansion": dict(self.tag_graph_expander.last_trace),
                },
                user_profile=asdict(user_profile),
                session_profile_update=asdict(session_update),
                active_profile=asdict(active_profile),
                search_plan=asdict(search_plan_result),
                router=asdict(router_result),
                timing=timing,
            ),
            router_result=router_result,
            updated_user_profile=user_profile,
            active_profile=active_profile,
        )

    def _extract_merge_current_profile(
        self,
        query: str,
        user_profile: UserProfile,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[Any, SessionProfileUpdateResult, ActiveProfile]:
        result, _ = self._extract_merge_current_profile_with_timing(
            query,
            user_profile,
            conversation_history=conversation_history,
        )
        return result

    def _extract_merge_current_profile_with_timing(
        self,
        query: str,
        user_profile: UserProfile,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[tuple[Any, SessionProfileUpdateResult, ActiveProfile], dict[str, float]]:
        detail_start = time.perf_counter()
        intent_start = time.perf_counter()
        intent_result = self.intent_extractor.extract(
            query,
            user_id=user_profile.user_id,
            conversation_history=conversation_history,
            session_context=asdict(user_profile.session_context),
        )
        intent_extract_ms = _elapsed_ms(intent_start)
        _log_qu_trace(
            "intent_extracted",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "conversation_history": dict(self.intent_extractor.last_trace).get("conversation_history", []),
                "intent": asdict(intent_result),
            },
        )
        semantic_mapping_start = time.perf_counter()
        semantic_mapping = self.semantic_mapper.map_items(intent_result.semantic_preferences.items)
        semantic_mapping_ms = _elapsed_ms(semantic_mapping_start)
        _log_qu_trace(
            "tag_mapping_completed",
            {
                "user_id": user_profile.user_id,
                "semantic_mapping": asdict(semantic_mapping),
                "semantic_mapper_trace": dict(self.semantic_mapper.last_trace),
            },
        )
        tag_graph_expansion_start = time.perf_counter()
        graph_seed_items = self._build_tag_graph_seed_items(intent_result, semantic_mapping)
        runtime_tag_expansion = self.tag_graph_expander.expand_mapping(graph_seed_items)
        tag_graph_expansion_ms = _elapsed_ms(tag_graph_expansion_start)
        _log_qu_trace(
            "tag_graph_expansion_completed",
            {
                "user_id": user_profile.user_id,
                "graph_seed_items": [asdict(item) for item in graph_seed_items],
                "runtime_tag_expansion": asdict(runtime_tag_expansion),
                "tag_graph_expansion_trace": dict(self.tag_graph_expander.last_trace),
            },
        )
        _log_qu_json(
            "tag_mapping",
            "tag_mapping_completed",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "semantic_preferences": asdict(intent_result.semantic_preferences),
                "semantic_mapping": asdict(semantic_mapping),
                "semantic_mapper_trace": dict(self.semantic_mapper.last_trace),
                "graph_seed_items": [asdict(item) for item in graph_seed_items],
                "runtime_tag_expansion": asdict(runtime_tag_expansion),
                "tag_graph_expansion_trace": dict(self.tag_graph_expander.last_trace),
            },
        )
        session_update_start = time.perf_counter()
        session_update = self._apply_session_profile_update(
            user_profile,
            intent_result,
            semantic_mapping,
            runtime_tag_expansion,
            query=query,
        )
        session_profile_update_ms = _elapsed_ms(session_update_start)
        _log_qu_trace(
            "session_context_updated",
            {
                "user_id": user_profile.user_id,
                "applied_updates": dict(session_update.applied_updates),
                "session_context": asdict(user_profile.session_context),
                "semantic_mapping": dict(session_update.semantic_mapping),
            },
        )
        active_profile_start = time.perf_counter()
        active_profile = self._build_active_profile(user_profile, query=query)
        active_profile_merge_ms = _elapsed_ms(active_profile_start)
        _log_qu_json(
            "profile_retention",
            "profile_retention_resolved",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "long_term_profile": asdict(user_profile.long_term_profile),
                "tagremoved_profile": asdict(user_profile.tagremoved_profile),
                "resolver_trace": dict(
                    getattr(
                        getattr(self.current_profile_merger, "retention_resolver", None),
                        "last_trace",
                        {},
                    )
                ),
            },
        )
        _log_qu_json(
            "active_user_profile",
            "active_user_profile_merged",
            {
                "user_id": user_profile.user_id,
                "query": query,
                "active_profile": asdict(active_profile),
                "long_term_profile": asdict(user_profile.long_term_profile),
                "tagremoved_profile": asdict(user_profile.tagremoved_profile),
                "updated_session_context": asdict(user_profile.session_context),
                "applied_updates": dict(session_update.applied_updates),
            },
        )
        self._log_current_active_profile_snapshot(
            query=query,
            user_profile=user_profile,
            active_profile=active_profile,
            stage="after_session_profile_update",
            applied_updates=dict(session_update.applied_updates),
        )
        detail = {
            "intent_extract_ms": intent_extract_ms,
            "semantic_mapping_ms": semantic_mapping_ms,
            "tag_graph_expansion_ms": tag_graph_expansion_ms,
            "session_profile_update_ms": session_profile_update_ms,
            "active_profile_merge_ms": active_profile_merge_ms,
            "total_extract_merge_inner_ms": _elapsed_ms(detail_start),
        }
        return (intent_result, session_update, active_profile), detail

    def _timed_search_plan_run(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
    ) -> tuple[Any, float]:
        start = time.perf_counter()
        result = self.search_planner.run(query, conversation_history)
        return result, _elapsed_ms(start)

    def _timed_extract_merge_current_profile(
        self,
        query: str,
        user_profile: UserProfile,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[tuple[Any, SessionProfileUpdateResult, ActiveProfile], float, dict[str, float]]:
        start = time.perf_counter()
        result, detail = self._extract_merge_current_profile_with_timing(
            query,
            user_profile,
            conversation_history=conversation_history,
        )
        return result, _elapsed_ms(start), detail

    @staticmethod
    def _recent_user_queries(conversation_history: list[dict[str, str]] | None) -> list[str]:
        if not conversation_history:
            return []
        queries: list[str] = []
        for item in conversation_history[-5:]:
            query = str(item.get("user_query", "")).strip()
            if not query and str(item.get("role", "")).strip().lower() == "user":
                query = str(item.get("content", "")).strip()
            if query:
                queries.append(query)
        return queries

    def _apply_session_profile_update(
        self,
        user_profile: UserProfile,
        intent_result: Any,
        semantic_mapping: SemanticMappingResult,
        runtime_tag_expansion: RuntimeTagExpansion | None = None,
        *,
        query: str,
    ) -> SessionProfileUpdateResult:
        del query  # Kept for backward-compatible call sites and tests.
        return SessionProfileUpdater(score_threshold=self.semantic_mapper.score_threshold).apply(
            user_profile=user_profile,
            intent_result=intent_result,
            semantic_mapping=semantic_mapping,
            runtime_tag_expansion=runtime_tag_expansion,
        )

    def _build_active_profile(self, user_profile: UserProfile, *, query: str = "") -> ActiveProfile:
        merger = getattr(self, "current_profile_merger", None) or CurrentProfileMerger()
        if query:
            return merger.merge_into_user_profile(user_profile, query=query)
        return merger.merge(user_profile)

    def _log_current_active_profile_snapshot(
        self,
        *,
        query: str,
        user_profile: UserProfile,
        stage: str,
        active_profile: ActiveProfile | None = None,
        applied_updates: dict[str, Any] | None = None,
    ) -> None:
        try:
            snapshot_active_profile = active_profile or self._build_active_profile(user_profile)
            _log_qu_json(
                "current_active_profile",
                "current_active_profile_snapshot",
                {
                    "user_id": user_profile.user_id,
                    "query": query,
                    "stage": stage,
                    "active_profile": asdict(snapshot_active_profile),
                    "long_term_profile": asdict(user_profile.long_term_profile),
                    "tagremoved_profile": asdict(user_profile.tagremoved_profile),
                    "session_context": asdict(user_profile.session_context),
                    "applied_updates": applied_updates or {},
                },
            )
        except Exception:
            logger.exception("Failed to log current active profile snapshot.")

    def _build_tag_graph_seed_items(
        self,
        intent_result: Any,
        semantic_mapping: SemanticMappingResult,
    ) -> list[MappedSemanticItem]:
        seed_items: list[MappedSemanticItem] = []
        seen: set[tuple[str, str]] = set()
        for item in semantic_mapping.mapped_items:
            if not item.matched_tag or not item.matched_category:
                continue
            if item.score is None or item.score <= self.semantic_mapper.score_threshold:
                continue
            if item.matched_category not in GRAPH_EXPANSION_SEED_CATEGORIES:
                continue
            key = (item.matched_tag, item.matched_category)
            if key in seen:
                continue
            seen.add(key)
            seed_items.append(item)

        trip_type = getattr(intent_result.entities, "trip_type", None)
        if trip_type:
            normalized_trip_type = normalize_long_term_trip_type_value(trip_type)
            key = (normalized_trip_type, "SUITABLE_FOR")
            if key not in seen:
                seen.add(key)
                seed_items.append(
                    self._build_graph_seed_item(
                        tag=normalized_trip_type,
                        category="SUITABLE_FOR",
                    )
                )
        return seed_items

    def _build_graph_seed_item(
        self,
        *,
        tag: str,
        category: str,
        target_field: str = "session_amenities",
        score: float = 1.0,
    ) -> MappedSemanticItem:
        return MappedSemanticItem(
            text=tag,
            target_field=target_field,
            category=category,
            matched_category=category,
            matched_tag=tag,
            score=score,
            priority="soft",
        )

    def _coerce_user_profile(self, payload: UserProfile | dict[str, Any]) -> UserProfile:
        if isinstance(payload, UserProfile):
            return payload

        long_term_raw = payload.get("long_term_profile", {})
        tagremoved_raw = payload.get("tagremoved_profile", {})
        session_raw = payload.get("session_context", {})
        return UserProfile(
            user_id=str(payload.get("user_id", "")),
            name=payload.get("name"),
            long_term_profile=LongTermProfile(
                nationality=long_term_raw.get("nationality"),
                age_group=long_term_raw.get("age_group"),
                current_workplace=long_term_raw.get("current_workplace"),
                is_enough=long_term_raw.get("is_enough"),
                traveler_type=self._coerce_score_map(long_term_raw.get("traveler_type")),
                long_term_trip_types=self._coerce_score_map(long_term_raw.get("long_term_trip_types")),
                long_term_budget_levels=self._coerce_score_map(long_term_raw.get("long_term_budget_levels")),
                long_term_price_range=self._coerce_price_range(long_term_raw.get("long_term_price_range", {})),
                long_term_preference_habits=self._coerce_score_map(long_term_raw.get("long_term_preference_habits")),
                long_term_hotel_types=self._coerce_score_map(long_term_raw.get("long_term_hotel_types")),
                long_term_room_views=self._coerce_score_map(long_term_raw.get("long_term_room_views")),
                long_term_amenities=self._coerce_score_map(long_term_raw.get("long_term_amenities")),
                recommendation_clicks=self._coerce_recommendation_clicks(long_term_raw.get("recommendation_clicks")),
                long_term_negative_preferences=self._coerce_negative_preferences(
                    long_term_raw.get("long_term_negative_preferences", {})
                ),
            ),
            tagremoved_profile=LongTermProfile(
                nationality=tagremoved_raw.get("nationality"),
                age_group=tagremoved_raw.get("age_group"),
                current_workplace=tagremoved_raw.get("current_workplace"),
                is_enough=tagremoved_raw.get("is_enough"),
                traveler_type=self._coerce_score_map(tagremoved_raw.get("traveler_type")),
                long_term_trip_types=self._coerce_score_map(tagremoved_raw.get("long_term_trip_types")),
                long_term_budget_levels=self._coerce_score_map(tagremoved_raw.get("long_term_budget_levels")),
                long_term_price_range=self._coerce_price_range(tagremoved_raw.get("long_term_price_range", {})),
                long_term_preference_habits=self._coerce_score_map(
                    tagremoved_raw.get("long_term_preference_habits")
                ),
                long_term_hotel_types=self._coerce_score_map(tagremoved_raw.get("long_term_hotel_types")),
                long_term_room_views=self._coerce_score_map(tagremoved_raw.get("long_term_room_views")),
                long_term_amenities=self._coerce_score_map(tagremoved_raw.get("long_term_amenities")),
                recommendation_clicks=self._coerce_recommendation_clicks(tagremoved_raw.get("recommendation_clicks")),
                long_term_negative_preferences=self._coerce_negative_preferences(
                    tagremoved_raw.get("long_term_negative_preferences", {})
                ),
            ),
            session_context=SessionContext(
                destination=session_raw.get("destination"),
                current_location=session_raw.get("current_location"),
                nearby_place=session_raw.get("nearby_place"),
                number_of_guests=session_raw.get("number_of_guests"),
                has_pet=session_raw.get("has_pet"),
                has_children=session_raw.get("has_children"),
                check_in=session_raw.get("check_in"),
                check_out=session_raw.get("check_out"),
                note_amenities=session_raw.get("note_amenities"),
                is_enough_recommend=session_raw.get("is_enough_recommend", session_raw.get("is_enough")),
                session_trip_types=self._coerce_score_map(session_raw.get("session_trip_types")),
                session_budget_levels=self._coerce_score_map(session_raw.get("session_budget_levels")),
                session_price_range=self._coerce_price_range(session_raw.get("session_price_range", {})),
                session_preference_habits=self._coerce_score_map(session_raw.get("session_preference_habits")),
                session_hotel_types=self._coerce_score_map(session_raw.get("session_hotel_types")),
                session_room_views=self._coerce_score_map(session_raw.get("session_room_views")),
                session_amenities=self._coerce_score_map(session_raw.get("session_amenities")),
                session_negative_preferences=self._coerce_negative_preferences(
                    session_raw.get("session_negative_preferences", {})
                ),
                runtime_tag_expansion=self._coerce_runtime_tag_expansion(
                    session_raw.get("runtime_tag_expansion", {})
                ),
            ),
        )

    @staticmethod
    def _coerce_price_range(payload: dict[str, Any]) -> PriceRange:
        return PriceRange(
            min=payload.get("min"),
            max=payload.get("max"),
            currency=payload.get("currency", "VND"),
        )

    @staticmethod
    def _coerce_score_map(payload: Any) -> dict[str, CountInteractionValue]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            result: dict[str, CountInteractionValue] = {}
            for key, value in payload.items():
                if isinstance(value, dict) and "count" in value and "last_interaction" in value:
                    result[str(key)] = CountInteractionValue(
                        count=int(value["count"]),
                        last_interaction=str(value["last_interaction"]),
                    )
            return result
        return {}

    @staticmethod
    def _coerce_recommendation_clicks(payload: Any) -> RecommendationClicks:
        if payload is None:
            payload = {}
        hotel_ids = payload.get("hotel", []) if isinstance(payload, dict) else []
        return RecommendationClicks(hotel=[str(item) for item in hotel_ids or []])

    @staticmethod
    def _coerce_negative_preferences(payload: dict[str, Any]) -> NegativePreferences:
        if payload is None:
            payload = {}
        return NegativePreferences(
            avoid_hotel_types=QueryUnderstandingPipeline._coerce_score_map(payload.get("avoid_hotel_types")),
            avoid_amenities=QueryUnderstandingPipeline._coerce_score_map(payload.get("avoid_amenities")),
            avoid_preference_habits=QueryUnderstandingPipeline._coerce_score_map(
                payload.get("avoid_preference_habits")
            ),
            avoid_nearby_places=QueryUnderstandingPipeline._coerce_score_map(payload.get("avoid_nearby_places")),
            avoid_locations=QueryUnderstandingPipeline._coerce_score_map(payload.get("avoid_locations")),
        )

    @staticmethod
    def _coerce_runtime_tag_expansion(payload: Any) -> RuntimeTagExpansion:
        if not isinstance(payload, dict):
            return RuntimeTagExpansion()
        return RuntimeTagExpansion(
            mapped_tags=QueryUnderstandingPipeline._coerce_runtime_tags(payload.get("mapped_tags")),
            expanded_tags=QueryUnderstandingPipeline._coerce_runtime_tags(payload.get("expanded_tags")),
            final_tags=QueryUnderstandingPipeline._coerce_runtime_tags(payload.get("final_tags")),
        )

    @staticmethod
    def _coerce_runtime_tags(payload: Any) -> list[RuntimeTag]:
        if not isinstance(payload, list):
            return []
        tags: list[RuntimeTag] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            tag = str(item.get("tag", "")).strip()
            category = str(item.get("category", "")).strip()
            if not tag or not category:
                continue
            tags.append(
                RuntimeTag(
                    tag=tag,
                    category=category,
                    score=float(item.get("score", 0.0)),
                    source=str(item.get("source", "")),
                    relation_type=item.get("relation_type"),
                    edge_score=item.get("edge_score"),
                    confidence=item.get("confidence"),
                )
            )
        return tags


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _log_qu_trace(event: str, payload: dict[str, Any]) -> None:
    try:
        logger.info(
            "query_understanding_trace %s",
            json.dumps(
                {
                    "event": event,
                    **payload,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
    except Exception:
        logger.exception("Failed to write query understanding trace log.")


def _log_qu_json(log_name: str, event: str, payload: dict[str, Any]) -> None:
    try:
        path = JSON_TRACE_FILES.get(log_name)
        if path is None:
            return
        record = {
            "event": event,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        _append_json_record(path, record)
    except Exception:
        logger.exception("Failed to write query understanding JSON trace.")


def _append_json_record(path: Path, record: dict[str, Any]) -> None:
    with _JSON_TRACE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        if path.exists() and path.stat().st_size > 0:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    records = [item for item in payload if isinstance(item, dict)]
            except json.JSONDecodeError:
                records = []
        records.append(record)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(records, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)
