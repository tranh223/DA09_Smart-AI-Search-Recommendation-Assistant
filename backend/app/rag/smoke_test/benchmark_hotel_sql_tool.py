"""Focused benchmark for tools/hotel_sql_tool.py.

Measures resolver and DA10 API lookup latency. Results are saved under
smoke_test/results as JSON.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hotel_sql_tool import HotelLookupInput, HotelSqlTool


BENCHMARK_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "RESOLVE_001",
        "name": "Resolve hotel by fuzzy name",
        "payload": {
            "hotel_name": "Bamboo Airways Hotel Da Nang",
            "city": "Đà Nẵng",
            "need": [],
        },
        "iterations": 1,
        "expected_metric": "latency < 3000ms",
    },
    {
        "id": "LOOKUP_001",
        "name": "Lookup detail by hotel_id",
        "payload": {
            "hotel_id": 9195,
            "need": ["detail"],
        },
        "iterations": 3,
        "expected_metric": "latency < 2000ms",
    },
    {
        "id": "LOOKUP_002",
        "name": "Lookup policies by hotel_id",
        "payload": {
            "hotel_id": 9195,
            "need": ["policies"],
        },
        "iterations": 3,
        "expected_metric": "latency < 2000ms",
    },
    {
        "id": "LOOKUP_003",
        "name": "Lookup activities by hotel_id",
        "payload": {
            "hotel_id": 9195,
            "need": ["activities"],
        },
        "iterations": 3,
        "expected_metric": "latency < 2000ms",
    },
    {
        "id": "LOOKUP_004",
        "name": "Lookup all hotel SQL data by hotel_id",
        "payload": {
            "hotel_id": 9195,
            "need": ["detail", "policies", "activities"],
        },
        "iterations": 3,
        "expected_metric": "latency < 3500ms",
    },
    {
        "id": "LOOKUP_005",
        "name": "Resolve by name and lookup all hotel SQL data",
        "payload": {
            "hotel_name": "Renaissance Riverside",
            "city": "Hồ Chí Minh",
            "need": ["detail", "policies", "activities"],
        },
        "iterations": 1,
        "expected_metric": "latency < 6000ms",
    },
    {
        "id": "ERROR_001",
        "name": "Unknown hotel name returns controlled error",
        "payload": {
            "hotel_name": "Definitely Unknown Hotel Name 000000",
            "city": "Hồ Chí Minh",
            "need": ["detail"],
        },
        "iterations": 1,
        "expected_error": "HotelNotFoundError",
        "expected_metric": "controlled HotelNotFoundError",
    },
]


class HotelSqlToolBenchmark:
    """Benchmark executor for HotelSqlTool."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    async def execute_operation(
        self,
        tool: HotelSqlTool,
        scenario: dict[str, Any],
    ) -> tuple[float, int, dict[str, Any]]:
        """Execute one benchmark scenario and return latency data."""

        iterations = int(scenario.get("iterations", 1))
        payload = HotelLookupInput(**scenario["payload"])
        last_result: dict[str, Any] | None = None

        start = time.perf_counter()
        for _ in range(iterations):
            output = await tool.lookup(payload)
            last_result = output.model_dump()
        elapsed = time.perf_counter() - start

        return elapsed / iterations, iterations, self._summarize_output(last_result or {})

    async def run_benchmark(self, verbose: bool = True) -> None:
        """Run all benchmark scenarios."""

        print("=" * 90)
        print("HOTEL SQL TOOL BENCHMARK")
        print("=" * 90)
        print(f"Running {len(BENCHMARK_SCENARIOS)} scenarios...\n")

        async with HotelSqlTool(timeout=20.0, max_retries=2) as tool:
            for index, scenario in enumerate(BENCHMARK_SCENARIOS, 1):
                scenario_id = scenario["id"]
                name = scenario["name"]
                expected = scenario.get("expected_metric", "N/A")

                print(f"[{index}/{len(BENCHMARK_SCENARIOS)}] {scenario_id}: {name}")

                try:
                    latency, iterations, result = await self.execute_operation(tool, scenario)
                    status = "PASS" if self._check_threshold(scenario, latency) else "SLOW"
                    if scenario.get("expected_error"):
                        status = "ERROR"

                    print(f"  Latency: {latency * 1000:.2f}ms (avg over {iterations} iterations)")
                    print(f"  Result: {json.dumps(result, ensure_ascii=False)[:180]}")
                    print(f"  Expected: {expected}")
                    print(f"  {status}\n")

                    self.results.append(
                        {
                            "scenario_id": scenario_id,
                            "name": name,
                            "payload": scenario["payload"],
                            "iterations": iterations,
                            "latency_ms": latency * 1000,
                            "latency_total_ms": latency * iterations * 1000,
                            "result": result,
                            "expected_metric": expected,
                            "status": status,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                except Exception as exc:
                    error_type = type(exc).__name__
                    expected_error = scenario.get("expected_error")
                    status = "PASS" if error_type == expected_error else "ERROR"

                    print(f"  {status}: {error_type}: {exc}\n")

                    self.results.append(
                        {
                            "scenario_id": scenario_id,
                            "name": name,
                            "payload": scenario["payload"],
                            "latency_ms": None,
                            "error": str(exc),
                            "error_type": error_type,
                            "expected_error": expected_error,
                            "expected_metric": expected,
                            "status": status,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

    def print_summary(self) -> None:
        """Print benchmark summary."""

        if not self.results:
            print("No results to display.")
            return

        successful_latencies = [
            result["latency_ms"]
            for result in self.results
            if isinstance(result.get("latency_ms"), (int, float))
        ]
        passed = len([result for result in self.results if result.get("status") == "PASS"])

        print("\n" + "=" * 90)
        print("BENCHMARK SUMMARY")
        print("=" * 90)
        print(f"Total Scenarios: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed/Slow: {len(self.results) - passed}")

        if successful_latencies:
            sorted_latencies = sorted(successful_latencies)
            p95_index = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
            p99_index = min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)

            print("\n--- LATENCY STATISTICS (ms) ---")
            print(f"  Average: {sum(successful_latencies) / len(successful_latencies):.2f}ms")
            print(f"  Min:     {min(successful_latencies):.2f}ms")
            print(f"  Max:     {max(successful_latencies):.2f}ms")
            print(f"  Median:  {sorted_latencies[len(sorted_latencies) // 2]:.2f}ms")
            print(f"  P95:     {sorted_latencies[p95_index]:.2f}ms")
            print(f"  P99:     {sorted_latencies[p99_index]:.2f}ms")

        print("\n" + "=" * 90)

    def save_results(self, output_file: Path) -> None:
        """Save detailed benchmark results to JSON."""

        output = {
            "timestamp": datetime.now().isoformat(),
            "tool": "tools.hotel_sql_tool.HotelSqlTool",
            "total_scenarios": len(self.results),
            "passed_scenarios": len(
                [result for result in self.results if result.get("status") == "PASS"]
            ),
            "results": self.results,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2, ensure_ascii=False)

        print(f"Detailed results saved to: {output_file}")

    def _check_threshold(self, scenario: dict[str, Any], latency: float) -> bool:
        """Check whether latency meets the expected metric threshold."""

        expected = scenario.get("expected_metric", "")
        if "< " not in expected or "ms" not in expected:
            return True

        try:
            threshold_ms = float(expected.split("< ", 1)[1].split("ms", 1)[0])
        except ValueError:
            return True

        return latency * 1000 < threshold_ms

    @staticmethod
    def _summarize_output(output: dict[str, Any]) -> dict[str, Any]:
        """Create compact benchmark metadata without changing raw tool behavior."""

        return {
            "hotel_id": output.get("hotel_id"),
            "resolved_name": output.get("resolved_name"),
            "has_detail": output.get("detail") is not None,
            "has_policies": output.get("policies") is not None,
            "has_activities": output.get("activities") is not None,
            "errors": output.get("errors", []),
            "payload_sizes": {
                "detail": len(json.dumps(output.get("detail"), ensure_ascii=False))
                if output.get("detail") is not None
                else 0,
                "policies": len(json.dumps(output.get("policies"), ensure_ascii=False))
                if output.get("policies") is not None
                else 0,
                "activities": len(json.dumps(output.get("activities"), ensure_ascii=False))
                if output.get("activities") is not None
                else 0,
            },
        }


async def async_main() -> int:
    """Async benchmark entry point."""

    benchmark = HotelSqlToolBenchmark()
    await benchmark.run_benchmark(verbose=True)
    benchmark.print_summary()

    output_dir = Path(__file__).parent / "results"
    output_file = (
        output_dir
        / f"hotel_sql_tool_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    benchmark.save_results(output_file)

    return 0


def main() -> int:
    """Main entry point."""

    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
