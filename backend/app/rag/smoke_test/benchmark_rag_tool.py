"""Smoke test + benchmark for tools.rag_tool.search_rag

Goal: exercise FAISS retrieval hard (latency, top_k correctness, and basic
sanity checks across diverse query patterns).

Outputs:
- smoke_test/results/rag_tool_benchmark_YYYYMMDD_HHMMSS.json

Run:
  cd smoke_test
  python benchmark_rag_tool.py
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.rag_tool import search_rag


@dataclass
class QueryCase:
    id: str
    name: str
    query: str
    expected_contains_any: List[str]
    tags: List[str]


QUERY_CASES: List[QueryCase] = [
    QueryCase(
        id="RUC01",
        name="Policy - check in/out",
        query="Khách sạn có chính sách check-in và check-out như thế nào?",
        expected_contains_any=["check", "in", "out", "thời gian"],
        tags=["policy"],
    ),
    QueryCase(
        id="RUC02",
        name="Amenities - WiFi/breakfast",
        query="Khách sạn có wifi mạnh và bữa sáng miễn phí không?",
        expected_contains_any=["wifi", "bữa sáng", "breakfast"],
        tags=["amenities"],
    ),
    QueryCase(
        id="RUC03",
        name="Pets policy",
        query="Thú nuôi có được phép mang vào khách sạn không?",
        expected_contains_any=["pet", "thú nuôi", "không được phép", "cho phép"],
        tags=["policy", "pets"],
    ),
    QueryCase(
        id="RUC04",
        name="Deposit policy",
        query="Khách sạn có yêu cầu đặt cọc không? Nếu có thì như thế nào?",
        expected_contains_any=["deposit", "tiền đặt cọc", "đặt cọc"],
        tags=["policy", "deposit"],
    ),
    QueryCase(
        id="RUC05",
        name="Children policy",
        query="Chính sách cho trẻ em bao nhiêu tuổi được miễn phí?",
        expected_contains_any=["trẻ em", "children", "miễn phí", "tuổi"],
        tags=["policy", "kids"],
    ),
    QueryCase(
        id="RUC06",
        name="Activities",
        query="Khách sạn có những hoạt động/tour nào cho khách tham quan?",
        expected_contains_any=["activity", "tour", "hoạt động"],
        tags=["activities"],
    ),
    QueryCase(
        id="RUC07",
        name="Pool",
        query="Có hồ bơi và dịch vụ đi kèm như thế nào?",
        expected_contains_any=["pool", "hồ bơi", "bể bơi"],
        tags=["amenities", "pool"],
    ),
    QueryCase(
        id="RUC08",
        name="Spa/fitness",
        query="Khách sạn có spa, xông hơi hoặc phòng tập gym không?",
        expected_contains_any=["spa", "xông hơi", "gym", "fitness"],
        tags=["amenities", "spa"],
    ),
    QueryCase(
        id="RUC09",
        name="Transport/transfer",
        query="Khách sạn có cung cấp đưa đón sân bay hoặc thuê xe không?",
        expected_contains_any=["airport", "transfer", "thuê xe", "đưa đón"],
        tags=["transport"],
    ),
    QueryCase(
        id="RUC10",
        name="Parking",
        query="Bãi đỗ xe hoặc valet có sẵn không?",
        expected_contains_any=["parking", "valet", "bãi đỗ xe"],
        tags=["amenities", "parking"],
    ),
]


def _normalize_text(s: str) -> str:
    return (s or "").lower()


def _score_result(result: List[Dict[str, Any]], expected_keywords: List[str]) -> float:
    """Simple keyword overlap score between retrieved content and expected keywords."""
    if not result:
        return 0.0
    haystack = " ".join([_normalize_text(r.get("content") or "") for r in result])
    if not expected_keywords:
        return 0.5
    hits = 0
    for kw in expected_keywords:
        if _normalize_text(kw) in haystack:
            hits += 1
    return hits / len(expected_keywords)


def _run_one(case: QueryCase, top_k: int, iterations: int) -> Tuple[float, Any]:
    """Return (avg_latency, last_result)"""
    latencies: List[float] = []
    last = None
    for _ in range(iterations):
        t0 = time.time()
        last = search_rag(case.query, top_k=top_k)
        latencies.append(time.time() - t0)
    return sum(latencies) / len(latencies), last


def main():
    random.seed(42)

    # Parameters: adjust for harder benchmark
    top_k = int(random.choice([3, 5]))
    iterations_per_case = int(random.choice([3, 5]))

    print("=" * 80)
    print("RAG TOOL BENCHMARK (FAISS)")
    print("=" * 80)
    print(f"Cases: {len(QUERY_CASES)} | top_k={top_k} | iterations/case={iterations_per_case}")
    print()

    results: List[Dict[str, Any]] = []
    overall_latencies: List[float] = []

    for idx, case in enumerate(QUERY_CASES, 1):
        print(f"[{idx}/{len(QUERY_CASES)}] {case.id}: {case.name}")

        try:
            avg_latency, last_result = _run_one(case, top_k=top_k, iterations=iterations_per_case)
            overall_latencies.append(avg_latency)

            score = _score_result(last_result or [], case.expected_contains_any)
            got_count = len(last_result or [])

            # Sanity: every item should have required keys
            required_keys = {"score", "content", "section", "metadata", "chunk_id"}
            missing_keys = []
            if last_result:
                for r in last_result:
                    mk = list(required_keys - set(r.keys()))
                    if mk:
                        missing_keys.append(mk)

            status = "✓ PASS" if got_count > 0 else "✗ FAIL"
            print(f"  avg_latency={avg_latency*1000:.1f}ms | got={got_count} | keyword_score={score:.2f} | {status}")
            if missing_keys:
                print(f"  ⚠ missing_keys (first): {missing_keys[0]}")

            results.append(
                {
                    "case_id": case.id,
                    "case_name": case.name,
                    "query": case.query,
                    "tags": case.tags,
                    "top_k": top_k,
                    "iterations": iterations_per_case,
                    "avg_latency_ms": avg_latency * 1000,
                    "got_count": got_count,
                    "keyword_score": score,
                    "expected_keywords": case.expected_contains_any,
                    "last_result_preview": [
                        {
                            "score": r.get("score"),
                            "chunk_id": r.get("chunk_id"),
                            "section": r.get("section"),
                            "content_preview": (r.get("content") or "")[:120],
                            "metadata_preview": {k: (v if not isinstance(v, (dict, list)) else type(v).__name__) for k, v in (r.get("metadata") or {}).items()} ,
                        }
                        for r in (last_result or [])[:top_k]
                    ],
                }
            )
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append(
                {
                    "case_id": case.id,
                    "case_name": case.name,
                    "query": case.query,
                    "tags": case.tags,
                    "top_k": top_k,
                    "iterations": iterations_per_case,
                    "avg_latency_ms": None,
                    "got_count": 0,
                    "keyword_score": 0.0,
                    "error": str(e),
                }
            )

        print()

    summary = {
        "timestamp": datetime.now().isoformat(),
        "top_k": top_k,
        "iterations_per_case": iterations_per_case,
        "total_cases": len(QUERY_CASES),
        "successful_cases": len([r for r in results if r.get("error") is None]),
        "latency_avg_ms": (sum(overall_latencies) / len(overall_latencies)) if overall_latencies else None,
        "keyword_score_avg": (sum(r.get("keyword_score", 0.0) for r in results) / len(results)) if results else None,
    }

    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"rag_tool_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    payload = {"summary": summary, "detailed": results}
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 80)
    print("Benchmark done")
    print(f"Summary: {summary}")
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()

