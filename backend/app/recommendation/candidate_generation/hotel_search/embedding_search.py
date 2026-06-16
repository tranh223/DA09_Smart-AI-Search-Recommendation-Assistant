"""
Hybrid hotel search — tất cả retrieval trong một module:
  - Dense: BGE-M3 + Qdrant (cosine ANN)
  - Keyword: BM25 (rank_bm25)
  - Fusion: Reciprocal Rank Fusion (RRF)
"""

from __future__ import annotations

import logging
import os
import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.db.vector_store.qdrant_store import get_qdrant_store
from app.recommendation.candidate_generation.hotel_search.slots import extract_slots
from app.recommendation.embedding.bge_embedder import get_embedder
from app.recommendation.models import CandidateHotel, RecommendInput
from app.recommendation.trace import RecommendTrace

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_BM25_INDEX_PATH = Path(
    os.getenv(
        "BM25_INDEX_PATH",
        str(PROJECT_ROOT / "data" / "embeddings" / "hotel_bm25.pkl"),
    )
)

RETRIEVAL_OVERSAMPLE = 2
RRF_K = 60


# ── Query text ────────────────────────────────────────────────────────────────

def _build_query_text(inp: RecommendInput, slots: dict[str, Any]) -> str:
    parts = [inp.original_query] if inp.original_query else []
    city = slots.get("city")
    if city:
        parts.append(f"thành phố {city}")
    if slots.get("nearby_place"):
        parts.append(f"gần {slots['nearby_place']}")
    if slots.get("max_price"):
        parts.append(f"ngân sách tối đa {int(slots['max_price'])} VND")
    tags = slots.get("tags") or []
    if tags:
        parts.append("sở thích: " + ", ".join(tags[:10]))
    return ". ".join(parts)


# ── BM25 keyword search ───────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def hotel_document_text(hotel: dict) -> str:
    """Text corpus cho BM25 — dùng khi build index offline."""
    tag_names = [t["tag_id"].split("::", 1)[-1] for t in hotel.get("tags", [])]
    parts = [hotel.get("hotel_name") or "", hotel.get("city_name") or "", *tag_names]
    return " ".join(p for p in parts if p).strip()


class HotelBM25Index:
    def __init__(
        self,
        bm25: BM25Okapi,
        hotel_ids: list[int],
        metadata: dict[int, dict],
    ):
        self.bm25 = bm25
        self.hotel_ids = hotel_ids
        self.metadata = metadata
        self._city_to_indices: dict[str, list[int]] = {}

    @classmethod
    def build(cls, hotels: dict[int, dict]) -> HotelBM25Index:
        hotel_ids = list(hotels.keys())
        corpus = [_tokenize(hotel_document_text(hotels[hid])) for hid in hotel_ids]
        metadata = {
            hid: {
                "hotel_id": hid,
                "hotel_name": hotels[hid].get("hotel_name"),
                "city_name": hotels[hid].get("city_name"),
                "tags": hotels[hid].get("tags", []),
            }
            for hid in hotel_ids
        }
        index = cls(bm25=BM25Okapi(corpus), hotel_ids=hotel_ids, metadata=metadata)
        index._build_city_index()
        return index

    def save(self, path: Path | str = DEFAULT_BM25_INDEX_PATH) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(
                {"bm25": self.bm25, "hotel_ids": self.hotel_ids, "metadata": self.metadata},
                f,
            )
        logger.info("Saved BM25 index → %s (%d hotels)", path, len(self.hotel_ids))

    @classmethod
    def load(cls, path: Path | str = DEFAULT_BM25_INDEX_PATH) -> HotelBM25Index:
        path = Path(path)
        with path.open("rb") as f:
            data = pickle.load(f)
        index = cls(bm25=data["bm25"], hotel_ids=data["hotel_ids"], metadata=data["metadata"])
        index._build_city_index()
        return index

    def _build_city_index(self) -> None:
        self._city_to_indices = {}
        for idx, hid in enumerate(self.hotel_ids):
            city = (self.metadata[hid].get("city_name") or "").strip()
            if city:
                self._city_to_indices.setdefault(city, []).append(idx)

    def search(self, query: str, *, city: str | None = None, limit: int = 10) -> list[dict]:
        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        indices = self._city_to_indices.get(city, []) if city else list(range(len(self.hotel_ids)))

        ranked = [(idx, float(scores[idx])) for idx in indices if float(scores[idx]) > 0]
        ranked.sort(key=lambda x: x[1], reverse=True)

        hits: list[dict] = []
        for idx, score in ranked[:limit]:
            hid = self.hotel_ids[idx]
            meta = self.metadata[hid]
            hits.append(
                {
                    "hotel_id": hid,
                    "hotel_name": meta.get("hotel_name"),
                    "city_name": meta.get("city_name"),
                    "score": score,
                    "tags": meta.get("tags", []),
                    "retrieval": "bm25",
                }
            )
        return hits


@lru_cache(maxsize=1)
def _get_bm25_index() -> HotelBM25Index | None:
    path = DEFAULT_BM25_INDEX_PATH
    if not path.exists():
        logger.warning("[BM25] Index not found: %s", path)
        return None
    try:
        return HotelBM25Index.load(path)
    except Exception as exc:
        logger.warning("[BM25] Failed to load index: %s", exc)
        return None


# ── RRF fusion ────────────────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    *result_lists: list[dict],
    limit: int = 10,
    k: int = RRF_K,
) -> list[dict]:
    rrf_scores: dict[int, float] = {}
    meta: dict[int, dict] = {}

    for hits in result_lists:
        for rank, hit in enumerate(hits):
            hid = int(hit["hotel_id"])
            rrf_scores[hid] = rrf_scores.get(hid, 0.0) + 1.0 / (k + rank + 1)
            if hid not in meta:
                meta[hid] = hit.copy()

    sorted_ids = sorted(rrf_scores, key=lambda h: rrf_scores[h], reverse=True)[:limit]
    fused: list[dict] = []
    for hid in sorted_ids:
        row = meta[hid].copy()
        row["score"] = rrf_scores[hid]
        row["fusion"] = "rrf"
        fused.append(row)
    return fused


# ── Dense search (BGE-M3 + Qdrant) ────────────────────────────────────────────

def _dense_search(query_text: str, city: str, limit: int) -> list[dict]:
    embedder = get_embedder()
    store = get_qdrant_store()
    query_vec = embedder.encode_one(query_text, is_query=True)
    hits = store.search_hotels(query_vec, city=city, limit=limit)
    for h in hits:
        h["retrieval"] = "dense"
    return hits


# ── Candidates mapping ────────────────────────────────────────────────────────

def _hits_to_candidates(hits: list[dict]) -> list[CandidateHotel]:
    candidates: list[CandidateHotel] = []
    for hit in hits:
        tag_names = [t.get("tag_id", "").split("::", 1)[-1] for t in hit.get("tags", [])]
        retrieval = hit.get("retrieval") or hit.get("fusion") or "hybrid"
        candidates.append(
            CandidateHotel(
                hotel_id=int(hit["hotel_id"]),
                hotel_name=hit.get("hotel_name"),
                source="embedding_search",
                score=float(hit["score"]),
                matched_paths=[f"Tag({n})" for n in tag_names[:5]],
                reason=f"{retrieval} match ({hit['score']:.3f}) | {hit.get('city_name', '')}",
                metadata={
                    "strategy": "hybrid_bge_m3_bm25",
                    "city": hit.get("city_name"),
                    "tags": hit.get("tags", []),
                    "retrieval": retrieval,
                },
            )
        )
    return candidates


# ── Public API ────────────────────────────────────────────────────────────────

def get_embedding_search_candidates(
    inp: RecommendInput,
    trace: RecommendTrace | None = None,
) -> list[CandidateHotel]:
    slots = extract_slots(inp)
    city = slots.get("city") or ""

    if trace and trace.enabled:
        trace.step("slots trích xuất từ profile + session", slots)

    if not city:
        if trace and trace.enabled:
            trace.info("Thiếu city → bỏ qua embedding_search")
        logger.info("[EmbeddingSearch] Không có city → bỏ qua.")
        return []

    query_text = _build_query_text(inp, slots)
    fetch_limit = inp.limit_per_source * RETRIEVAL_OVERSAMPLE

    dense_hits: list[dict] = []
    bm25_hits: list[dict] = []

    try:
        dense_hits = _dense_search(query_text, city, fetch_limit)
        if trace and trace.enabled:
            trace.step("Dense search (BGE-M3 + Qdrant)", {"hits": len(dense_hits), "city": city})
    except Exception as exc:
        logger.warning("[EmbeddingSearch] Dense retrieval lỗi: %s", exc)
        if trace and trace.enabled:
            trace.info(f"Dense lỗi: {exc}")

    bm25_index = _get_bm25_index()
    if bm25_index is not None:
        try:
            bm25_hits = bm25_index.search(query_text, city=city, limit=fetch_limit)
            if trace and trace.enabled:
                trace.step("Keyword search (BM25)", {"hits": len(bm25_hits), "city": city})
        except Exception as exc:
            logger.warning("[EmbeddingSearch] BM25 retrieval lỗi: %s", exc)
            if trace and trace.enabled:
                trace.info(f"BM25 lỗi: {exc}")
    elif trace and trace.enabled:
        trace.info("BM25 index chưa có → chỉ dùng dense search")

    if dense_hits and bm25_hits:
        fused = _reciprocal_rank_fusion(dense_hits, bm25_hits, limit=inp.limit_per_source)
        if trace and trace.enabled:
            trace.info(f"RRF fusion → {len(fused)} hotel(s)")
    elif dense_hits:
        fused = dense_hits[: inp.limit_per_source]
    elif bm25_hits:
        fused = bm25_hits[: inp.limit_per_source]
    else:
        fused = []

    candidates = _hits_to_candidates(fused)
    logger.info(
        "[EmbeddingSearch] Trả về %d candidates tại %s (dense=%d, bm25=%d).",
        len(candidates),
        city,
        len(dense_hits),
        len(bm25_hits),
    )
    return candidates
