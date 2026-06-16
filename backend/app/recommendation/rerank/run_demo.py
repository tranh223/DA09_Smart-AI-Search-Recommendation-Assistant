from __future__ import annotations

import json
from pathlib import Path

try:
    from tabulate import tabulate
except ModuleNotFoundError:
    def tabulate(rows, headers, tablefmt=None):
        all_rows = [headers] + rows
        widths = [max(len(str(row[index])) for row in all_rows) for index in range(len(headers))]
        lines = []
        for row_index, row in enumerate(all_rows):
            line = " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
            lines.append(line)
            if row_index == 0:
                lines.append("-+-".join("-" * width for width in widths))
        return "\n".join(lines)

from . import rerank
from .config import load_settings, postgres_debug_info
from .postgres_candidate_store import postgres_driver_debug_info


BASE_DIR = Path(__file__).resolve().parent
DEMO_OUTPUT_PATH = BASE_DIR / "logs" / "demo_ranked_hotels.json"
DEMO_DEBUG_PATH = BASE_DIR / "logs" / "demo_rerank_debug.json"
DEMO_LLM_REQUEST_PATH = BASE_DIR / "logs" / "demo_llm_request.json"


def _parsed_llm_request(debug: dict) -> dict:
    llm_debug = debug.get("llm_debug") or {}
    request = llm_debug.get("request") or {}
    messages = request.get("messages") or []
    parsed_messages = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            try:
                item["content_json"] = json.loads(item["content"])
            except json.JSONDecodeError:
                pass
        parsed_messages.append(item)
    return {
        "model": llm_debug.get("model"),
        "source": debug.get("llm_source"),
        "reason": llm_debug.get("reason"),
        "candidate_ids": llm_debug.get("candidate_ids", []),
        "messages": parsed_messages,
    }


def main() -> None:
    request = json.loads((BASE_DIR / "data" / "example_request.json").read_text(encoding="utf-8"))
    options = dict(request.get("options", {}))
    if request.get("session_context"):
        options["session_context"] = request["session_context"]
    candidate_items = request.get("candidate_items", [])
    settings = load_settings()
    print(f"Postgres config: {json.dumps(postgres_debug_info(settings.postgres_dsn), ensure_ascii=False)}")
    print(f"Postgres driver: {json.dumps(postgres_driver_debug_info(), ensure_ascii=False)}")
    print(f"Postgres enrichment enabled: {bool(options.get('enrich_postgres_candidates'))}")
    print("Candidate source: request_json")
    result = rerank(
        user_id=request.get("user_id"),
        user_context=request.get("user_context"),
        candidate_items=candidate_items,
        query=request.get("query"),
        options=options,
    )
    debug = result.get("debug", {})
    if debug.get("candidate_source"):
        print(f"Rerank candidate source: {debug.get('candidate_source')}")
    enrich_debug = debug.get("candidate_enrichment_debug") or {}
    if enrich_debug.get("requested"):
        print(f"Postgres enrich: {json.dumps(enrich_debug, ensure_ascii=False)}")
    print(f"Loaded user profile source: {debug.get('profile_source', 'unknown')}")
    print(f"Loaded booking source: {debug.get('booking_source', 'unknown')}")
    print(f"Candidates: {debug.get('total_candidates', 0)} total, {debug.get('after_hard_filter', 0)} after hard filter")
    session = debug.get("normalized_session") or {}
    if session:
        print(f"Session destination: {session.get('destination') or 'unknown'}")
    print(f"LLM source: {debug.get('llm_source', 'unknown')}")
    llm_debug = debug.get("llm_debug") or {}
    if llm_debug:
        print(f"LLM fallback reason: {llm_debug.get('reason') or 'none'}")
        print(f"LLM candidate IDs: {', '.join(llm_debug.get('candidate_ids', []))}")
        attempts = llm_debug.get("attempts") or []
        if attempts:
            print(f"LLM attempts: {json.dumps(attempts, ensure_ascii=False)}")
        validated = llm_debug.get("validated") or {}
        print(f"LLM valid IDs: {', '.join(validated.get('valid_item_ids', [])) or 'none'}")
        rejected = validated.get("rejected_items", [])
        if rejected:
            print(f"LLM rejected items: {json.dumps(rejected, ensure_ascii=False)}")
    filtered_items = debug.get("filtered_items") or []
    if filtered_items:
        print("Filtered items:")
        for item in filtered_items:
            print(
                "  - "
                f"{item.get('item_id')} {item.get('name') or ''}: {item.get('reason')}"
                f" (destination={item.get('destination')}, available={item.get('available')}, "
                f"price={item.get('price_min')}-{item.get('price_max')})"
            )
    print()

    rows = []
    for item in result["ranked_items"]:
        features = item["feature_scores"]
        rows.append(
            [
                item["rank"],
                item["item_id"],
                item.get("name", ""),
                item["final_score"],
                item["base_score"],
                item["llm_score"],
                features.get("trend"),
                features.get("room_view"),
            ]
        )
    print("Top ranked hotels")
    print(tabulate(rows, headers=["Rank", "ID", "Name", "Final", "Base", "LLM", "Trend", "Room view"], tablefmt="github"))
    print(f"Ranked hotel JSON items: {len(result.get('ranked_hotels', []))}")
    print()

    for item in result["ranked_items"]:
        print(f"#{item['rank']} {item.get('name', item['item_id'])} ({item['item_id']})")
        print(f"  final_score={item['final_score']} base_score={item['base_score']} llm_score={item['llm_score']}")
        for reason in item.get("reasons", []):
            print(f"  - {reason}")
        for warning in item.get("warnings", []):
            print(f"  ! {warning}")
        print()

    ranked_hotels = result.get("ranked_hotels", [])
    DEMO_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_OUTPUT_PATH.write_text(json.dumps(ranked_hotels, ensure_ascii=False, indent=2), encoding="utf-8")
    DEMO_DEBUG_PATH.write_text(
        json.dumps(
            {
                "request_summary": {
                    "user_id": request.get("user_id"),
                    "query": request.get("query"),
                    "candidate_count": len(candidate_items),
                    "options": options,
                },
                "debug": debug,
                "ranked_items": result.get("ranked_items", []),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    DEMO_LLM_REQUEST_PATH.write_text(
        json.dumps(_parsed_llm_request(debug), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Ranked hotel JSON saved: {DEMO_OUTPUT_PATH}")
    print(f"Rerank debug JSON saved: {DEMO_DEBUG_PATH}")
    print(f"LLM request JSON saved: {DEMO_LLM_REQUEST_PATH}")
    print(f"Ranked hotel IDs: {', '.join(item.get('item_id', '') for item in ranked_hotels) or 'none'}")


if __name__ == "__main__":
    main()
