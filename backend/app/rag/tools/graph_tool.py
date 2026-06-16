"""
Graph Tool
Retrieves relevant nodes from a Neo4j knowledge graph.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests
from dotenv import load_dotenv

from utils.logger import get_logger
from utils.langsmith_tracer import tracer

load_dotenv()

logger = get_logger(__name__)

DEFAULT_GRAPH_URL = "http://34.158.39.31:7474"
DEFAULT_DATABASE = "neo4j"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_RELATIONSHIP_LIMIT = 5

_session: Optional[requests.Session] = None


def _get_env_value(names: List[str], default: str = "") -> str:
    """Read the first configured env value, tolerating quotes and spaces."""
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        value = value.strip().strip('"\'')
        if value:
            return value
    return default


def _normalize_graph_url(url: str) -> str:
    """Convert browser/Bolt-ish inputs into the Neo4j HTTP base URL."""
    url = (url or DEFAULT_GRAPH_URL).strip().strip('"\'')
    if not url:
        url = DEFAULT_GRAPH_URL
    if "://" not in url:
        url = f"http://{url}"

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.endswith("/browser"):
        path = path[: -len("/browser")]

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")


def get_graph_config() -> Dict[str, str]:
    """Return Neo4j connection settings sourced from .env."""
    return {
        "url": _normalize_graph_url(
            _get_env_value(["NEO4J_URI", "NEO4J_URL", "GRAPH_DB_URL"], DEFAULT_GRAPH_URL)
        ),
        "user": _get_env_value(["NEO4J_USER", "NEO4J_USERNAME", "GRAPH_DB_USER", "GRAPH_DB_USERNAME"]),
        "password": _get_env_value(["NEO4J_PASSWORD", "GRAPH_DB_PASSWORD"]),
        "database": _get_env_value(["NEO4J_DATABASE", "GRAPH_DB_DATABASE"], DEFAULT_DATABASE),
    }


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def run_cypher(
    statement: str,
    parameters: Optional[Dict[str, Any]] = None,
    database: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Execute a Cypher query through Neo4j's HTTP transaction endpoint.

    Returns:
        List of row dictionaries keyed by returned column names.
    """
    config = get_graph_config()
    if not config["user"] or not config["password"]:
        raise ValueError(
            "Neo4j credentials are not set. Add NEO4J_USER and NEO4J_PASSWORD "
            "or GRAPH_DB_USER and GRAPH_DB_PASSWORD to .env."
        )

    db_name = database or config["database"]
    endpoint = f"{config['url']}/db/{db_name}/tx/commit"
    payload = {
        "statements": [
            {
                "statement": statement,
                "parameters": parameters or {},
                "resultDataContents": ["row"],
            }
        ]
    }

    response = _get_session().post(
        endpoint,
        json=payload,
        auth=(config["user"], config["password"]),
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    body = response.json()
    errors = body.get("errors") or []
    if errors:
        messages = "; ".join(error.get("message", str(error)) for error in errors)
        raise RuntimeError(f"Neo4j query failed: {messages}")

    result = (body.get("results") or [{}])[0]
    columns = result.get("columns") or []
    rows = []
    for item in result.get("data") or []:
        row_values = item.get("row") or []
        rows.append(dict(zip(columns, row_values)))
    return rows


def _query_terms(query: str) -> List[str]:
    terms = []
    for term in query.lower().split():
        cleaned = term.strip(".,;:!?()[]{}\"'")
        if len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
    return terms


def _build_search_cypher(query: str) -> str:
    if not query.strip():
        return """
        MATCH (n)
        WHERE none(label IN labels(n) WHERE toLower(label) IN ['user', 'profile', 'userprofile'])
          AND ($hotel_id IS NULL OR n.hotel_id = $hotel_id OR n.id = $hotel_id)
        CALL {
            WITH n
            OPTIONAL MATCH (n)-[r]-(m)
            WHERE m IS NULL OR none(label IN labels(m) WHERE toLower(label) IN ['user', 'profile', 'userprofile'])
            WITH n, r, m
            LIMIT $relationship_limit
            RETURN collect(
                CASE WHEN r IS NULL THEN null ELSE {
                    type: type(r),
                    direction: CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END,
                    neighbor_id: id(m),
                    neighbor_labels: labels(m),
                    neighbor_properties: properties(m)
                } END
            ) AS relationship_rows
        }
        RETURN {
            id: id(n),
            labels: labels(n),
            properties: properties(n),
            matched_properties: [],
            score: 0,
            relationships: [rel IN relationship_rows WHERE rel IS NOT NULL]
        } AS result
        LIMIT $limit
        """

    return """
    MATCH (n)
    WHERE none(label IN labels(n) WHERE toLower(label) IN ['user', 'profile', 'userprofile'])
      AND ($hotel_id IS NULL OR n.hotel_id = $hotel_id OR n.id = $hotel_id)
    WITH n, properties(n) AS props
    WITH n, props,
         [key IN keys(props)
          WHERE any(term IN $terms WHERE toLower(toString(props[key])) CONTAINS term)
             OR toLower(toString(props[key])) CONTAINS $query] AS matched_keys
    WHERE size(matched_keys) > 0
    WITH n, props, matched_keys,
         size(matched_keys) +
         reduce(score = 0, key IN matched_keys |
             score + CASE WHEN toLower(toString(props[key])) CONTAINS $query THEN 3 ELSE 1 END
         ) AS score
    CALL {
        WITH n
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE m IS NULL OR none(label IN labels(m) WHERE toLower(label) IN ['user', 'profile', 'userprofile'])
        WITH n, r, m
        LIMIT $relationship_limit
        RETURN collect(
            CASE WHEN r IS NULL THEN null ELSE {
                type: type(r),
                direction: CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END,
                neighbor_id: id(m),
                neighbor_labels: labels(m),
                neighbor_properties: properties(m)
            } END
        ) AS relationship_rows
    }
    RETURN {
        id: id(n),
        labels: labels(n),
        properties: props,
        matched_properties: matched_keys,
        score: score,
        relationships: [rel IN relationship_rows WHERE rel IS NOT NULL]
    } AS result
    ORDER BY score DESC
    LIMIT $limit
    """


@tracer.trace("tool_graph_search")
def search_graph(
    query: str,
    top_k: int = 5,
    hotel_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search the Neo4j knowledge graph for nodes whose properties match query text.

    Args:
        query: Search query.
        top_k: Number of results.

    Returns:
        List of matching graph records. Each record includes node labels,
        properties, matched property names, score, and nearby relationships.
    """
    safe_limit = 5 if top_k is None else max(int(top_k), 0)
    if safe_limit == 0:
        return []

    query_text = (query or "").strip().lower()
    params = {
        "query": query_text,
        "terms": _query_terms(query_text),
        "limit": safe_limit,
        "relationship_limit": DEFAULT_RELATIONSHIP_LIMIT,
        "hotel_id": hotel_id,
    }

    try:
        rows = run_cypher(_build_search_cypher(query_text), params)
        return [row["result"] for row in rows if row.get("result") is not None]
    except Exception as exc:
        logger.error(f"Error searching Neo4j graph: {exc}")
        return []
