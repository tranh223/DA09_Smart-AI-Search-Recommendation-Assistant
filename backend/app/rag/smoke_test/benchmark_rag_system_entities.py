"""Smoke + benchmark end-to-end for rag_system with entity-focused comparison.

Entities here are explicit database entities:
- hotel (khách sạn)
- activity (hoạt động)/policy sections from hotel chunks

Outputs:
  smoke_test/results/rag_system_entity_benchmark_YYYYMMDD_HHMMSS.json

Run:
  cd smoke_test
  python benchmark_rag_system_entities.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system import get_chatbot


@dataclass
class EntityCase:
    id: str
    name: str
    query: str

    # Explicit entities that should appear in the answer text.
    # These are either HOTEL-related terms or ACTIVITY/POLICY-like terms from the DB chunks.
    entity_keywords: List[str]

    # Expected evidence sources.
    expected_sources: List[str]


CASES: List[EntityCase] = [
    EntityCase(
        id="ES_01",
        name="Hotel/activity relationship in HCM",
        query="Trong dataset, nếu xét khách sạn 'Khách sạn Renaissance Riverside Sài Gòn (Renaissance Riverside Hotel Saigon)' thì khách sạn này có mối quan hệ thế nào với các hoạt động: 'Vé vào cửa Công viên giải trí VinWonders Cửa Hội' và 'Vé vào cổng Công viên Chủ đề Suối Tiên' ở Thành phố Hồ Chí Minh? Hãy so sánh mức độ liên quan giữa các hoạt động và nêu thêm thông tin về các hoạt động đó (không cần gợi ý khách sạn nào khác).", 
        entity_keywords=["khách sạn", "VinWonders Cửa Hội", "Suối Tiên", "Thành phố Hồ Chí Minh"],
        expected_sources=["hotel_sql", "rag", "graph"],
    ),
    EntityCase(
        id="ES_02",
        name="Activity/Policy oriented - Da Nang",
        query="Ở Đà Nẵng, hãy phân tích mối quan hệ giữa các hoạt động (activities) và ít nhất một khách sạn cụ thể trong dataset. Chọn một khách sạn bất kỳ trong Đà Nẵng và trả lời: khách sạn đó có những hoạt động nào được gắn kèm, và các hoạt động nào phù hợp cho gia đình? Nêu thêm thông tin về từng hoạt động.",
        entity_keywords=["hoạt động", "gia đình", "Đà Nẵng", "tour"],
        expected_sources=["hotel_sql", "rag", "graph"],
    ),
    EntityCase(
        id="ES_03",
        name="Hotel vs activity pair - HCM",
        query="Trong dataset, với khách sạn 'Khách sạn Renaissance Riverside Sài Gòn (Renaissance Riverside Hotel Saigon)', so sánh mối quan hệ của khách sạn này với hai hoạt động: 'VIP Fast Track nhập cảnh tại sân bay Tân Sơn Nhất' và 'Dịch vụ Fast Track tại Sân bay Quốc tế Tân Sơn Nhất (SGN)'. Hoạt động nào liên quan hơn? Nêu thêm thông tin của từng hoạt động và giải thích quan hệ của chúng với khách sạn.",
        entity_keywords=["Renaissance Riverside", "Fast Track", "Tân Sơn Nhất", "khách sạn"],
        expected_sources=["hotel_sql", "rag", "graph"],
    ),
    EntityCase(
        id="ES_04",
        name="Hotel vs activities - Nha Trang",
        query="Với khách sạn 'Sunrise Nha Trang Beach Hotel & Spa', hãy mô tả mối quan hệ giữa khách sạn và các hoạt động: 'Vé vào cổng Công viên giải trí VinWonders Nha Trang' và 'Vé vào cổng Vinpearl Harbour Nha Trang'. So sánh hai hoạt động này về mức độ liên quan với khách sạn, và nêu thêm thông tin về từng hoạt động.",
        entity_keywords=["Sunrise Nha Trang", "VinWonders Nha Trang", "Vinpearl Harbour", "khách sạn"],
        expected_sources=["hotel_sql", "rag", "graph"],
    ),
    EntityCase(
        id="ES_05",
        name="Compare policies/activities mentions - HN",
        query="Trong dataset, xét khách sạn 'Khách sạn Pullman Hà Nội (Pullman Hanoi Hotel)'. Khách sạn này được mô tả gắn kèm những hoạt động nào? Hãy so sánh mối quan hệ giữa ít nhất hai hoạt động cụ thể: 'Vé xem Múa rối nước Lotus tại Hà Nội' và 'Vé xem Múa rối nước Thăng Long tại Hà Nội'. Nêu thêm thông tin về từng hoạt động và trả lời chúng khác nhau thế nào.",
        entity_keywords=["Pullman Hanoi", "Múa rối nước", "Lotus", "Thăng Long", "khách sạn"],
        expected_sources=["hotel_sql", "rag", "graph"],
    ),
]


def _normalize(s: str) -> str:
    return (s or "").lower()


def _contains_all_keywords(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    norm = _normalize(text)
    hits = 0
    missed: List[str] = []
    for kw in keywords:
        if _normalize(kw) in norm:
            hits += 1
        else:
            missed.append(kw)
    return hits, missed


def _count_rag_evidence(rag_results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not rag_results:
        return {"ok": False, "item_count": 0}

    items = rag_results.get("results") or []
    if isinstance(items, list):
        return {
            "ok": rag_results.get("success") is True,
            "item_count": len(items),
            "first_sections": [i.get("section") for i in items[:3] if isinstance(i, dict)],
        }

    return {"ok": False, "item_count": 0}


def _count_graph_evidence(graph_results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not graph_results:
        return {"ok": False, "item_count": 0}

    items = graph_results.get("results") or []
    if isinstance(items, list):
        labels = []
        for it in items[:5]:
            if isinstance(it, dict) and it.get("labels"):
                labels.append(it.get("labels"))
        return {
            "ok": graph_results.get("success") is True,
            "item_count": len(items),
            "sample_labels": labels[:2],
        }

    return {"ok": False, "item_count": 0}


def _count_hotel_sql_evidence(hotel_sql_results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not hotel_sql_results:
        return {"ok": False, "has_detail": False, "has_policies": False, "has_activities": False}

    ok = hotel_sql_results.get("success") is True
    res = hotel_sql_results.get("results") or {}

    detail = res.get("detail") if isinstance(res, dict) else None
    policies = res.get("policies") if isinstance(res, dict) else None
    activities = res.get("activities") if isinstance(res, dict) else None

    return {
        "ok": ok,
        "has_detail": detail is not None,
        "has_policies": policies is not None,
        "has_activities": activities is not None,
        "errors": res.get("errors") if isinstance(res, dict) else None,
    }


def _extract_entity_highlights(answer: str, entity_keywords: List[str]) -> Dict[str, Any]:
    hits, missed = _contains_all_keywords(answer, entity_keywords)
    return {
        "hit_count": hits,
        "missed_keywords": missed,
        "present_keywords": [kw for kw in entity_keywords if kw not in missed],
    }


def run_case(case: EntityCase, user_id: str = "user_001") -> Dict[str, Any]:
    bot = get_chatbot(user_id=user_id)

    t0 = time.time()
    detailed = bot.process(
        case.query,
        return_detailed=True,
        enable_rag=True,
        enable_graph=True,
    )
    latency_s = time.time() - t0

    response_text = detailed.get("response") or ""

    rag_evidence = _count_rag_evidence(detailed.get("rag"))
    graph_evidence = _count_graph_evidence(detailed.get("graph"))
    hotel_sql_evidence = _count_hotel_sql_evidence(detailed.get("hotel_sql"))

    entity_highlights = _extract_entity_highlights(response_text, case.entity_keywords)
    keyword_coverage = entity_highlights["hit_count"] / max(len(case.entity_keywords), 1)

    return {
        "case_id": case.id,
        "case_name": case.name,
        "query": case.query,
        "latency_s": latency_s,
        "latency_ms": latency_s * 1000,
        "response_preview": response_text[:400],
        "entity_keywords": case.entity_keywords,
        "entity_highlights": entity_highlights,
        "keyword_coverage": keyword_coverage,
        "evidence_summary": {
            "hotel_sql": hotel_sql_evidence,
            "rag": rag_evidence,
            "graph": graph_evidence,
        },
        "plan_result": detailed.get("plan"),
        "debug_detailed_keys": list(detailed.keys()),
    }


def main() -> int:
    user_id = "user_001"
    results: List[Dict[str, Any]] = []

    for case in CASES:
        print(f"Running {case.id}: {case.name}")
        try:
            r = run_case(case, user_id=user_id)
            results.append(r)
            print(
                f"  latency_ms={r['latency_ms']:.1f} keyword_coverage={r['keyword_coverage']:.2f} "
                f"present={r['entity_highlights']['present_keywords']}"
            )
        except Exception as e:
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
    keyword_cov = [
        r["keyword_coverage"]
        for r in results
        if isinstance(r.get("keyword_coverage"), (int, float))
    ]

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(results),
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "avg_keyword_coverage": (sum(keyword_cov) / len(keyword_cov)) if keyword_cov else None,
    }

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"rag_system_entity_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    payload = {"summary": summary, "results": results}
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Saved:", out_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

