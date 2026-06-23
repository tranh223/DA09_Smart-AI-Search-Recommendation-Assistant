"""
REC_MERGE — Gộp candidates từ nhiều nguồn thành MergedCandidate.

Nguyên tắc:
  1. Dedup theo hotel_id — gộp sources, paths, reasons.
  2. Boost đa nguồn: hotel xuất hiện ở nhiều nguồn được cộng điểm.
  3. Tính pre_rank_score theo weighted combination trước khi sang REC_RANK.
  4. Giữ nguyên tất cả matched_paths và reasons để phục vụ explainability.

Trọng số nguồn mặc định (có thể tune):
  personalization   : 0.50
  embedding_search  : 0.50

Bonus đa nguồn:
  2 nguồn → +0.10
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.recommendation.models import CandidateHotel, MergedCandidate

logger = logging.getLogger(__name__)

# ── Weights ────────────────────────────────────────────────────────────────────
SOURCE_WEIGHTS: dict[str, float] = {
    "personalization": 0.50,
    "embedding_search": 0.50,
}

MULTI_SOURCE_BONUS: dict[int, float] = {
    2: 0.10,
}


# ── Score normalisation ────────────────────────────────────────────────────────

def _normalize_scores(candidates: list[CandidateHotel]) -> dict[str, dict[int, float]]:
    """
    Min-max normalize scores per source (0→1) để so sánh được giữa các nguồn.
    Returns {source: {hotel_id: normalized_score}}.
    """
    source_scores: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for c in candidates:
        source_scores[c.source].append((c.hotel_id, c.score))

    normalized: dict[str, dict[int, float]] = {}
    for source, items in source_scores.items():
        scores = [s for _, s in items]
        min_s, max_s = min(scores), max(scores)
        span = max_s - min_s if max_s > min_s else 1.0
        normalized[source] = {hid: (s - min_s) / span for hid, s in items}

    return normalized


# ── Public API ─────────────────────────────────────────────────────────────────

def merge_candidates(candidates: list[CandidateHotel]) -> list[MergedCandidate]:
    """
    Nhận list[CandidateHotel] từ Orchestrator → trả về list[MergedCandidate]
    đã dedup + tính pre_rank_score, sorted DESC.
    """
    if not candidates:
        return []

    normalized = _normalize_scores(candidates)

    # Gộp theo hotel_id.
    # _seen_paths / _seen_reasons dùng set để dedup O(1) thay vì O(n) list scan.
    bucket: dict[int, dict[str, Any]] = {}
    seen_paths: dict[int, set[str]] = {}
    seen_reasons: dict[int, set[str]] = {}

    for c in candidates:
        hid = c.hotel_id
        if hid not in bucket:
            bucket[hid] = {
                "hotel_id": hid,
                "hotel_name": c.hotel_name,
                "sources": [],
                "source_scores": {},
                "matched_paths": [],
                "reasons": [],
                "metadata": c.metadata.copy(),
            }
            seen_paths[hid] = set()
            seen_reasons[hid] = set()

        entry = bucket[hid]

        # Ưu tiên hotel_name không rỗng
        if not entry["hotel_name"] and c.hotel_name:
            entry["hotel_name"] = c.hotel_name

        if c.source not in entry["sources"]:
            entry["sources"].append(c.source)

        # Nếu cùng source xuất hiện nhiều lần → giữ score cao nhất
        norm_score = normalized.get(c.source, {}).get(hid, 0.0)
        if norm_score > entry["source_scores"].get(c.source, -1.0):
            entry["source_scores"][c.source] = norm_score

        for path in c.matched_paths:
            if path not in seen_paths[hid]:
                seen_paths[hid].add(path)
                entry["matched_paths"].append(path)

        if c.reason and c.reason not in seen_reasons[hid]:
            seen_reasons[hid].add(c.reason)
            entry["reasons"].append(c.reason)

        # Gộp metadata (ưu tiên giá trị không None)
        for k, v in c.metadata.items():
            if v is not None and entry["metadata"].get(k) is None:
                entry["metadata"][k] = v

    # Tính pre_rank_score
    merged: list[MergedCandidate] = []
    for hid, entry in bucket.items():
        # Weighted sum của các source
        weighted_sum = sum(
            entry["source_scores"].get(src, 0.0) * SOURCE_WEIGHTS.get(src, 0.0)
            for src in entry["sources"]
        )

        # Bonus đa nguồn
        n_sources = len(entry["sources"])
        bonus = MULTI_SOURCE_BONUS.get(n_sources, 0.0)

        pre_rank_score = min(weighted_sum + bonus, 1.0)   # cap ở 1.0

        merged.append(
            MergedCandidate(
                hotel_id=hid,
                hotel_name=entry["hotel_name"],
                sources=entry["sources"],
                source_scores=entry["source_scores"],
                matched_paths=entry["matched_paths"],
                reasons=entry["reasons"],
                pre_rank_score=pre_rank_score,
                metadata=entry["metadata"],
            )
        )

    result = sorted(merged, key=lambda m: m.pre_rank_score, reverse=True)
    logger.info(
        "[Merger] %d raw candidates → %d merged (%.0f%% dedup ratio)",
        len(candidates),
        len(result),
        (1 - len(result) / max(len(candidates), 1)) * 100,
    )
    return result
