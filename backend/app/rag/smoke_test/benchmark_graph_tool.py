"""
Focused benchmark for graph_tool.py.
Runs graph smoke tests first, then measures Neo4j query and retrieval latency.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add parent to path so we can import tools when running from smoke_test/.
sys.path.insert(0, str(Path(__file__).parent.parent))

from smoke_test.test_graph_tool import run_smoke_tests
from tools.graph_tool import run_cypher, search_graph


BENCHMARK_SCENARIOS = [
    # ---- Baselines (slightly tightened) ----
    {
        "id": "CONN_001",
        "name": "Count all nodes",
        "operation": "cypher",
        "category": "baseline",
        "statement": "MATCH (n) RETURN count(n) AS count",
        "iterations": 5,
        "expected_metric": "latency < 800ms",
    },
    {
        "id": "CONN_002",
        "name": "Count all relationships",
        "operation": "cypher",
        "category": "baseline",
        "statement": "MATCH ()-[r]-() RETURN count(r) AS count",
        "iterations": 5,
        "expected_metric": "latency < 900ms",
    },
    {
        "id": "META_001",
        "name": "List labels",
        "operation": "cypher",
        "category": "metadata",
        "statement": "CALL db.labels() YIELD label RETURN collect(label) AS labels",
        "iterations": 8,
        "expected_metric": "latency < 400ms",
    },
    {
        "id": "META_002",
        "name": "Label distribution",
        "operation": "cypher",
        "category": "metadata",
        "statement": """
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label, count(*) AS count
        ORDER BY count DESC
        """,
        "iterations": 4,
        "expected_metric": "latency < 1200ms",
    },
    {
        "id": "META_003",
        "name": "Relationship distribution",
        "operation": "cypher",
        "category": "metadata",
        "statement": """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship_type, count(*) AS count
        ORDER BY count DESC
        """,
        "iterations": 4,
        "expected_metric": "latency < 1600ms",
    },

    # ---- Retrieval / Search (more tokens + bigger top_k) ----
    {
        "id": "SEARCH_001",
        "name": "Get first 5 graph nodes (empty query)",
        "operation": "search",
        "category": "retrieval",
        "query": "",
        "top_k": 5,
        "iterations": 10,
        "expected_metric": "latency < 1200ms",
    },
    {
        "id": "SEARCH_002",
        "name": "Search Da Nang (bigger top_k)",
        "operation": "search",
        "category": "retrieval",
        "query": "Da Nang",
        "top_k": 20,
        "iterations": 7,
        "expected_metric": "latency < 2000ms",
    },
    {
        "id": "SEARCH_003",
        "name": "Search hotel (bigger top_k + more iterations)",
        "operation": "search",
        "category": "retrieval",
        "query": "hotel room price",
        "top_k": 25,
        "iterations": 6,
        "expected_metric": "latency < 2500ms",
    },
    {
        "id": "SEARCH_004",
        "name": "Search restaurant (diacritics + multi-term)",
        "operation": "search",
        "category": "retrieval",
        "query": "nhà hàng ẩm thực",
        "top_k": 20,
        "iterations": 6,
        "expected_metric": "latency < 2800ms",
    },
    {
        "id": "SEARCH_005",
        "name": "Search Vietnamese city + larger top_k",
        "operation": "search",
        "category": "retrieval",
        "query": "Đà Nẵng khách sạn gần biển hồ bơi wifi",
        "top_k": 40,
        "iterations": 4,
        "expected_metric": "latency < 3500ms",
    },
    {
        "id": "SEARCH_006",
        "name": "Search amenities and room terms (very large top_k)",
        "operation": "search",
        "category": "retrieval",
        "query": "wifi pool breakfast room family sea view",
        "top_k": 50,
        "iterations": 3,
        "expected_metric": "latency < 4200ms",
    },
    {
        "id": "SEARCH_007",
        "name": "Search whitespace/odd spacing (term extraction edge)",
        "operation": "search",
        "category": "edge",
        "query": "   wifi   pool    ",
        "top_k": 30,
        "iterations": 6,
        "expected_metric": "latency < 3000ms",
    },
    {
        "id": "SEARCH_008",
        "name": "Search multi-lingual mixed tokens",
        "operation": "search",
        "category": "retrieval",
        "query": "beach gần biển pool hồ bơi breakfast bữa sáng",
        "top_k": 35,
        "iterations": 4,
        "expected_metric": "latency < 3800ms",
    },

    # ---- Traversal / Cypher (deeper paths + heavier aggregations) ----
    {
        "id": "TRAVERSAL_001",
        "name": "City to hotels to rooms aggregation (more iterations)",
        "operation": "cypher",
        "category": "traversal",
        "statement": """
        MATCH (c:City)<-[:LOCATED_IN]-(h:Hotel)
        OPTIONAL MATCH (h)-[:HAS_ROOM]->(room:Room)
        RETURN c.name AS city,
               count(DISTINCT h) AS hotel_count,
               count(room) AS room_count
        ORDER BY hotel_count DESC, room_count DESC
        LIMIT 30
        """,
        "iterations": 5,
        "expected_metric": "latency < 2200ms",
    },
    {
        "id": "TRAVERSAL_002",
        "name": "City to hotels to activities expansion (more expensive projection)",
        "operation": "cypher",
        "category": "traversal",
        "statement": """
        MATCH (c:City)<-[:LOCATED_IN]-(h:Hotel)
        OPTIONAL MATCH (h)-[:OFFERS_ACTIVITY]->(activity:Activity)
        WITH
          c.name AS city,
          h,
          activity
        RETURN
          city,
          count(DISTINCT h) AS hotel_count,
          count(DISTINCT activity) AS activity_count,
          collect(DISTINCT activity.name)[0..15] AS sample_activities,
          avg(CASE WHEN toFloat(activity.price) IS NULL THEN 0 ELSE toFloat(activity.price) END) AS avg_activity_price
        ORDER BY activity_count DESC, hotel_count DESC
        LIMIT 25
        """,
        "iterations": 4,
        "expected_metric": "latency < 2600ms",
    },
    {
        "id": "TRAVERSAL_003",
        "name": "Hotel neighborhood and tag fanout (reduced to avoid timeouts)",
        "operation": "cypher",
        "category": "traversal",
        "statement": """
        MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:NEAR]->(place:Place)
        OPTIONAL MATCH (h)-[:HAS_TAG]->(tag:Tag)
        WITH
          h.name AS hotel,
          h.city AS city,
          place,
          tag
        RETURN
          hotel,
          city,
          count(DISTINCT place) AS nearby_places,
          count(DISTINCT tag) AS tags,
          collect(DISTINCT tag.name)[0..6] AS sample_tags
        ORDER BY nearby_places DESC, tags DESC
        LIMIT 20
        """,
        "iterations": 2,
        "expected_metric": "latency < 6000ms",
    },
    {
        "id": "TRAVERSAL_004",
        "name": "Two-hop path expansion from hotels (less expansion to avoid timeouts)",
        "operation": "cypher",
        "category": "traversal",
        "statement": """
        MATCH path = (h:Hotel)-[*1..2]-(neighbor)
        RETURN labels(neighbor) AS neighbor_labels,
               count(path) AS path_count
        ORDER BY path_count DESC
        LIMIT 15
        """,
        "iterations": 2,
        "expected_metric": "latency < 7000ms",
    },

    # ---- Analytics (heavier compute + tighter thresholds) ----
    {
        "id": "ANALYTICS_001",
        "name": "Hotel score and price analytics by city (tighter + more iterations)",
        "operation": "cypher",
        "category": "analytics",
        "statement": """
        MATCH (c:City)<-[:LOCATED_IN]-(h:Hotel)-[:HAS_ROOM]->(room:Room)
        OPTIONAL MATCH (h)-[:HAS_TAG]->(t:Tag)
        WITH c.name AS city,
             count(DISTINCT h) AS hotels,
             avg(toFloat(h.review_score)) AS avg_review_score,
             avg(toFloat(room.price)) AS avg_room_price,
             min(toFloat(room.price)) AS min_room_price,
             max(toFloat(room.price)) AS max_room_price,
             count(DISTINCT t) AS distinct_tags
        RETURN city, hotels, avg_review_score, avg_room_price, min_room_price, max_room_price, distinct_tags
        ORDER BY hotels DESC
        LIMIT 25
        """,
        "iterations": 3,
        "expected_metric": "latency < 3800ms",
    },
    {
        "id": "ANALYTICS_002",
        "name": "Top connected nodes by relationship fanout (tighter + heavier projection)",
        "operation": "cypher",
        "category": "analytics",
        "statement": """
        MATCH (n)-[r]-()
        WITH id(n) AS node_id,
             labels(n) AS labels,
             properties(n) AS properties,
             count(r) AS degree,
             collect(DISTINCT type(r))[0..6] AS relationship_types
        RETURN node_id, labels, properties, degree, relationship_types
        ORDER BY degree DESC
        LIMIT 40
        """,
        "iterations": 3,
        "expected_metric": "latency < 4200ms",
    },
    {
        "id": "ANALYTICS_003",
        "name": "Relational density per city (fanout + aggregations)",
        "operation": "cypher",
        "category": "analytics",
        "statement": """
        MATCH (c:City)<-[:LOCATED_IN]-(h:Hotel)
        OPTIONAL MATCH (h)-[:NEAR]->(p:Place)
        OPTIONAL MATCH (h)-[:OFFERS_ACTIVITY]->(a:Activity)
        WITH c.name AS city,
             count(DISTINCT h) AS hotel_count,
             count(DISTINCT p) AS place_count,
             count(DISTINCT a) AS activity_count
        RETURN city,
               hotel_count,
               place_count,
               activity_count,
               (toFloat(place_count) + toFloat(activity_count)) / CASE WHEN hotel_count = 0 THEN 1 ELSE toFloat(hotel_count) END AS density_score
        ORDER BY density_score DESC
        LIMIT 20
        """,
        "iterations": 3,
        "expected_metric": "latency < 3500ms",
    },

    # ---- Mixed workload / stress ----
    {
        "id": "MIXED_001",
        "name": "Mixed retrieval workload (more queries + bigger top_k)",
        "operation": "mixed_search",
        "category": "stress",
        "queries": [
            "Da Nang",
            "hotel",
            "restaurant",
            "wifi pool breakfast",
            "Đà Nẵng khách sạn gần biển",
            "room family",
            "activity",
            "near beach",
            "hồ bơi",
            "bữa sáng",
        ],
        "top_k": 20,
        "iterations": 4,
        "expected_metric": "latency < 4200ms",
    },
    {
        "id": "MIXED_002",
        "name": "Mixed retrieval workload (hard multi-term tokens)",
        "operation": "mixed_search",
        "category": "stress",
        "queries": [
            "wifi pool breakfast room sea view",
            "gần biển khách sạn wifi miễn phí",
            "nhà hàng hải sản",
            "family room lớn",
            "activity thể thao biển",
        ],
        "top_k": 35,
        "iterations": 3,
        "expected_metric": "latency < 5200ms",
    },

    # ---- Edge ----
    {
        "id": "EDGE_001",
        "name": "Search top_k zero",
        "operation": "search",
        "category": "edge",
        "query": "anything",
        "top_k": 0,
        "iterations": 80,
        "expected_metric": "latency < 0.8ms",
    },
]


def _result_preview(result: Any) -> Any:
    if isinstance(result, list):
        if result and isinstance(result[0], dict) and "query" in result[0] and "results" in result[0]:
            return {
                "count": len(result),
                "queries": [
                    {
                        "query": item["query"],
                        "result_count": len(item.get("results", [])),
                        "first_labels": (
                            item.get("results", [{}])[0].get("labels")
                            if item.get("results")
                            else None
                        ),
                    }
                    for item in result
                ],
            }
        return {
            "count": len(result),
            "first": result[0] if result else None,
        }
    return result


def _check_threshold(scenario: Dict[str, Any], latency_ms: float) -> bool:
    expected = scenario.get("expected_metric", "")
    if "< " not in expected or "ms" not in expected:
        return True

    try:
        threshold_ms = float(expected.split("< ", 1)[1].split("ms", 1)[0])
    except ValueError:
        return True

    return latency_ms < threshold_ms


class GraphToolBenchmark:
    def __init__(self, graph_info: Dict[str, Any]):
        self.graph_info = graph_info
        self.results: List[Dict[str, Any]] = []

    def execute_operation(self, scenario: Dict[str, Any]) -> Tuple[float, int, Any]:
        """Execute a benchmark operation and return average latency, iterations, result."""
        operation = scenario["operation"]
        iterations = scenario.get("iterations", 1)

        start = time.time()
        result = None
        for _ in range(iterations):
            if operation == "cypher":
                result = run_cypher(
                    scenario["statement"],
                    parameters=scenario.get("parameters"),
                )
            elif operation == "search":
                result = search_graph(
                    scenario.get("query", ""),
                    top_k=scenario.get("top_k", 5),
                )
            elif operation == "mixed_search":
                result = []
                for query in scenario.get("queries", []):
                    result.append(
                        {
                            "query": query,
                            "results": search_graph(
                                query,
                                top_k=scenario.get("top_k", 5),
                            ),
                        }
                    )
            else:
                raise ValueError(f"Unsupported operation: {operation}")

        elapsed = time.time() - start
        return elapsed / iterations, iterations, result

    def run_benchmark(self) -> None:
        """Run all graph benchmark scenarios."""
        print("\n" + "=" * 90)
        print("GRAPH TOOL BENCHMARK")
        print("=" * 90)
        print(f"Graph source: {json.dumps(self.graph_info['graph_source'], ensure_ascii=False)}")
        print(f"Node count: {self.graph_info['node_count']}")
        print(f"Running {len(BENCHMARK_SCENARIOS)} scenarios...\n")

        for index, scenario in enumerate(BENCHMARK_SCENARIOS, 1):
            scenario_id = scenario["id"]
            name = scenario["name"]
            expected = scenario.get("expected_metric", "N/A")

            print(f"[{index}/{len(BENCHMARK_SCENARIOS)}] {scenario_id}: {name}")

            try:
                latency, iterations, result = self.execute_operation(scenario)
                latency_ms = latency * 1000
                preview = _result_preview(result)
                preview_text = json.dumps(preview, ensure_ascii=True, default=str)[:300]
                status = "PASS" if _check_threshold(scenario, latency_ms) else "SLOW"

                print(f"  Latency: {latency_ms:.2f}ms (avg over {iterations} iterations)")
                print(f"  Result: {preview_text}")
                print(f"  Expected: {expected}")
                print(f"  {status}\n")

                self.results.append(
                    {
                        "scenario_id": scenario_id,
                        "name": name,
                        "operation": scenario["operation"],
                        "category": scenario.get("category"),
                        "query": scenario.get("query"),
                        "queries": scenario.get("queries"),
                        "top_k": scenario.get("top_k"),
                        "iterations": iterations,
                        "latency_ms": latency_ms,
                        "latency_total_ms": latency_ms * iterations,
                        "result_preview": preview,
                        "expected_metric": expected,
                        "status": status,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as exc:
                print(f"  ERROR: {exc}\n")
                self.results.append(
                    {
                        "scenario_id": scenario_id,
                        "name": name,
                        "operation": scenario["operation"],
                        "category": scenario.get("category"),
                        "latency_ms": None,
                        "error": str(exc),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    def print_summary(self) -> None:
        """Print benchmark summary."""
        if not self.results:
            print("No benchmark results to display.")
            return

        latencies = [r["latency_ms"] for r in self.results if r.get("latency_ms") is not None]

        print("\n" + "=" * 90)
        print("GRAPH BENCHMARK SUMMARY")
        print("=" * 90)
        print(f"\nTotal Scenarios: {len(self.results)}")
        print(f"Successful: {len(latencies)}")
        print(f"Failed: {len(self.results) - len(latencies)}")

        if not latencies:
            print("\nNo valid latency measurements.")
            return

        sorted_latencies = sorted(latencies)
        p95_index = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
        p99_index = min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)

        print("\n--- LATENCY STATISTICS (ms) ---")
        print(f"  Average:     {sum(latencies) / len(latencies):.2f}ms")
        print(f"  Min:         {min(latencies):.2f}ms")
        print(f"  Max:         {max(latencies):.2f}ms")
        print(f"  Median:      {sorted_latencies[len(sorted_latencies) // 2]:.2f}ms")
        print(f"  P95:         {sorted_latencies[p95_index]:.2f}ms")
        print(f"  P99:         {sorted_latencies[p99_index]:.2f}ms")

        ops: Dict[str, List[float]] = {}
        categories: Dict[str, List[float]] = {}
        for result in self.results:
            if result.get("latency_ms") is None:
                continue
            ops.setdefault(result["operation"], []).append(result["latency_ms"])
            categories.setdefault(result.get("category") or "uncategorized", []).append(
                result["latency_ms"]
            )

        print("\n--- BREAKDOWN BY OPERATION ---")
        for operation, operation_latencies in sorted(ops.items()):
            print(f"  {operation}:")
            print(f"    Calls:   {len(operation_latencies)}")
            print(f"    Avg:     {sum(operation_latencies) / len(operation_latencies):.2f}ms")
            print(f"    Min/Max: {min(operation_latencies):.2f}ms / {max(operation_latencies):.2f}ms")

        print("\n--- BREAKDOWN BY CATEGORY ---")
        for category, category_latencies in sorted(categories.items()):
            print(f"  {category}:")
            print(f"    Scenarios: {len(category_latencies)}")
            print(f"    Avg:       {sum(category_latencies) / len(category_latencies):.2f}ms")
            print(f"    Min/Max:   {min(category_latencies):.2f}ms / {max(category_latencies):.2f}ms")

        print("\n" + "=" * 90)

    def save_results(self, output_file: Path) -> None:
        """Save benchmark results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "graph_info": self.graph_info,
            "total_scenarios": len(self.results),
            "successful_scenarios": len(
                [r for r in self.results if r.get("latency_ms") is not None]
            ),
            "results": self.results,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2, ensure_ascii=False, default=str)

        print(f"Detailed benchmark results saved to: {output_file}")


def main() -> int:
    """Run graph smoke tests, then benchmark."""
    try:
        graph_info = run_smoke_tests()
        benchmark = GraphToolBenchmark(graph_info)
        benchmark.run_benchmark()
        benchmark.print_summary()

        output_dir = Path(__file__).parent / "results"
        output_file = output_dir / f"graph_tool_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        benchmark.save_results(output_file)
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
