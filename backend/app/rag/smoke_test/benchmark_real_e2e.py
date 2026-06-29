#!/usr/bin/env python3
"""
RAG PIPELINE - REAL END-TO-END BENCHMARK WITH LLM
Full integration test with actual LLM calls
"""

import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment FIRST
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"WARNING: .env not found at {env_path}")

# Add RAG module to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Verify API key
if not os.getenv('OPENAI_API_KEY'):
    print("ERROR: OPENAI_API_KEY not set. Please check .env file.")
    sys.exit(1)

print(f"API Key configured: {os.getenv('OPENAI_API_KEY')[:30]}...")

# Real benchmark test cases
REAL_BENCHMARK_CASES = [
    {
        "id": "REAL001",
        "name": "Feature Query - Pool Amenity",
        "input": "Does Sofitel Hanoi have a swimming pool?",
        "category": "Feature Query",
        "expected_keywords": ["pool", "swimming", "sofitel"],
    },
    {
        "id": "REAL002",
        "name": "Feature Query - Family Amenities",
        "input": "What family amenities does Vinpearl Resort have?",
        "category": "Feature Query",
        "expected_keywords": ["family", "amenities"],
    },
    {
        "id": "REAL003",
        "name": "Policy Query - Check-in Time",
        "input": "What is the check-in time at Pullman Hanoi?",
        "category": "Policy Query",
        "expected_keywords": ["check-in", "time"],
    },
    {
        "id": "REAL004",
        "name": "Policy Query - Pet Policy",
        "input": "Are pets allowed at Sheraton Hanoi?",
        "category": "Policy Query",
        "expected_keywords": ["pet", "allowed"],
    },
    {
        "id": "REAL005",
        "name": "Comparison Query - Best Hotels",
        "input": "What are the best luxury hotels in Hanoi?",
        "category": "Comparison Query",
        "expected_keywords": ["hotel", "hanoi"],
    },
    {
        "id": "REAL006",
        "name": "Information Query - Amenities",
        "input": "Tell me about the facilities at Sofitel Metropole Hanoi",
        "category": "Information Query",
        "expected_keywords": ["sofitel", "hanoi"],
    },
]


class RealE2EBenchmark:
    """Real end-to-end RAG pipeline benchmark"""
    
    def __init__(self):
        self.results = []
        self.metrics = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total_time": 0.0,
            "avg_latency": 0.0,
            "latencies": []
        }
        self.chatbot = None
    
    def init_chatbot(self):
        """Initialize RAG chatbot"""
        try:
            print("\nInitializing RAG chatbot...")
            from backend.app.rag.rag_system import get_chatbot
            
            self.chatbot = get_chatbot("benchmark_user")
            print("  [OK] Chatbot initialized")
            return True
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            return False
    
    def evaluate_output(self, case, output, latency_ms):
        """Evaluate output"""
        
        if not output:
            return {"score": 0.0, "keywords": 0, "issues": ["Empty output"]}
        
        output_text = str(output).lower()
        keywords_found = sum(1 for kw in case["expected_keywords"] if kw.lower() in output_text)
        keyword_rate = keywords_found / len(case["expected_keywords"]) if case["expected_keywords"] else 1.0
        
        score = 0.0
        if output:
            score += 0.4
        if keyword_rate >= 0.3:
            score += 0.4
        if latency_ms <= 5000:
            score += 0.2
        
        return {
            "score": round(score, 2),
            "keywords": keywords_found,
            "total_keywords": len(case["expected_keywords"]),
            "keyword_rate": round(keyword_rate, 2),
            "latency_ok": latency_ms <= 5000
        }
    
    def run_case(self, case_idx, case):
        """Run single test"""
        
        print(f"\n  [{case_idx}] {case['id']}: {case['name']}")
        print(f"      Input: {case['input'][:60]}...")
        
        try:
            start = time.time()
            output = self.chatbot.chat(case['input'])
            latency_ms = round((time.time() - start) * 1000, 2)
            
            evaluation = self.evaluate_output(case, output, latency_ms)
            
            result = {
                "case_id": case["id"],
                "name": case["name"],
                "category": case["category"],
                "latency_ms": latency_ms,
                "evaluation": evaluation,
                "output_preview": str(output)[:150],
                "status": "PASS" if evaluation["score"] >= 0.60 else "FAIL"
            }
            
            print(f"      Status: {result['status']} | Latency: {latency_ms}ms | Score: {evaluation['score']}")
            print(f"      Keywords: {evaluation['keywords']}/{evaluation['total_keywords']} | Output: {len(str(output))} chars")
            
            return result
            
        except Exception as e:
            error_msg = str(e)[:100]
            print(f"      Status: ERROR | Error: {error_msg}")
            
            return {
                "case_id": case["id"],
                "name": case["name"],
                "category": case["category"],
                "error": error_msg,
                "latency_ms": 0,
                "status": "ERROR"
            }
    
    def run(self):
        """Run all tests"""
        
        print("\n" + "=" * 130)
        print(" " * 35 + "RAG PIPELINE - REAL END-TO-END BENCHMARK")
        print(" " * 25 + "Live LLM Integration with Graph DB & Vector Search")
        print("=" * 130)
        
        if not self.init_chatbot():
            print("\nFATAL: Cannot initialize chatbot")
            return
        
        print(f"\nRunning {len(REAL_BENCHMARK_CASES)} live benchmark cases...\n")
        
        total_start = time.time()
        
        for i, case in enumerate(REAL_BENCHMARK_CASES, 1):
            result = self.run_case(i, case)
            self.results.append(result)
            
            self.metrics["total"] += 1
            
            if result["status"] == "PASS":
                self.metrics["passed"] += 1
            elif result["status"] == "ERROR":
                self.metrics["errors"] += 1
            else:
                self.metrics["failed"] += 1
            
            if "latency_ms" in result:
                self.metrics["latencies"].append(result["latency_ms"])
        
        self.metrics["total_time"] = round(time.time() - total_start, 2)
        
        if self.metrics["latencies"]:
            self.metrics["avg_latency"] = round(sum(self.metrics["latencies"]) / len(self.metrics["latencies"]), 2)
    
    def report(self):
        """Print report"""
        
        print("\n" + "=" * 130)
        print("REAL END-TO-END BENCHMARK RESULTS")
        print("=" * 130)
        
        total = self.metrics["total"]
        passed = self.metrics["passed"]
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"""
EXECUTION SUMMARY:
  Total Cases: {total}
  Passed: {passed} ({pass_rate:.1f}%)
  Failed: {self.metrics['failed']}
  Errors: {self.metrics['errors']}
  Total Time: {self.metrics['total_time']}s

PERFORMANCE:
  Average Latency: {self.metrics['avg_latency']}ms
  Min Latency: {min(self.metrics['latencies']) if self.metrics['latencies'] else 'N/A'}ms
  Max Latency: {max(self.metrics['latencies']) if self.metrics['latencies'] else 'N/A'}ms

DETAILED RESULTS:
""")
        
        by_cat = {}
        for r in self.results:
            cat = r.get("category", "unknown")
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(r)
        
        for cat in sorted(by_cat.keys()):
            cases = by_cat[cat]
            cat_pass = sum(1 for r in cases if r["status"] == "PASS")
            print(f"\n  {cat}: {cat_pass}/{len(cases)} passed")
            
            for r in cases:
                if r["status"] == "ERROR":
                    print(f"    {r['case_id']} | {r['name']}")
                    print(f"      ERROR: {r.get('error', 'Unknown')}")
                else:
                    ev = r.get("evaluation", {})
                    print(f"    {r['case_id']} | {r['name']}")
                    print(f"      {r['status']} | {r['latency_ms']}ms | Score: {ev.get('score', 0)}")
                    print(f"      Keywords: {ev.get('keywords', 0)}/{ev.get('total_keywords', 0)}")
        
        print("\n" + "=" * 130)


def main():
    benchmark = RealE2EBenchmark()
    benchmark.run()
    benchmark.report()
    
    # Save
    output_file = Path(__file__).resolve().parent / "benchmark_real_e2e_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "metrics": benchmark.metrics,
            "results": benchmark.results
        }, f, indent=2)
    
    print(f"\nResults: {output_file}\n")
    return 0 if benchmark.metrics["passed"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
