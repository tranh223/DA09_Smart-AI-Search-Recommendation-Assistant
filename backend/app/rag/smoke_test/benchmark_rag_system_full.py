#!/usr/bin/env python3
"""End-to-end smoke benchmark for the whole RAG system.

Runs `rag_system.chatbot.process(..., return_detailed=True)` across a list of
queries and captures:
- response text
- plan
- retrieval evidence from RAG and Graph

Outputs a single JSON file into:
  backend/app/rag/smoke_test/results/

Run:
  python backend/app/rag/smoke_test/benchmark_rag_system_full.py
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

# Add project root to path so imports work when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag.rag_system import get_chatbot  # type: ignore


RESULT_DIR = Path(__file__).parent / "results"


@dataclass
class Case:
    id: str
    name: str
    query: str
    expect_keywords: List[str]


CASES: List[Case] = [
    Case(
        id="FULL_01",
        name="Hotel feature QA (RAG only expected)",
        query="Khách sạn nào phù hợp nhất cho gia đình đi Đà Nẵng và vì sao? Nêu các tiện ích/đặc điểm quan trọng.",
        expect_keywords=["Đà Nẵng"],
    ),
    Case(
        id="FULL_02",
        name="Hotel policy/FAQ QA",
        query="Cho mình hỏi chính sách hoàn/hủy và các yêu cầu đặt phòng của khách sạn ở Nha Trang như thế nào?",
        expect_keywords=["Nha Trang"],
    ),
    Case(
        id="FULL_03",
        name="Hotel vs activities comparison (RAG + Graph)",
        query="So sánh mức độ liên quan giữa các hoạt động dành cho trẻ em tại VinWonders Cửa Hội và Suối Tiên đối với một gia đình ở Thành phố Hồ Chí Minh.",
        expect_keywords=["VinWonders", "Suối Tiên"],
    ),
]


def _normalize(s: str) -> str:
    return (s or "").lower()


def _coverage(answer: str, keywords: List[str]) -> Dict[str, Any]:
    norm = _normalize(answer)
    present = [kw for kw in keywords if _normalize(kw) in norm]
    missed = [kw for kw in keywords if kw not in present]
    return {
        "hit_count": len(present),
        "present_keywords": present,
        "missed_keywords": missed,
        "keyword_coverage": len(present) / max(len(keywords), 1),
    }


def run_case(bot: Any, case: Case, user_id: str) -> Dict[str, Any]:
    t0 = time.time()

    detailed = bot.process(
        case.query,
        return_detailed=True,
        enable_rag=True,
        enable_graph=True,
    )

    latency_s = time.time() - t0
    response = detailed.get("response") if isinstance(detailed, dict) else None
    response_text = response or ""

    rag = detailed.get("rag") if isinstance(detailed, dict) else None
    graph = detailed.get("graph") if isinstance(detailed, dict) else None

    rag_items = (rag or {}).get("results") if isinstance(rag, dict) else []
    graph_items = (graph or {}).get("results") if isinstance(graph, dict) else []

    cov = _coverage(response_text, case.expect_keywords)

    return {
        "case_id": case.id,
        "case_name": case.name,
        "query": case.query,
        "latency_ms": latency_s * 1000,
        "response_preview": response_text[:500],
        "response_len": len(response_text),
        "plan": detailed.get("plan") if isinstance(detailed, dict) else None,
        "rag_evidence": {
            "success": (rag or {}).get("success") if isinstance(rag, dict) else None,
            "count": len(rag_items) if isinstance(rag_items, list) else 0,
            "first_items": rag_items[:3] if isinstance(rag_items, list) else [],
        },
        "graph_evidence": {
            "success": (graph or {}).get("success") if isinstance(graph, dict) else None,
            "count": len(graph_items) if isinstance(graph_items, list) else 0,
            "first_items": graph_items[:3] if isinstance(graph_items, list) else [],
        },
        "keyword_coverage": cov,
        "debug_keys": list(detailed.keys()) if isinstance(detailed, dict) else [],
        "raw_detailed": detailed,
    }


def main() -> int:
    random.seed(42)

    user_id = "user_full_benchmark"
    bot = get_chatbot(user_id=user_id)

    results: List[Dict[str, Any]] = []

    for case in CASES:
        print(f"Running {case.id}: {case.name}")
        try:
            r = run_case(bot, case, user_id=user_id)
            results.append(r)
            print(
                f"  latency_ms={r['latency_ms']:.1f} rag_count={r['rag_evidence']['count']} "
                f"graph_count={r['graph_evidence']['count']} coverage={r['keyword_coverage']['keyword_coverage']:.2f}"
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "case_id": case.id,
                    "case_name": case.name,
                    "query": case.query,
                    "error": str(e),
                }
            )
            print(f"  ERROR: {e}")

    latencies = [r["latency_ms"] for r in results if isinstance(r.get("latency_ms"), (int, float))]
    coverages = [
        r["keyword_coverage"]["keyword_coverage"]
        for r in results
        if isinstance(r.get("keyword_coverage"), dict)
    ]

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(results),
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "avg_keyword_coverage": (sum(coverages) / len(coverages)) if coverages else None,
    }

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULT_DIR / f"rag_system_full_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Saved:", out_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

