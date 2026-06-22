"""
RecommendTrace — trace helper cho Candidate Generation pipeline.

Thay thế toàn bộ lệnh print() bằng structured logging:
  ota.trace.rec   — detail từng bước recommendation (INFO)
  ota.flow        — summary ngắn trên console (DEBUG)

Nếu có FlowTrace contextvar, các bước được tự động ghi vào span
"recommend" (nếu đang active) qua sub_spans.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.recommendation.models import CandidateHotel, MergedCandidate, RecommendInput
from app.core.trace import current_trace, Span

_rec_log = logging.getLogger("ota.trace.rec")
_flow_log = logging.getLogger("ota.flow")


class RecommendTrace:
    """
    Trace helper cho recommendation pipeline.
    enabled=True  → ghi log chi tiết (được bật trong nodes.py khi có FlowTrace).
    enabled=False → no-op (production parallel mode).
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._step = 0
        self._current_section: str = ""

    # ── API ──────────────────────────────────────────────────────────────────

    def section(self, title: str) -> None:
        if not self.enabled:
            return
        self._current_section = title
        _rec_log.info("=== %s ===", title)

    def step(self, message: str, data: Any = None) -> None:
        if not self.enabled:
            return
        self._step += 1
        if data is None:
            _rec_log.info("  [%d] %s", self._step, message)
        else:
            try:
                data_str = json.dumps(data, ensure_ascii=False, default=str)
            except Exception:  # noqa: BLE001
                data_str = str(data)
            _rec_log.info("  [%d] %s: %s", self._step, message, data_str)

    def info(self, message: str) -> None:
        if not self.enabled:
            return
        _rec_log.info("      %s", message)

    def candidates(self, source: str, items: list[CandidateHotel], max_show: int = 5) -> None:
        if not self.enabled:
            return
        _rec_log.info("  >> %s: %d candidate(s)", source, len(items))
        for i, c in enumerate(items[:max_show], 1):
            _rec_log.info(
                "     %d. [%s] %s  score=%.4f  %s",
                i, c.hotel_id, c.hotel_name or "?", c.score,
                c.reason[:100] if c.reason else "-",
            )
            if c.metadata.get("strategy"):
                _rec_log.info("        strategy=%s", c.metadata["strategy"])
        if len(items) > max_show:
            _rec_log.info("     ... +%d nữa", len(items) - max_show)

        # Ghi vào FlowTrace span nếu đang active
        trace = current_trace()
        if trace:
            span = _find_or_create_sub(trace, source)
            span.add(
                count=len(items),
                top=[
                    {
                        "hotel_id": c.hotel_id,
                        "name": c.hotel_name,
                        "score": round(c.score, 4),
                        "reason": c.reason[:100] if c.reason else "",
                    }
                    for c in items[:max_show]
                ],
            )

    def merged(self, items: list[MergedCandidate], max_show: int | None = None) -> None:
        if not self.enabled:
            return
        limit = len(items) if max_show is None else max_show
        _rec_log.info("  >> MERGE: %d unique hotel(s)", len(items))
        for i, m in enumerate(items[:limit], 1):
            _rec_log.info(
                "     %d. [%s] %s  sources=%s  pre_rank=%.4f",
                i, m.hotel_id, m.hotel_name or "?", m.sources, m.pre_rank_score,
            )
            _rec_log.info("        src_scores=%s", m.source_scores)
        if max_show is not None and len(items) > limit:
            _rec_log.info("     ... +%d nữa", len(items) - limit)


def _find_or_create_sub(trace: Any, name: str) -> "Span":
    """Tìm span 'recommend' đang active và tạo sub-span trong đó."""
    from app.core.trace import Span as _Span
    for span in reversed(trace.spans):
        if span.name == "recommend":
            return span.sub(name)
    # Nếu không tìm thấy span recommend, tạo span mới trực tiếp
    return trace.begin(name)


def trace_intent_input(inp: RecommendInput, trace: "RecommendTrace") -> None:
    """Log RecommendInput detail ở đầu pipeline."""
    trace.section("① INTENT INPUT → RecommendInput")
    trace.step("user_id", inp.user_id)
    trace.step(
        "session_context",
        {
            "destination": inp.session_context.destination,
            "nearby_place": inp.session_context.nearby_place,
            "check_in": inp.session_context.check_in,
            "check_out": inp.session_context.check_out,
            "price_range": inp.session_context.session_price_range.model_dump(),
        },
    )
    trace.step(
        "profile",
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
