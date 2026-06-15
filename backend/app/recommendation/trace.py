"""
Trace helper — in chi tiết từng bước pipeline recommend ra console.
Bật bằng: run_candidate_pipeline(inp, trace=True)
"""

from __future__ import annotations
import json
from typing import Any

from app.recommendation.models import CandidateHotel, MergedCandidate, RecommendInput


class RecommendTrace:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._step = 0

    def section(self, title: str) -> None:
        if not self.enabled:
            return
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print("=" * 60)

    def step(self, message: str, data: Any = None) -> None:
        if not self.enabled:
            return
        self._step += 1
        print(f"\n  [{self._step}] {message}")
        if data is not None:
            print(_format_data(data))

    def info(self, message: str) -> None:
        if not self.enabled:
            return
        print(f"       {message}")

    def candidates(self, source: str, items: list[CandidateHotel], max_show: int = 5) -> None:
        if not self.enabled:
            return
        print(f"\n  >> {source}: {len(items)} candidate(s)")
        for i, c in enumerate(items[:max_show], 1):
            print(f"     {i}. [{c.hotel_id}] {c.hotel_name or '?'}")
            print(f"        score={c.score:.4f} | {c.reason[:80] if c.reason else '-'}")
            if c.metadata.get("strategy"):
                print(f"        strategy={c.metadata['strategy']}")
        if len(items) > max_show:
            print(f"     ... +{len(items) - max_show} nữa")

    def merged(self, items: list[MergedCandidate], max_show: int | None = None) -> None:
        if not self.enabled:
            return
        show_all = max_show is None
        limit = len(items) if show_all else max_show
        print(f"\n  >> MERGE: {len(items)} unique hotel(s)")
        for i, m in enumerate(items[:limit], 1):
            print(f"     {i}. [{m.hotel_id}] {m.hotel_name or '?'}")
            print(f"        sources={m.sources} | pre_rank={m.pre_rank_score:.4f}")
            print(f"        src_scores={m.source_scores}")
        if not show_all and len(items) > limit:
            print(f"     ... +{len(items) - limit} nữa")


def trace_intent_input(inp: RecommendInput, trace: RecommendTrace) -> None:
    trace.section("① INTENT INPUT → RecommendInput")
    trace.step("user_id", inp.user_id)
    trace.step(
        "session_context",
        {
            "destination": inp.session_context.destination,
            "nearby_place": inp.session_context.nearby_place,
            "check_in": inp.session_context.check_in,
            "check_out": inp.session_context.check_out,
            "session_price_range": inp.session_context.session_price_range.model_dump(),
        },
    )
    trace.step(
        "profile (tóm tắt)",
        {
            "nationality": inp.profile.nationality,
            "age_group": inp.profile.age_group,
            "trip_types": list(inp.profile.long_term_trip_types.keys()),
            "budget_levels": list(inp.profile.long_term_budget_levels.keys()),
            "preference_habits": list(inp.profile.long_term_preference_habits.keys()),
            "room_views": list(inp.profile.long_term_room_views.keys()),
            "amenities": list(inp.profile.long_term_amenities.keys()),
        },
    )
    trace.step("original_query", inp.original_query)
    trace.step("limit_per_source", inp.limit_per_source)


def _format_data(data: Any) -> str:
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False, indent=8, default=str)
    return f"        {data}"
