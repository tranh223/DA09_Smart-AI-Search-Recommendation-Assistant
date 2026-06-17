"""Benchmark structured-input scenarios for the full hotel RAG pipeline.

This benchmark runs the real pipeline with the new structured input contract and
writes a JSON report under smoke_test/results/.

Usage:
  python smoke_test/benchmark_structured_pipeline.py
  python smoke_test/benchmark_structured_pipeline.py --limit 3
  python smoke_test/benchmark_structured_pipeline.py --case FEATURE_FAMILY_KIDS
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system import chatbot


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "FEATURE_FAMILY_KIDS",
        "category": "feature",
        "payload": {
            "intent_type": "HOTEL_FEATURE_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Khu nghỉ dưỡng Pullman Đà Nẵng có phù hợp cho gia đình và có kids club không?",
                "features": {
                    "hotel_name": "Khu nghỉ dưỡng Pullman Đà Nẵng",
                    "destination": "Da Nang",
                    "amenities": ["kids_club"],
                    "expectations": ["family_trip"],
                },
            },
        },
    },
    {
        "id": "FEATURE_POOL_SPA",
        "category": "feature",
        "payload": {
            "intent_type": "HOTEL_FEATURE_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Vinpearl Resort Nha Trang co ho boi va spa phu hop nghi duong khong?",
                "features": {
                    "hotel_name": "Vinpearl Resort Nha Trang",
                    "destination": "Nha Trang",
                    "amenities": ["pool", "spa"],
                    "expectations": ["relaxation"],
                },
            },
        },
    },
    {
        "id": "FEATURE_PARKING_DALAT",
        "category": "feature",
        "payload": {
            "intent_type": "HOTEL_FEATURE_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "TTC Hotel Da Lat co bai dau xe va tien di lai khong?",
                "features": {
                    "hotel_name": "TTC Hotel Dalat",
                    "destination": "Da Lat",
                    "amenities": ["parking", "transport"],
                    "expectations": ["city_trip"],
                },
            },
        },
    },
    {
        "id": "POLICY_CHECKIN",
        "category": "policy",
        "payload": {
            "intent_type": "HOTEL_POLICY_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Pullman Hanoi cho check-in va check-out luc may gio?",
                "features": {
                    "hotel_name": "Pullman Hanoi",
                    "destination": "Hanoi",
                    "amenities": [],
                    "expectations": ["checkin_checkout"],
                },
            },
        },
    },
    {
        "id": "POLICY_PETS",
        "category": "policy",
        "payload": {
            "intent_type": "HOTEL_POLICY_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Sheraton Hanoi co cho mang thu cung khong?",
                "features": {
                    "hotel_name": "Sheraton Hanoi",
                    "destination": "Hanoi",
                    "amenities": ["pets"],
                    "expectations": ["pet_friendly"],
                },
            },
        },
    },
    {
        "id": "POLICY_CHILDREN",
        "category": "policy",
        "payload": {
            "intent_type": "HOTEL_POLICY_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Sofitel Legend Metropole Hanoi co chinh sach tre em nhu the nao?",
                "features": {
                    "hotel_name": "Sofitel Legend Metropole Hanoi",
                    "destination": "Hanoi",
                    "amenities": [],
                    "expectations": ["children_policy", "family_trip"],
                },
            },
        },
    },
    {
        "id": "COMPARISON_FAMILY_NHATRANG",
        "category": "comparison",
        "payload": {
            "intent_type": "HOTEL_COMPARISON_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "So sanh cac lua chon resort o Nha Trang cho gia dinh co tre nho.",
                "features": {
                    "hotel_name": "",
                    "destination": "Nha Trang",
                    "amenities": ["kids_club", "pool"],
                    "expectations": ["family_trip"],
                },
            },
        },
    },
    {
        "id": "COMPARISON_LUXURY_HANOI",
        "category": "comparison",
        "payload": {
            "intent_type": "HOTEL_COMPARISON_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "So sanh Sofitel Legend Metropole Hanoi voi cac khach san luxury o Ha Noi.",
                "features": {
                    "hotel_name": "Sofitel Legend Metropole Hanoi",
                    "destination": "Hanoi",
                    "amenities": ["restaurant_food", "spa"],
                    "expectations": ["luxury_trip"],
                },
            },
        },
    },
    {
        "id": "COMPARISON_DANANG_TRANSPORT",
        "category": "comparison",
        "payload": {
            "intent_type": "HOTEL_COMPARISON_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "So sanh khach san o Da Nang co vi tri thuan tien di chuyen va gan bien.",
                "features": {
                    "hotel_name": "",
                    "destination": "Da Nang",
                    "amenities": ["transport"],
                    "expectations": ["beach_trip"],
                },
            },
        },
    },
    {
        "id": "FEATURE_ALIAS_NAME",
        "category": "entity_resolution",
        "payload": {
            "intent_type": "HOTEL_FEATURE_QA",
            "source": "RAG_SERVICE",
            "parameters": {
                "query": "Intercon Danang Sun Peninsula co phu hop nghi duong gia dinh khong?",
                "features": {
                    "hotel_name": "Intercon Danang Sun Peninsula",
                    "destination": "Da Nang",
                    "amenities": ["pool", "restaurant_food"],
                    "expectations": ["family_trip", "luxury_trip"],
                },
            },
        },
    },
]


def _compact_source(source: Any) -> dict[str, Any] | None:
    if source is None:
        return None
    if not isinstance(source, dict):
        return {"raw_type": type(source).__name__, "raw_preview": str(source)[:500]}

    results = source.get("results")
    count = source.get("count")
    compact: dict[str, Any] = {
        "success": source.get("success"),
        "source": source.get("source"),
        "count": count,
        "error": source.get("error"),
    }
    if isinstance(results, list):
        compact["sample"] = results[:2]
    elif isinstance(results, dict):
        compact["sample"] = results
    elif results is not None:
        compact["sample"] = str(results)[:1000]
    if source.get("entity_resolution"):
        compact["entity_resolution"] = source.get("entity_resolution")
    return compact


def _compact_trace(result: dict[str, Any]) -> dict[str, Any]:
    aggregated = result.get("aggregated_info")
    if isinstance(aggregated, dict):
        aggregated_trace = {
            "success": aggregated.get("success"),
            "sources_count": aggregated.get("sources_count"),
            "pass_count": aggregated.get("pass_count"),
            "error": aggregated.get("error"),
            "aggregated_preview": str(aggregated.get("aggregated_info"))[:1500],
        }
    else:
        aggregated_trace = {"raw_preview": str(aggregated)[:1500]}

    return {
        "retrieval_query": result.get("retrieval_query"),
        "plan": result.get("plan"),
        "skill_agent": result.get("skill_agent"),
        "entity_resolution": result.get("entity_resolution"),
        "sources": {
            "rag": _compact_source(result.get("rag")),
            "graph": _compact_source(result.get("graph")),
            "hotel_sql": _compact_source(result.get("hotel_sql")),
        },
        "aggregation": aggregated_trace,
    }


def _pipeline_errors(result: dict[str, Any], response: Any) -> list[str]:
    errors: list[str] = []

    if result.get("error"):
        errors.append(str(result.get("error")))

    response_text = str(response or "").lower()
    response_error_markers = [
        "error code:",
        "incorrect api key",
        "invalid_api_key",
        "tôi gặp lỗi",
        "có lỗi xảy ra",
    ]
    if any(marker in response_text for marker in response_error_markers):
        errors.append("response contains generation/API error")

    source_names = ("rag", "graph", "hotel_sql")
    evidence_count = 0
    for source_name in source_names:
        source = result.get(source_name)
        if not isinstance(source, dict):
            continue
        if source.get("error"):
            errors.append(f"{source_name}: {source.get('error')}")
        try:
            evidence_count += int(source.get("count") or 0)
        except (TypeError, ValueError):
            pass

    if evidence_count == 0:
        errors.append("no retrieval evidence returned")

    return errors


def _run_case(system: chatbot, scenario: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    payload = scenario["payload"]
    query = payload["parameters"]["query"]
    started = time.perf_counter()
    wall_started = datetime.now().isoformat(timespec="seconds")

    try:
        result = system.process(
            payload,
            enable_rag=not args.disable_rag,
            enable_graph=not args.disable_graph,
            return_detailed=True,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response = result.get("response") if isinstance(result, dict) else str(result)
        errors = _pipeline_errors(result, response) if isinstance(result, dict) else []
        record = {
            "id": scenario["id"],
            "category": scenario["category"],
            "status": "ok" if isinstance(result, dict) and not errors else "error",
            "started_at": wall_started,
            "latency_ms": latency_ms,
            "input": payload,
            "query": query,
            "response": response,
            "trace": _compact_trace(result) if isinstance(result, dict) else {},
        }
        if errors:
            record["error"] = "; ".join(errors)
        return record
    except Exception as exc:
        return {
            "id": scenario["id"],
            "category": scenario["category"],
            "status": "exception",
            "started_at": wall_started,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "input": payload,
            "query": query,
            "response": None,
            "trace": {},
            "error": str(exc),
        }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [r["latency_ms"] for r in records]
    ok_count = sum(1 for r in records if r["status"] == "ok")
    return {
        "total": len(records),
        "ok": ok_count,
        "failed": len(records) - ok_count,
        "latency_avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "latency_min_ms": min(latencies) if latencies else 0,
        "latency_max_ms": max(latencies) if latencies else 0,
        "by_status": {
            status: sum(1 for r in records if r["status"] == status)
            for status in sorted({r["status"] for r in records})
        },
    }


def _select_scenarios(args: argparse.Namespace) -> list[dict[str, Any]]:
    scenarios = SCENARIOS
    if args.case:
        wanted = {case_id.strip() for case_id in args.case.split(",") if case_id.strip()}
        scenarios = [s for s in scenarios if s["id"] in wanted]
        missing = sorted(wanted - {s["id"] for s in scenarios})
        if missing:
            raise ValueError(f"Unknown scenario id(s): {missing}")
    if args.limit is not None:
        scenarios = scenarios[: args.limit]
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--case", type=str, default="")
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--disable-rag", action="store_true")
    parser.add_argument("--disable-graph", action="store_true")
    args = parser.parse_args()

    scenarios = _select_scenarios(args)
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    output_path = (
        Path(args.output)
        if args.output
        else results_dir
        / f"structured_pipeline_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    print("=" * 80)
    print("STRUCTURED RAG PIPELINE BENCHMARK")
    print("=" * 80)
    print(f"Scenarios: {len(scenarios)}")
    print(f"Output: {output_path}")
    print()

    system = chatbot()
    records: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        print(f"[{index}/{len(scenarios)}] {scenario['id']}")
        record = _run_case(system, scenario, args)
        records.append(record)
        print(f"  status={record['status']} latency_ms={record['latency_ms']}")

    report = {
        "benchmark": "structured_rag_pipeline",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "environment": {
            "llm_provider": os.getenv("LLM_PROVIDER", ""),
            "langsmith_tracing": os.getenv("LANGSMITH_TRACING", ""),
            "langsmith_project": os.getenv("LANGSMITH_PROJECT", ""),
            "enable_rag": not args.disable_rag,
            "enable_graph": not args.disable_graph,
        },
        "summary": _summary(records),
        "results": records,
    }

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {output_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
