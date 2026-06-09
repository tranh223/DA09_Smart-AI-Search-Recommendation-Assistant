"""
Benchmark suite for RAG pipeline
Tests latency, accuracy, and end-to-end performance across ~20 diverse use cases.
"""
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system import get_chatbot
from tools.user_profile_tool import get_all_user_profiles, get_user_by_id
from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# BENCHMARK USE CASES (~20 diverse scenarios)
# ============================================================================

BENCHMARK_CASES = [
    # =========================
    # 1. Simple Factual Queries
    # =========================
    {
        "id": "UC01",
        "name": "Simple destination info",
        "query": "What are the best beaches in Da Nang?",
        "category": "factual",
        "expected_keywords": ["beach", "Da Nang", "sand", "swimming"],
    },
    {
        "id": "UC02",
        "name": "Hotel search",
        "query": "Find budget-friendly hotels near My Khe Beach",
        "category": "factual",
        "expected_keywords": ["hotel", "budget", "affordable", "My Khe"],
    },
    {
        "id": "UC03",
        "name": "Activity recommendation",
        "query": "What activities are available in Ho Chi Minh City?",
        "category": "factual",
        "expected_keywords": ["activity", "Ho Chi Minh", "tours", "attractions"],
    },
    
    # =========================
    # 2. User Profile-Based Queries
    # =========================
    {
        "id": "UC04",
        "name": "Personalized recommendation for user_001",
        "query": "Find accommodation for user_001 in Da Nang",
        "category": "personalized",
        "expected_keywords": ["homestay", "budget", "near_beach"],
    },
    {
        "id": "UC05",
        "name": "Budget-constrained search",
        "query": "Show me budget hotels under 1,500,000 VND",
        "category": "personalized",
        "expected_keywords": ["price", "budget", "affordable", "under"],
    },
    {
        "id": "UC06",
        "name": "Traveler type matching",
        "query": "Recommend unique and lively destinations for explorers",
        "category": "personalized",
        "expected_keywords": ["explorer", "unique", "lively", "adventure"],
    },
    
    # =========================
    # 3. Complex Multi-Step Queries
    # =========================
    {
        "id": "UC07",
        "name": "Multi-criteria search",
        "query": "Find a homestay in Da Nang with WiFi, breakfast, unique vibe, and under 1.5M VND",
        "category": "complex",
        "expected_keywords": ["homestay", "WiFi", "breakfast", "unique", "price"],
    },
    {
        "id": "UC08",
        "name": "Comparison request",
        "query": "Compare budget hotels vs hostels in Da Nang",
        "category": "complex",
        "expected_keywords": ["compare", "budget_hotel", "hostel", "difference"],
    },
    {
        "id": "UC09",
        "name": "Planning query",
        "query": "Plan a 3-day trip to Da Nang with activities and accommodation",
        "category": "complex",
        "expected_keywords": ["plan", "itinerary", "accommodation", "activities", "day"],
    },
    
    # =========================
    # 4. Constraint-Based Queries
    # =========================
    {
        "id": "UC10",
        "name": "Group travel planning",
        "query": "Find accommodations for a group of 4 with budget constraints in Nha Trang",
        "category": "constraint",
        "expected_keywords": ["group", "4", "accommodation", "budget", "Nha Trang"],
    },
    {
        "id": "UC11",
        "name": "Pet-friendly search",
        "query": "Find pet-friendly hotels in Ho Chi Minh City",
        "category": "constraint",
        "expected_keywords": ["pet", "friendly", "Ho Chi Minh", "allow"],
    },
    {
        "id": "UC12",
        "name": "Family travel",
        "query": "Best family-friendly hotels with children facilities",
        "category": "constraint",
        "expected_keywords": ["family", "children", "kid-friendly", "facilities"],
    },
    
    # =========================
    # 5. Preference Refinement Queries
    # =========================
    {
        "id": "UC13",
        "name": "Negative preference handling",
        "query": "Find hotels in Da Nang but avoid luxury and crowded areas",
        "category": "preference",
        "expected_keywords": ["avoid", "luxury", "crowded", "quiet"],
    },
    {
        "id": "UC14",
        "name": "Safety-focused search",
        "query": "Show me safe neighborhoods and low-crime areas in Ho Chi Minh City",
        "category": "preference",
        "expected_keywords": ["safe", "security", "low-crime", "neighborhood"],
    },
    {
        "id": "UC15",
        "name": "Amenity-focused",
        "query": "Hotels with strong WiFi and breakfast included",
        "category": "preference",
        "expected_keywords": ["WiFi", "breakfast", "included", "amenities"],
    },
    
    # =========================
    # 6. Context-Aware Queries
    # =========================
    {
        "id": "UC16",
        "name": "Real estate + travel mix",
        "query": "Find vacation rentals near tech hubs in Ho Chi Minh",
        "category": "context",
        "expected_keywords": ["rental", "vacation", "tech", "area"],
    },
    {
        "id": "UC17",
        "name": "Seasonal planning",
        "query": "Best time to visit Da Nang and recommended accommodations",
        "category": "context",
        "expected_keywords": ["season", "weather", "best_time", "accommodation"],
    },
    {
        "id": "UC18",
        "name": "Transportation integration",
        "query": "Hotels near major transport hubs in Da Nang with good connectivity",
        "category": "context",
        "expected_keywords": ["transport", "hub", "near", "connectivity"],
    },
    
    # =========================
    # 7. Advanced Reasoning
    # =========================
    {
        "id": "UC19",
        "name": "Cross-destination comparison",
        "query": "Which is better: Da Nang or Nha Trang for a budget traveler?",
        "category": "reasoning",
        "expected_keywords": ["compare", "better", "Da Nang", "Nha Trang", "budget"],
    },
    {
        "id": "UC20",
        "name": "Long-tail discovery",
        "query": "Hidden gems and off-the-beaten-path accommodations in central Vietnam",
        "category": "reasoning",
        "expected_keywords": ["hidden", "gem", "off-beaten", "unique", "Vietnam"],
    },
]


# ============================================================================
# METRICS & EVALUATION
# ============================================================================

class BenchmarkMetrics:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.summary = {}
    
    def add_result(self, use_case_id: str, response: str, latency: float, 
                   use_case: Dict[str, Any], accuracy_score: float):
        """Record a benchmark result."""
        result = {
            "use_case_id": use_case_id,
            "use_case_name": use_case.get("name"),
            "category": use_case.get("category"),
            "query": use_case.get("query"),
            "response_preview": response[:200] + "..." if len(response) > 200 else response,
            "latency_ms": latency * 1000,
            "accuracy_score": accuracy_score,
            "timestamp": datetime.now().isoformat(),
        }
        self.results.append(result)
    
    def compute_summary(self):
        """Compute summary statistics."""
        if not self.results:
            return
        
        latencies = [r["latency_ms"] for r in self.results]
        accuracies = [r["accuracy_score"] for r in self.results]
        
        self.summary = {
            "total_cases": len(self.results),
            "latency_avg_ms": sum(latencies) / len(latencies),
            "latency_min_ms": min(latencies),
            "latency_max_ms": max(latencies),
            "latency_p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "accuracy_avg": sum(accuracies) / len(accuracies),
            "accuracy_min": min(accuracies),
            "accuracy_max": max(accuracies),
            "category_breakdown": self._breakdown_by_category(),
        }
    
    def _breakdown_by_category(self) -> Dict[str, Dict]:
        """Breakdown metrics by use case category."""
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"count": 0, "latencies": [], "accuracies": []}
            categories[cat]["count"] += 1
            categories[cat]["latencies"].append(result["latency_ms"])
            categories[cat]["accuracies"].append(result["accuracy_score"])
        
        breakdown = {}
        for cat, data in categories.items():
            lats = data["latencies"]
            accs = data["accuracies"]
            breakdown[cat] = {
                "count": data["count"],
                "avg_latency_ms": sum(lats) / len(lats),
                "avg_accuracy": sum(accs) / len(accs),
            }
        return breakdown


# ============================================================================
# ACCURACY EVALUATION
# ============================================================================

def evaluate_accuracy(query: str, response: str, expected_keywords: List[str]) -> float:
    """
    Evaluate accuracy by checking for expected keywords in response.
    Returns score between 0 and 1.
    """
    if not response:
        return 0.0
    
    response_lower = response.lower()
    found_keywords = [kw for kw in expected_keywords if kw.lower() in response_lower]
    
    # Score: percentage of keywords found
    score = len(found_keywords) / len(expected_keywords) if expected_keywords else 0.5
    
    # Bonus: longer response = more likely to be informative
    response_length_bonus = min(len(response) / 500, 0.2)  # Max +0.2 bonus
    
    final_score = min(score + response_length_bonus, 1.0)
    return final_score


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

def run_benchmark(verbose: bool = True) -> BenchmarkMetrics:
    """Run the complete benchmark suite."""
    print("=" * 80)
    print("RAG PIPELINE BENCHMARK")
    print("=" * 80)
    print(f"Running {len(BENCHMARK_CASES)} use cases...")
    print()
    
    metrics = BenchmarkMetrics()
    
    try:
        chatbot = get_chatbot()
    except Exception as e:
        print(f"⊘ Could not initialize chatbot: {e}")
        print("Skipping benchmark.")
        return metrics
    
    for i, use_case in enumerate(BENCHMARK_CASES, 1):
        use_case_id = use_case["id"]
        query = use_case["query"]
        expected_keywords = use_case.get("expected_keywords", [])
        
        print(f"[{i}/{len(BENCHMARK_CASES)}] {use_case_id}: {use_case['name']}")
        
        if verbose:
            print(f"  Query: {query}")
        
        try:
            # Measure latency
            start_time = time.time()
            response = chatbot.chat(query)
            latency = time.time() - start_time
            
            # Evaluate accuracy
            accuracy = evaluate_accuracy(query, response, expected_keywords)
            
            # Record result
            metrics.add_result(use_case_id, response, latency, use_case, accuracy)
            
            if verbose:
                print(f"  Response: {response[:100]}...")
                print(f"  Latency: {latency*1000:.1f}ms, Accuracy: {accuracy:.2f}")
            else:
                print(f"  ✓ {latency*1000:.1f}ms | Accuracy: {accuracy:.2f}")
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            metrics.add_result(use_case_id, f"ERROR: {str(e)}", 0, use_case, 0.0)
        
        print()
    
    # Compute summary
    metrics.compute_summary()
    return metrics


def print_results(metrics: BenchmarkMetrics):
    """Print formatted benchmark results."""
    if not metrics.summary:
        print("No results to display.")
        return
    
    summary = metrics.summary
    
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Use Cases: {summary['total_cases']}")
    
    print(f"\n--- LATENCY (ms) ---")
    print(f"  Average:  {summary['latency_avg_ms']:.1f}ms")
    print(f"  Min:      {summary['latency_min_ms']:.1f}ms")
    print(f"  Max:      {summary['latency_max_ms']:.1f}ms")
    print(f"  P95:      {summary['latency_p95_ms']:.1f}ms")
    
    print(f"\n--- ACCURACY (0-1) ---")
    print(f"  Average:  {summary['accuracy_avg']:.3f}")
    print(f"  Min:      {summary['accuracy_min']:.3f}")
    print(f"  Max:      {summary['accuracy_max']:.3f}")
    
    print(f"\n--- BREAKDOWN BY CATEGORY ---")
    for category, stats in summary['category_breakdown'].items():
        print(f"  {category}:")
        print(f"    Cases:    {stats['count']}")
        print(f"    Avg Lat:  {stats['avg_latency_ms']:.1f}ms")
        print(f"    Avg Acc:  {stats['avg_accuracy']:.3f}")
    
    print("\n" + "=" * 80)


def save_results(metrics: BenchmarkMetrics, output_file: Path):
    """Save detailed results to JSON."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": metrics.summary,
        "detailed_results": metrics.results,
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to: {output_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    # Run benchmark
    metrics = run_benchmark(verbose=False)
    
    # Print results
    print_results(metrics)
    
    # Save results to file
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_results(metrics, output_file)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
