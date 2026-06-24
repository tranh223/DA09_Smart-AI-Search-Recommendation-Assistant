"""
Smoke test for graph_tool.py.
Validates Neo4j config, connectivity, metadata, and basic retrieval.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent to path so we can import tools when running from smoke_test/.
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_tool import get_graph_config, run_cypher, search_graph


def _masked_config() -> Dict[str, str]:
    config = get_graph_config()
    masked = dict(config)
    if masked.get("password"):
        masked["password"] = "***"
    return masked


def test_graph_config() -> None:
    """Test graph config loads from .env."""
    print("TEST: Load Neo4j config")
    config = get_graph_config()

    assert config["url"], "GRAPH_DB_URL or NEO4J_URI is required"
    assert config["url"].startswith(("http://", "https://")), "Graph URL must use HTTP(S)"
    assert config["user"], "GRAPH_DB_USER or NEO4J_USER is required"
    assert config["password"], "GRAPH_DB_PASSWORD or NEO4J_PASSWORD is required"
    assert config["database"], "GRAPH_DB_DATABASE or NEO4J_DATABASE is required"

    print(f"OK Config: {json.dumps(_masked_config(), ensure_ascii=False)}")
    test_graph_config.config = config  # type: ignore[attr-defined]


def test_graph_connection() -> None:
    """Test direct Cypher execution against Neo4j."""
    print("\nTEST: Neo4j connection")
    rows = run_cypher("MATCH (n) RETURN count(n) AS node_count")

    assert isinstance(rows, list), "Expected list of rows"
    assert rows, "Expected one count row from Neo4j"
    assert "node_count" in rows[0], "Expected node_count column"
    assert isinstance(rows[0]["node_count"], int), "Expected node_count to be int"

    print(f"OK Connected. Node count: {rows[0]['node_count']}")
    test_graph_connection.node_count = rows[0]["node_count"]  # type: ignore[attr-defined]


def test_graph_metadata() -> None:
    """Test graph labels and relationship types are readable."""
    print("\nTEST: Neo4j metadata")
    label_rows = run_cypher("CALL db.labels() YIELD label RETURN collect(label) AS labels")
    rel_rows = run_cypher(
        "CALL db.relationshipTypes() YIELD relationshipType "
        "RETURN collect(relationshipType) AS relationship_types"
    )

    labels = label_rows[0].get("labels", []) if label_rows else []
    relationship_types = rel_rows[0].get("relationship_types", []) if rel_rows else []

    assert isinstance(labels, list), "Expected labels to be list"
    assert isinstance(relationship_types, list), "Expected relationship_types to be list"

    print(f"OK Labels ({len(labels)}): {labels[:10]}")
    print(f"OK Relationship types ({len(relationship_types)}): {relationship_types[:10]}")
    test_graph_metadata.metadata = {"labels": labels, "relationship_types": relationship_types}  # type: ignore[attr-defined]


def test_search_graph_returns_list() -> None:
    """Test search_graph returns a result list."""
    print("\nTEST: search_graph returns list")
    results = search_graph("", top_k=3)

    assert isinstance(results, list), "Expected search_graph to return list"
    assert len(results) <= 3, "Expected search_graph to respect top_k"

    print(f"OK Returned {len(results)} result(s)")
    test_search_graph_returns_list.results = results  # type: ignore[attr-defined]


def test_search_graph_result_structure() -> None:
    """Test result shape when the graph has retrievable nodes."""
    print("\nTEST: search_graph result structure")
    results = getattr(test_search_graph_returns_list, "results", [])
    if not results:
        print("SKIP: Graph search returned no rows")
        return

    first = results[0]
    required_fields = [
        "id",
        "labels",
        "properties",
        "matched_properties",
        "score",
        "relationships",
    ]
    for field in required_fields:
        assert field in first, f"Missing required result field: {field}"

    assert isinstance(first["labels"], list), "Expected labels to be list"
    assert isinstance(first["properties"], dict), "Expected properties to be dict"
    assert isinstance(first["relationships"], list), "Expected relationships to be list"

    print(f"OK First result labels: {first['labels']}")


def test_search_graph_top_k_zero() -> None:
    """Test zero limit does not query and returns empty list."""
    print("\nTEST: search_graph top_k=0")
    results = search_graph("anything", top_k=0)

    assert results == [], "Expected empty list for top_k=0"
    print("OK top_k=0 returns []")


def run_smoke_tests() -> Dict[str, Any]:
    """Run all graph smoke tests and return graph metadata."""
    print("=" * 60)
    print("SMOKE TEST: graph_tool")
    print("=" * 60)

    test_graph_config()
    test_graph_connection()
    test_graph_metadata()
    test_search_graph_returns_list()
    test_search_graph_result_structure()
    test_search_graph_top_k_zero()

    config = test_graph_config.config  # type: ignore[attr-defined]
    node_count = test_graph_connection.node_count  # type: ignore[attr-defined]
    metadata = test_graph_metadata.metadata  # type: ignore[attr-defined]

    print("\n" + "=" * 60)
    print("OK ALL GRAPH TESTS PASSED")
    print("=" * 60)

    return {
        "graph_source": _masked_config(),
        "node_count": node_count,
        "labels": metadata["labels"],
        "relationship_types": metadata["relationship_types"],
        "database": config["database"],
    }


def main() -> int:
    """Run graph smoke tests."""
    try:
        run_smoke_tests()
        return 0
    except AssertionError as exc:
        print(f"\nTEST FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\nERROR: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
