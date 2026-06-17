"""Harder benchmark for tools.rag_tool.search_rag

This script generates additional long-tail queries by combining:
- Vietnamese policy/amenity keywords
- English synonyms
- Random filler patterns

It measures latency under repeated calls and validates basic return structure.

Run:
  cd smoke_test
  python benchmark_hard_cases_rag_tool.py
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.rag_tool import search_rag


FILLERS = [
    "cho tôi",
    "giúp tôi",
    "tìm kiếm",
    "cần biết",
    "có hay không",
    "mình muốn",
    "với ngân sách phù hợp",
    "nếu có thì mức nào",
]

VI_KW = [
    "bữa sáng",
    "wifi",
    "hồ bơi",
    "spa",
    "xông hơi",
    "phòng tập gym",
    "thú nuôi",
    "đặt cọc",
    "trẻ em miễn phí",
    "đưa đón sân bay",
    "thuê xe",
    "bãi đỗ xe",
    "valet",
]

EN_KW = [
    "breakfast",
    "wifi",
    "pool",
    "spa",
    "sauna",
    "gym",
    "pet",
    "deposit",
    "children free",
    "airport transfer",
    "car rental",
    "parking",
    "valet",
]

QUESTION_TEMPLATES = [
    "Khách sạn {kw} có không? {filler}.",
    "Cho mình thông tin về {kw}. {filler}.",
    "Mình đang tìm {kw} và điều kiện như thế nào? {filler}.",
    "Có quy định liên quan đến {kw} không? {filler}.",
]


def _make_query(kw: str, filler: str, template: str) -> str:
    return template.format(kw=kw, filler=filler)


def _validate_item(item: Dict[str, Any]) -> List[str]:
    required = ["score", "content", "section", "metadata", "chunk_id"]
    missing = [k for k in required if k not in item]
    return missing


def main():
    random.seed(123)

    top_k = int(random.choice([5, 8]))
    per_case = int(random.choice([3, 4]))
    cases_per_kw = 2

    kw_pool = VI_KW + EN_KW
    templates = QUESTION_TEMPLATES

    generated: List[str] = []
    for kw in kw_pool:
        for _ in range(cases_per_kw):
            generated.append(_make_query(kw, random.choice(FILLERS), random.choice(templates)))

    # keep manageable but hard
    random.shuffle(generated)
    generated = generated[:60]

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []

    print("=" * 80)
    print("HARD CASE BENCHMARK (RAG TOOL)")
    print("=" * 80)
    print(f"Generated cases: {len(generated)} | top_k={top_k} | per_case={per_case}")

    for i, q in enumerate(generated, 1):
        t0 = time.time()
        last = None
        err = None
        try:
            for _ in range(per_case):
                last = search_rag(q, top_k=top_k)
            dt = time.time() - t0
            avg_latency = dt / per_case
            latencies.append(avg_latency)
        except Exception as e:
            avg_latency = None
            err = str(e)

        got = last or []

        missing_any = []
        if got:
            for it in got[:top_k]:
                miss = _validate_item(it)
                if miss:
                    missing_any.append(miss)
                    break

        status = "PASS" if (not err and len(got) > 0) else "FAIL"
        print(f"[{i}/{len(generated)}] {status} | avg_latency_ms={(avg_latency*1000) if avg_latency is not None else None}")

        results.append(
            {
                "query": q,
                "top_k": top_k,
                "per_case": per_case,
                "avg_latency_ms": (avg_latency * 1000) if avg_latency is not None else None,
                "got_count": len(got),
                "error": err,
                "missing_first_item": missing_any[0] if missing_any else None,
                "top_sections": [r.get("section") for r in got[: min(5, len(got))]],
            }
        )

    summary = {
        "timestamp": datetime.now().isoformat(),
        "top_k": top_k,
        "per_case": per_case,
        "total_queries": len(generated),
        "successful": len([r for r in results if r.get("error") is None and r.get("got_count", 0) > 0]),
        "latency_avg_ms": (sum(latencies) / len(latencies) * 1000) if latencies else None,
        "latency_p95_ms": (sorted(latencies)[int(len(latencies) * 0.95)] * 1000) if latencies else None,
    }

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"rag_tool_hard_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps({"summary": summary, "detailed": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 80)
    print("DONE")
    print(f"Summary: {summary}")
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()

