"""
Recommendation Engine — Entry Point

Sơ đồ:
  RecommendInput
       │
       ▼
  Orchestrator (quyết định nguồn)
  ┌────┬──────────────┬─────────────────────┐
  │    │              │                     │
  ▼    ▼              ▼                     ▼
EMBED TOP           PERSONALIZATION
SEARCH TRENDING      (Neo4j unified template)
(Qdrant)  (MongoDB)
  │    │              │
  └────┴──────────────┘
              │
              ▼
          REC_MERGE
        (MergedCandidate[])
              │
              ▼
       → sang REC_RANK (module riêng)
"""

from __future__ import annotations
import logging

from app.recommendation.models import RecommendInput, MergedCandidate
from app.recommendation.candidate_generation.orchestrator import generate_candidates
from app.recommendation.merge.merger import merge_candidates
from app.recommendation.trace import RecommendTrace, trace_intent_input

logger = logging.getLogger(__name__)


def run_candidate_pipeline(
    inp: RecommendInput,
    trace: bool = False,
) -> list[MergedCandidate]:
    """
    Chạy toàn bộ Candidate Generation → Merge.
    trace=True → in chi tiết từng bước ra console.
    """
    tracer = RecommendTrace(enabled=trace)

    if trace:
        trace_intent_input(inp, tracer)

    logger.info(
        "[Engine] Start | user=%s | city=%s | query='%s'",
        inp.user_id,
        inp.session_context.destination,
        inp.original_query[:60],
    )

    raw_candidates = generate_candidates(inp, trace=tracer if trace else None)
    logger.info("[Engine] Tổng raw candidates: %d", len(raw_candidates))

    if trace:
        by_source: dict[str, int] = {}
        for c in raw_candidates:
            by_source[c.source] = by_source.get(c.source, 0) + 1
        tracer.section("⑥ REC_MERGE")
        tracer.step("raw candidates theo nguồn", by_source)
        tracer.step("tổng raw (có trùng hotel_id)", len(raw_candidates))

    merged = merge_candidates(raw_candidates)
    logger.info("[Engine] Sau merge: %d unique hotels", len(merged))

    if trace:
        tracer.step("sau dedup", len(merged))
        tracer.merged(merged)

    return merged
