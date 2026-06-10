"""
Focused benchmark for user_profile_tool.py
Tests latency, accuracy, and performance of user profile retrieval functions.
"""
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.user_profile_tool import (
    get_user_profile_source,
    get_all_user_profiles,
    get_user_by_id,
    refresh_user_profile_cache,
    search_user_profile,
    search_users_by_destination,
    get_user_preferences,
    filter_users_by_budget_level,
    filter_users_by_traveler_type,
    filter_users_by_amenities,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# BENCHMARK SCENARIOS FOR user_profile_tool
# ============================================================================

BENCHMARK_SCENARIOS = [
    # Load operations
    {
        "id": "LOAD_001",
        "name": "Load all users (cold start)",
        "operation": "load_all",
        "iterations": 1,
        "expected_metric": "latency < 500ms",
    },
    {
        "id": "LOAD_002",
        "name": "Load all users (cached)",
        "operation": "load_all",
        "iterations": 100,
        "expected_metric": "latency < 5ms (avg)",
    },
    
    # Search by ID operations
    {
        "id": "SEARCH_001",
        "name": "Get user by ID (first)",
        "operation": "get_by_id",
        "user_id": "user_001",
        "iterations": 50,
        "expected_metric": "latency < 10ms",
    },
    {
        "id": "SEARCH_002",
        "name": "Get user by ID (middle)",
        "operation": "get_by_id",
        "user_id": "user_005",
        "iterations": 50,
        "expected_metric": "latency < 10ms",
    },
    {
        "id": "SEARCH_003",
        "name": "Search user profile by ID",
        "operation": "search_profile",
        "user_id": "user_001",
        "iterations": 50,
        "expected_metric": "latency < 10ms",
    },
    
    # Destination search operations
    {
        "id": "DEST_001",
        "name": "Search users by destination (Da Nang)",
        "operation": "search_destination",
        "destination": "Da Nang",
        "iterations": 30,
        "expected_metric": "latency < 20ms",
    },
    {
        "id": "DEST_002",
        "name": "Search users by destination (Ho Chi Minh)",
        "operation": "search_destination",
        "destination": "Ho Chi Minh",
        "iterations": 30,
        "expected_metric": "latency < 20ms",
    },
    {
        "id": "DEST_003",
        "name": "Search users by partial destination match",
        "operation": "search_destination",
        "destination": "Nha",
        "iterations": 30,
        "expected_metric": "latency < 20ms",
    },
    
    # Preference extraction
    {
        "id": "PREF_001",
        "name": "Get user preferences (user_001)",
        "operation": "get_preferences",
        "user_id": "user_001",
        "iterations": 40,
        "expected_metric": "latency < 15ms",
    },
    {
        "id": "PREF_002",
        "name": "Get user preferences (user_002)",
        "operation": "get_preferences",
        "user_id": "user_002",
        "iterations": 40,
        "expected_metric": "latency < 15ms",
    },
    
    # Complex queries
    {
        "id": "COMPLEX_001",
        "name": "Filter users by budget level",
        "operation": "complex_filter",
        "filter_type": "budget",
        "filter_value": "low",
        "iterations": 20,
        "expected_metric": "latency < 30ms",
    },
    {
        "id": "COMPLEX_002",
        "name": "Filter users by traveler type",
        "operation": "complex_filter",
        "filter_type": "traveler_type",
        "iterations": 20,
        "expected_metric": "latency < 30ms",
    },
    {
        "id": "COMPLEX_003",
        "name": "Filter users by amenities preference",
        "operation": "complex_filter",
        "filter_type": "amenities",
        "iterations": 20,
        "expected_metric": "latency < 30ms",
    },
]


# ============================================================================
# BENCHMARK EXECUTOR
# ============================================================================

class UserProfileToolBenchmark:
    def __init__(self):
        self.results = []
        self.all_users = None
        self.profile_source = get_user_profile_source()
    
    def execute_operation(self, scenario: Dict[str, Any]) -> Tuple[float, int, Any]:
        """Execute a benchmark operation and return (latency, iterations, result)."""
        operation = scenario["operation"]
        iterations = scenario.get("iterations", 1)
        
        if operation == "load_all" and scenario.get("id") == "LOAD_001":
            refresh_user_profile_cache()
            self.all_users = None

        # Load data if needed. Do not warm the cache before load benchmarks.
        if self.all_users is None and operation != "load_all":
            self.all_users = get_all_user_profiles()
        
        if operation == "load_all":
            start = time.time()
            for _ in range(iterations):
                get_all_user_profiles()
            elapsed = time.time() - start
            return elapsed / iterations, iterations, len(get_all_user_profiles())
        
        elif operation == "get_by_id":
            user_id = scenario.get("user_id")
            start = time.time()
            for _ in range(iterations):
                get_user_by_id(user_id)
            elapsed = time.time() - start
            result = get_user_by_id(user_id)
            return elapsed / iterations, iterations, result.get("name") if result else None
        
        elif operation == "search_profile":
            user_id = scenario.get("user_id")
            start = time.time()
            for _ in range(iterations):
                search_user_profile(user_id)
            elapsed = time.time() - start
            result = search_user_profile(user_id)
            return elapsed / iterations, iterations, result.get("name") if result else None
        
        elif operation == "search_destination":
            destination = scenario.get("destination")
            start = time.time()
            for _ in range(iterations):
                search_users_by_destination(destination)
            elapsed = time.time() - start
            results = search_users_by_destination(destination)
            return elapsed / iterations, iterations, len(results)
        
        elif operation == "get_preferences":
            user_id = scenario.get("user_id")
            start = time.time()
            for _ in range(iterations):
                get_user_preferences(user_id)
            elapsed = time.time() - start
            result = get_user_preferences(user_id)
            return elapsed / iterations, iterations, bool(result)
        
        elif operation == "complex_filter":
            filter_type = scenario.get("filter_type")
            filter_value = scenario.get("filter_value")
            start = time.time()
            for _ in range(iterations):
                if filter_type == "budget":
                    filter_users_by_budget_level(filter_value or "low")
                elif filter_type == "traveler_type":
                    filter_users_by_traveler_type("solo")
                elif filter_type == "amenities":
                    filter_users_by_amenities("wifi")
            elapsed = time.time() - start
            if filter_type == "budget":
                results = filter_users_by_budget_level(filter_value or "low")
            elif filter_type == "traveler_type":
                results = filter_users_by_traveler_type("solo")
            elif filter_type == "amenities":
                results = filter_users_by_amenities("wifi")
            else:
                results = []
            return elapsed / iterations, iterations, len(results)
        
        return 0, iterations, None
    
    def run_benchmark(self, verbose: bool = True):
        """Run all benchmark scenarios."""
        print("=" * 90)
        print("USER PROFILE TOOL BENCHMARK")
        print("=" * 90)
        print(
            "MongoDB source: "
            f"{self.profile_source['database']}.{self.profile_source['collection']}"
        )
        print(f"Running {len(BENCHMARK_SCENARIOS)} scenarios...\n")
        
        for i, scenario in enumerate(BENCHMARK_SCENARIOS, 1):
            scenario_id = scenario["id"]
            name = scenario["name"]
            iterations = scenario.get("iterations", 1)
            expected = scenario.get("expected_metric", "N/A")
            
            print(f"[{i}/{len(BENCHMARK_SCENARIOS)}] {scenario_id}: {name}")
            
            try:
                latency, iters, result = self.execute_operation(scenario)
                
                result_str = str(result)[:50] if result else "N/A"
                print(f"  Latency: {latency*1000:.2f}ms (avg over {iters} iterations)")
                print(f"  Result: {result_str}")
                print(f"  Expected: {expected}")
                
                # Determine pass/fail
                status = "✓ PASS" if self._check_threshold(scenario, latency) else "⚠ SLOW"
                print(f"  {status}\n")
                
                self.results.append({
                    "scenario_id": scenario_id,
                    "name": name,
                    "operation": scenario["operation"],
                    "profile_source": self.profile_source,
                    "iterations": iters,
                    "latency_ms": latency * 1000,
                    "latency_total_ms": latency * iters * 1000,
                    "result": result_str,
                    "expected_metric": expected,
                    "timestamp": datetime.now().isoformat(),
                })
            
            except Exception as e:
                print(f"  ✗ ERROR: {e}\n")
                self.results.append({
                    "scenario_id": scenario_id,
                    "name": name,
                    "operation": scenario["operation"],
                    "profile_source": self.profile_source,
                    "latency_ms": None,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
    
    def _check_threshold(self, scenario: Dict[str, Any], latency: float) -> bool:
        """Check if latency meets expected threshold."""
        expected = scenario.get("expected_metric", "")
        
        # Parse expected metric
        if "< " in expected:
            threshold_str = expected.split("< ")[1].split("ms")[0]
            try:
                threshold_ms = float(threshold_str)
                return latency * 1000 < threshold_ms
            except:
                return True
        
        return True
    
    def print_summary(self):
        """Print benchmark summary."""
        if not self.results:
            print("No results to display.")
            return
        
        latencies = [r["latency_ms"] for r in self.results if r.get("latency_ms")]
        
        if not latencies:
            print("No valid latency measurements.")
            return
        
        print("\n" + "=" * 90)
        print("BENCHMARK SUMMARY")
        print("=" * 90)
        
        print(f"\nTotal Scenarios: {len(self.results)}")
        print(f"Successful: {len(latencies)}")
        print(f"Failed: {len(self.results) - len(latencies)}")
        
        print(f"\n--- LATENCY STATISTICS (ms) ---")
        print(f"  Average:     {sum(latencies) / len(latencies):.2f}ms")
        print(f"  Min:         {min(latencies):.2f}ms")
        print(f"  Max:         {max(latencies):.2f}ms")
        print(f"  Median:      {sorted(latencies)[len(latencies)//2]:.2f}ms")
        print(f"  P95:         {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")
        print(f"  P99:         {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")
        
        # Group by operation
        ops = {}
        for r in self.results:
            op = r.get("operation")
            if op not in ops:
                ops[op] = []
            if r.get("latency_ms"):
                ops[op].append(r["latency_ms"])
        
        print(f"\n--- BREAKDOWN BY OPERATION ---")
        for op, lats in sorted(ops.items()):
            print(f"  {op}:")
            print(f"    Calls:   {len(lats)}")
            if lats:
                print(f"    Avg:     {sum(lats)/len(lats):.2f}ms")
                print(f"    Min/Max: {min(lats):.2f}ms / {max(lats):.2f}ms")
            else:
                print(f"    Avg:     N/A (no successful calls)")
                print(f"    Min/Max: N/A")
        
        print("\n" + "=" * 90)
    
    def save_results(self, output_file: Path):
        """Save detailed results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "profile_source": self.profile_source,
            "total_scenarios": len(self.results),
            "successful_scenarios": len([r for r in self.results if r.get("latency_ms")]),
            "results": self.results,
        }
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"Detailed results saved to: {output_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    benchmark = UserProfileToolBenchmark()
    
    # Run benchmark
    benchmark.run_benchmark(verbose=True)
    
    # Print summary
    benchmark.print_summary()
    
    # Save results
    output_dir = Path(__file__).parent / "results"
    output_file = output_dir / f"user_profile_tool_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    benchmark.save_results(output_file)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
