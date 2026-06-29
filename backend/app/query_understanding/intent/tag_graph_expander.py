from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import asdict
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    def load_dotenv() -> bool:
        return False

try:
    from neo4j import GraphDatabase
    import neo4j.exceptions as neo4j_exc
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    GraphDatabase = None
    neo4j_exc = None

from query_understanding.config.settings import (
    EXPANSION_WEIGHT,
    MAX_PER_CATEGORY,
    MIN_CONFIDENCE,
    MIN_EDGE_SCORE,
    MIN_MAPPING_SCORE,
)
from query_understanding.models.intent import MappedSemanticItem
from query_understanding.models.planner import RuntimeTag, RuntimeTagExpansion

logger = logging.getLogger(__name__)


def _neo4j_exception_type(name: str) -> type[BaseException]:
    if neo4j_exc is None:
        return _UnavailableNeo4jException
    return getattr(neo4j_exc, name, _UnavailableNeo4jException)


class _UnavailableNeo4jException(Exception):
    pass


NON_TRANSIENT_GRAPH_ERRORS = tuple(
    _neo4j_exception_type(name)
    for name in (
        "AuthConfigurationError",
        "AuthError",
        "ClientError",
        "ConfigurationError",
        "CypherSyntaxError",
        "CypherTypeError",
    )
)
TRANSIENT_GRAPH_ERRORS = tuple(
    _neo4j_exception_type(name)
    for name in (
        "TransientError",
        "ConnectionAcquisitionTimeoutError",
        "ConnectionPoolError",
        "ServiceUnavailable",
        "SessionExpired",
    )
)
DRIVER_ERROR_TYPE = _neo4j_exception_type("DriverError")


class TagGraphExpansionService:
    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        min_mapping_score: float = MIN_MAPPING_SCORE,
        min_edge_score: float = MIN_EDGE_SCORE,
        min_confidence: float = MIN_CONFIDENCE,
        max_per_category: int = MAX_PER_CATEGORY,
        expansion_weight: float = EXPANSION_WEIGHT,
        driver: Any | None = None,
    ) -> None:
        load_dotenv()
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.min_mapping_score = min_mapping_score
        self.min_edge_score = min_edge_score
        self.min_confidence = min_confidence
        self.max_per_category = max_per_category
        self.expansion_weight = expansion_weight
        self._driver = driver
        self._validated = driver is not None
        self.last_trace: dict[str, Any] = {}

    def expand_mapping(self, mapped_items: list[MappedSemanticItem]) -> RuntimeTagExpansion:
        accepted_items = [
            item
            for item in mapped_items
            if item.matched_tag
            and item.matched_category
            and item.score is not None
            and item.score > self.min_mapping_score
        ]
        mapped_tags = [
            RuntimeTag(
                tag=str(item.matched_tag),
                category=str(item.matched_category),
                score=1.0,
                source="semantic_mapper",
            )
            for item in accepted_items
        ]
        if not mapped_tags:
            result = RuntimeTagExpansion()
            self.last_trace = self._build_trace(
                status="empty",
                mapped_tags=[],
                expanded_tags=[],
                final_tags=[],
            )
            return result

        try:
            expanded_candidates = self._expand_tags(mapped_tags)
        except Exception as exc:
            if not self._is_transient_graph_error(exc):
                self._log_graph_error("tag_graph_expansion_failed", exc, mapped_tags, transient=False)
                raise
            result = RuntimeTagExpansion(
                mapped_tags=mapped_tags,
                expanded_tags=[],
                final_tags=self._deduplicate_final_tags(mapped_tags, []),
            )
            self._log_graph_error("tag_graph_expansion_transient_error", exc, mapped_tags, transient=True)
            self.last_trace = self._build_trace(
                status="graph_transient_error",
                mapped_tags=mapped_tags,
                expanded_tags=[],
                final_tags=result.final_tags,
                error=exc,
            )
            return result

        expanded_candidates = self._deduplicate_expanded_candidates(mapped_tags, expanded_candidates)
        expanded_tags = self._apply_category_diversity(expanded_candidates)
        final_tags = self._deduplicate_final_tags(mapped_tags, expanded_tags)
        result = RuntimeTagExpansion(
            mapped_tags=mapped_tags,
            expanded_tags=expanded_tags,
            final_tags=final_tags,
        )
        self.last_trace = self._build_trace(
            status="ok",
            mapped_tags=mapped_tags,
            expanded_tags=expanded_tags,
            final_tags=final_tags,
        )
        return result

    def _expand_tag(self, mapped_tag: RuntimeTag) -> list[RuntimeTag]:
        return self._expand_tags([mapped_tag])

    def _expand_tags(self, mapped_tags: list[RuntimeTag]) -> list[RuntimeTag]:
        if not mapped_tags:
            return []
        self._ensure_ready()
        query = """
        UNWIND $tags AS mapped_tag
        MATCH (src:Tag {name: mapped_tag.tag, category: mapped_tag.category})
        MATCH (src)-[r:RELATED_TO]->(dst:Tag)
        WHERE r.score >= $min_edge_score
          AND r.confidence >= $min_confidence
        RETURN
          mapped_tag.tag AS source_tag,
          mapped_tag.category AS source_category,
          dst.name AS tag_name,
          dst.category AS category,
          r.score AS score,
          r.confidence AS confidence
        ORDER BY r.score DESC
        """
        records = self._run_query(
            query,
            {
                "tags": [asdict(tag) for tag in mapped_tags],
                "min_edge_score": self.min_edge_score,
                "min_confidence": self.min_confidence,
            },
        )
        expanded: list[RuntimeTag] = []
        for record in records:
            edge_score = float(_record_value(record, "score"))
            confidence = float(_record_value(record, "confidence"))
            expanded.append(
                RuntimeTag(
                    tag=str(_record_value(record, "tag_name")),
                    category=str(_record_value(record, "category")),
                    score=edge_score * self.expansion_weight,
                    source="graph_expansion",
                    relation_type="RELATED_TO",
                    edge_score=edge_score,
                    confidence=confidence,
                )
            )
        return expanded

    def _apply_category_diversity(self, candidates: list[RuntimeTag]) -> list[RuntimeTag]:
        sorted_candidates = sorted(candidates, key=lambda item: item.score, reverse=True)
        counts_by_category: dict[str, int] = defaultdict(int)
        selected: list[RuntimeTag] = []
        for candidate in sorted_candidates:
            if counts_by_category[candidate.category] >= self.max_per_category:
                continue
            selected.append(candidate)
            counts_by_category[candidate.category] += 1
        return selected

    @staticmethod
    def _deduplicate_expanded_candidates(
        mapped_tags: list[RuntimeTag],
        expanded_candidates: list[RuntimeTag],
    ) -> list[RuntimeTag]:
        seen = {(tag.tag, tag.category) for tag in mapped_tags}
        selected: list[RuntimeTag] = []
        for candidate in sorted(expanded_candidates, key=lambda item: item.score, reverse=True):
            key = (candidate.tag, candidate.category)
            if key in seen:
                continue
            seen.add(key)
            selected.append(candidate)
        return selected

    @staticmethod
    def _deduplicate_final_tags(mapped_tags: list[RuntimeTag], expanded_tags: list[RuntimeTag]) -> list[RuntimeTag]:
        final: list[RuntimeTag] = []
        seen: set[tuple[str, str]] = set()
        for tag in mapped_tags + expanded_tags:
            key = (tag.tag, tag.category)
            if key in seen:
                continue
            seen.add(key)
            final.append(tag)
        return final

    def _ensure_ready(self) -> None:
        if self._driver is None:
            if GraphDatabase is None:
                raise RuntimeError("neo4j package is required for tag graph expansion.")
            if not self.password:
                raise RuntimeError("NEO4J_PASSWORD is required for tag graph expansion.")
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        if not self._validated:
            self.validate_schema()
            self._validated = True

    def validate_schema(self) -> None:
        records = self._run_query(
            """
            MATCH (src:Tag)-[r:RELATED_TO]->(dst:Tag)
            RETURN
              count(r) AS edge_count,
              count(src.name) AS source_name_count,
              count(src.category) AS source_category_count,
              count(dst.name) AS target_name_count,
              count(dst.category) AS target_category_count,
              count(r.score) AS score_count,
              count(r.confidence) AS confidence_count
            """,
            {},
        )
        if not records:
            raise RuntimeError("Neo4j tag graph validation returned no records.")
        row = records[0]
        edge_count = int(_record_value(row, "edge_count"))
        if edge_count <= 0:
            raise RuntimeError("Neo4j tag graph is empty: expected (:Tag)-[:RELATED_TO]->(:Tag).")
        required_counts = {
            "source_name_count": int(_record_value(row, "source_name_count")),
            "source_category_count": int(_record_value(row, "source_category_count")),
            "target_name_count": int(_record_value(row, "target_name_count")),
            "target_category_count": int(_record_value(row, "target_category_count")),
            "score_count": int(_record_value(row, "score_count")),
            "confidence_count": int(_record_value(row, "confidence_count")),
        }
        missing = [key for key, count in required_counts.items() if count != edge_count]
        if missing:
            raise RuntimeError(
                "Neo4j tag graph is missing required Tag/RELATED_TO properties: "
                + ", ".join(missing)
            )

    def _run_query(self, query: str, parameters: dict[str, Any]) -> list[Any]:
        if self._driver is None:
            raise RuntimeError("Neo4j driver is not initialized.")
        with self._driver.session(database=self.database) as session:
            return list(session.run(query, parameters))

    def _build_trace(
        self,
        *,
        status: str,
        mapped_tags: list[RuntimeTag],
        expanded_tags: list[RuntimeTag],
        final_tags: list[RuntimeTag],
        error: Exception | None = None,
    ) -> dict[str, Any]:
        trace: dict[str, Any] = {
            "status": status,
            "min_mapping_score": self.min_mapping_score,
            "min_edge_score": self.min_edge_score,
            "min_confidence": self.min_confidence,
            "max_per_category": self.max_per_category,
            "expansion_weight": self.expansion_weight,
            "mapped_tags": [asdict(tag) for tag in mapped_tags],
            "expanded_tags": [asdict(tag) for tag in expanded_tags],
            "final_tags": [asdict(tag) for tag in final_tags],
        }
        if error is not None:
            trace["error"] = str(error)
            trace["error_type"] = type(error).__name__
        return trace

    @staticmethod
    def _is_transient_graph_error(exc: Exception) -> bool:
        if isinstance(exc, NON_TRANSIENT_GRAPH_ERRORS):
            return False
        if isinstance(exc, TRANSIENT_GRAPH_ERRORS):
            return True
        if isinstance(exc, DRIVER_ERROR_TYPE):
            return _looks_like_transient_driver_error(exc)
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        return False

    def _log_graph_error(
        self,
        event: str,
        exc: Exception,
        mapped_tags: list[RuntimeTag],
        *,
        transient: bool,
    ) -> None:
        extra = {
            "event": event,
            "transient": transient,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "mapped_tag_count": len(mapped_tags),
            "uri": self.uri,
            "database": self.database,
            "min_mapping_score": self.min_mapping_score,
            "min_edge_score": self.min_edge_score,
            "min_confidence": self.min_confidence,
            "max_per_category": self.max_per_category,
            "expansion_weight": self.expansion_weight,
        }
        if transient:
            logger.warning("Neo4j tag graph expansion transient error; falling back to mapped tags.", extra=extra)
            return
        logger.error("Neo4j tag graph expansion failed.", extra=extra)


def _record_value(record: Any, key: str) -> Any:
    if isinstance(record, dict):
        return record[key]
    return record[key]


def _looks_like_transient_driver_error(exc: Exception) -> bool:
    message = str(exc).lower()
    transient_markers = (
        "connection",
        "connect",
        "network",
        "temporar",
        "timeout",
        "timed out",
        "unavailable",
        "failed to read",
        "failed to write",
        "connection reset",
        "connection refused",
        "connection closed",
    )
    return any(marker in message for marker in transient_markers)
