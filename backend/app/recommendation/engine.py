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
from typing import Any

from app.recommendation.models import MergedCandidate, RecommendInput
from app.recommendation.candidate_generation.orchestrator import generate_candidates
from app.recommendation.merge.merger import merge_candidates
from app.recommendation.rerank.reranker import rerank as rerank_candidates
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


def _build_rerank_candidate_items(merged_candidates: list[MergedCandidate]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in merged_candidates:
        item: dict[str, Any] = {
            "item_id": str(candidate.hotel_id),
            "hotel_id": candidate.hotel_id,
        }
        if candidate.hotel_name is not None:
            item["name"] = candidate.hotel_name
        item["search_score"] = candidate.pre_rank_score
        item.update(candidate.metadata or {})
        if candidate.sources:
            item["sources"] = candidate.sources
        items.append(item)
    return items


def run_rerank_from_merged(
    inp: RecommendInput,
    merged: list[MergedCandidate],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chạy rerank từ danh sách merged candidates đã có sẵn."""
    candidate_items = _build_rerank_candidate_items(merged)
    opts = dict(options or {})
    if "session_context" not in opts:
        opts["session_context"] = inp.session_context.model_dump()
    opts.setdefault("top_k", 8)

    user_context = {
        "session_context": inp.session_context.model_dump(),
        "long_term_profile": inp.profile.model_dump(),
    }

    return rerank_candidates(
        user_id=inp.user_id,
        user_context=user_context,
        candidate_items=candidate_items,
        query=inp.original_query,
        options=opts,
    )


def run_recommend_and_rerank(
    inp: RecommendInput,
    options: dict[str, Any] | None = None,
    trace: bool = False,
) -> dict[str, Any]:
    """Chạy end-to-end: candidate generation, merge và rerank."""
    merged = run_candidate_pipeline(inp, trace=trace)
    return run_rerank_from_merged(inp=inp, merged=merged, options=options)
