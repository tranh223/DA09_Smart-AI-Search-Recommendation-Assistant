"""test_full_system_smoke

Smoke test cho TOÀN BỘ hệ thống (end-to-end) dạng "không cần assertion chặt":
- kiểm tra pipeline chạy được
- kiểm tra output format trả về string không rỗng
- kiểm tra plan_result/skill routing/aux intent extraction có mặt khi return_detailed=True

Các trường hợp cover:
1) Query chung (INFORMATION)
2) Query có tên khách sạn cụ thể => test intent phụ trợ extract entities
3) Query so sánh/hoạt động => test truy hồi + aggregation
4) Query chính sách => test hotel_sql + policy content presence (best-effort)
5) Edge: query rỗng/whitespace

Lưu kết quả JSON vào smoke_test/results.

Chạy:
  cd smoke_test
  python test_full_system_smoke.py

"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system import get_chatbot


@dataclass
class FullSystemCase:
    id: str
    name: str
    query: str
    expect_non_empty_response: bool = True
    expect_hotel_entity_hint: bool = False


CASES: List[FullSystemCase] = [
    FullSystemCase(
        id="FS_01",
        name="General information",
        query="Khách sạn có những tiện ích gì? Có hồ bơi và spa không?",
    ),
    FullSystemCase(
        id="FS_02",
        name="Hotel name present -> auxiliary intent extraction",
        query="Trong dataset khách sạn 'Hilton Hanoi Opera' có ảnh không và có bữa sáng không?",
        expect_hotel_entity_hint=True,
    ),
    FullSystemCase(
        id="FS_03",
        name="Activities / tour relationship",
        query="Cho tôi biết khách sạn có các hoạt động/tour nào phù hợp cho gia đình ở Đà Nẵng?",
    ),
    FullSystemCase(
        id="FS_04",
        name="Policies: check-in/out",
        query="Khách sạn có chính sách check-in và check-out như thế nào?",
    ),
    FullSystemCase(
        id="FS_05",
        name="Edge: empty query",
        query="   ",
        expect_non_empty_response=False,
    ),
]


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any((k or "").lower() in t for k in keywords)


def _run_one(bot, case: FullSystemCase, user_id: str = "user_smoke_001") -> Dict[str, Any]:
    t0 = time.time()

    detailed = bot.process(
        case.query,
        return_detailed=True,
        enable_rag=True,
        enable_graph=True,
    )

    elapsed_s = time.time() - t0

    # detailed should be dict when return_detailed=True
    if isinstance(detailed, dict):
        response = detailed.get("response")
        plan = detailed.get("plan")
        skill_agent = detailed.get("skill_agent")
        aggregated_info = detailed.get("aggregated_info")
        aux_context = None
        try:
            aux_context = (plan or {}).get("context")
        except Exception:
            aux_context = None

        res_text = response or ""

        ok_response = bool(res_text.strip()) if case.expect_non_empty_response else True

        aux_hint_ok = True
        if case.expect_hotel_entity_hint:
            # Our integration injects tag into plan_result.context
            aux_hint_ok = isinstance(aux_context, str) and "[Hotel Entities Extracted]" in aux_context

        # best-effort policy/presence checks
        policy_best_effort = True
        if case.id == "FS_04" and case.expect_non_empty_response:
            policy_best_effort = _contains_any(
                res_text,
                ["check", "in", "out", "thời gian", "nhận phòng", "trả phòng"],
            )

        return {
            "case_id": case.id,
            "case_name": case.name,
            "query": case.query,
            "latency_ms": elapsed_s * 1000,
            "ok_response": ok_response,
            "aux_hint_ok": aux_hint_ok,
            "policy_best_effort_ok": policy_best_effort,
            "response_preview": res_text[:300],
            "debug": {
                "plan_keys": list(plan.keys()) if isinstance(plan, dict) else None,
                "skill_agent": skill_agent,
                "aggregated_info_keys": list(aggregated_info.keys()) if isinstance(aggregated_info, dict) else None,
            },
        }

    # If not dict, treat as error-ish
    res_text = str(detailed)
    return {
        "case_id": case.id,
        "case_name": case.name,
        "query": case.query,
        "latency_ms": elapsed_s * 1000,
        "ok_response": bool(res_text.strip()) if case.expect_non_empty_response else True,
        "aux_hint_ok": not case.expect_hotel_entity_hint,
        "response_preview": res_text[:300],
        "debug": {},
    }


def main() -> int:
    bot = get_chatbot(user_id="user_smoke_001")

    results: List[Dict[str, Any]] = []
    for case in CASES:
        print(f"Running {case.id}: {case.name}")
        try:
            r = _run_one(bot, case)
            results.append(r)
            print(
                f"  latency_ms={r.get('latency_ms'):.1f} ok_response={r.get('ok_response')} "
                f"aux_hint_ok={r.get('aux_hint_ok')}"
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

    failed = [r for r in results if not r.get("ok_response")]

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "failed_response": len(failed),
        "results": results,
    }

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"full_system_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Saved:", out_file)

    # if response empty for required cases => FAIL
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

