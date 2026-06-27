"""Resolve hotel names to canonical hotel IDs.

Updated behavior (per task):
- Primary retrieval uses **vector search in Qdrant** over the hotels collection.
- Optional lightweight normalization + fuzzy reranking can be applied on the returned
  candidate set.

This module keeps the original public API (`hotel_entity_resolver.resolve(...)`)
so upstream code doesn't need to change.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.db.vector_store.qdrant_store import get_qdrant_store
from app.utils.embedder import get_embedder



LOW_VALUE_TOKENS = {
    "hotel",
    "khach",
    "san",
    "resort",
    "khu",
    "nghi",
    "duong",
    "spa",
    "apartment",
    "apartments",
    "villa",
}

TEXT_ALIASES = {
    "cantho": "can tho",
    "dalat": "da lat",
    "danang": "da nang",
    "hanoi": "ha noi",
    "hochiminh": "ho chi minh",
    "nhatrang": "nha trang",
    "phuquoc": "phu quoc",
}


def normalize_hotel_text(value: str | None) -> str:
    """Normalize accents, punctuation, and spacing for entity matching."""

    text = (value or "").strip().lower().replace("đ", "d")
    normalized = unicodedata.normalize("NFD", text)
    ascii_text = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()
    tokens = [TEXT_ALIASES.get(token, token) for token in cleaned.split()]
    return " ".join(tokens)


def _important_tokens(value: str) -> set[str]:
    tokens = set(normalize_hotel_text(value).split())
    important = tokens - LOW_VALUE_TOKENS
    return important or tokens


def _name_aliases(value: str) -> list[str]:
    """Return full name plus common aliases embedded in parentheses."""

    aliases = [value]
    aliases.extend(match.strip() for match in re.findall(r"\(([^)]+)\)", value) if match.strip())
    return list(dict.fromkeys(aliases))


class HotelCandidate(BaseModel):
    hotel_id: int
    hotel_name: str
    city: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class HotelResolution(BaseModel):
    status: str
    input_name: str
    input_city: str | None = None
    hotel_id: int | None = None
    canonical_name: str | None = None
    matched_alias: str | None = None
    confidence: float = 0.0
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class HotelEntityResolver:
    """Resolve hotel names using vector search + fuzzy reranking."""

    def __init__(
        self,
        *,
        auto_resolve_threshold: float = 75.0,
        ambiguity_margin: float = 2.0,
        max_ranked_candidates: int = 5,
        vector_limit: int = 12,
    ) -> None:
        self.auto_resolve_threshold = auto_resolve_threshold
        self.ambiguity_margin = ambiguity_margin
        self.max_ranked_candidates = max_ranked_candidates
        self.vector_limit = vector_limit

        # Cache embeddings for repeated names in a single process.
        self._resolved_cache: dict[tuple[str, str | None], tuple[int, str]] = {}

    def resolve(
        self,
        hotel_name: str,
        candidates: Sequence[HotelCandidate | Mapping[str, Any]],
        *,
        city: str | None = None,
    ) -> HotelResolution:
        """Resolve an input hotel name to a canonical hotel.

        `candidates` is kept for backwards compatibility with older call sites, but
        it is no longer required for correctness: Qdrant becomes the primary source.
        """

        normalized_name = normalize_hotel_text(hotel_name)
        normalized_city = normalize_hotel_text(city)

        cache_key = (normalized_name, normalized_city or None)
        cached = self._resolved_cache.get(cache_key)
        if cached:
            return HotelResolution(
                status="resolved",
                input_name=hotel_name,
                input_city=city,
                hotel_id=cached[0],
                canonical_name=cached[1],
                matched_alias=hotel_name,
                confidence=1.0,
            )

        # 1) Vector retrieval from Qdrant
        embedder = get_embedder()
        qdrant = get_qdrant_store()

        query_vector = embedder.encode_one(hotel_name, is_query=True)

        qdrant_hits = qdrant.search_hotels(
            query_vector,
            city=city,
            limit=self.vector_limit,
            score_threshold=None,
        )

        vec_candidates: list[HotelCandidate] = []
        for hit in qdrant_hits or []:
            hotel_id = hit.get("hotel_id")
            hotel_name_out = hit.get("hotel_name")
            hit_city = hit.get("city_name")
            if hotel_id is None or hotel_name_out is None:
                continue
            vec_candidates.append(
                HotelCandidate(
                    hotel_id=int(hotel_id),
                    hotel_name=str(hotel_name_out),
                    city=str(hit_city) if hit_city else None,
                    raw=hit.get("payload") or hit,
                )
            )

        # 2) Fallback: if Qdrant returns nothing, use provided candidates.
        if not vec_candidates:
            coerced: list[HotelCandidate] = []
            for candidate in candidates:
                coerced.append(
                    candidate
                    if isinstance(candidate, HotelCandidate)
                    else HotelCandidate.model_validate(candidate)
                )
            vec_candidates = coerced

        if not vec_candidates:
            return HotelResolution(
                status="not_found",
                input_name=hotel_name,
                input_city=city,
                candidates=[],
            )

        # 3) Fuzzy reranking among vector candidates
        scored = sorted(
            (
                {
                    "hotel_id": c.hotel_id,
                    "hotel_name": c.hotel_name,
                    "city": c.city,
                    "score": self._score(hotel_name, c, city),
                    "raw": c.raw,
                }
                for c in vec_candidates
            ),
            key=lambda item: item["score"],
            reverse=True,
        )

        ranked = scored[: self.max_ranked_candidates]
        if not ranked:
            return HotelResolution(
                status="not_found",
                input_name=hotel_name,
                input_city=city,
            )

        best = ranked[0]
        runner_up_score = ranked[1]["score"] if len(ranked) > 1 else 0.0
        margin = best["score"] - runner_up_score

        if best["score"] < self.auto_resolve_threshold:
            status = "not_found"
        elif len(ranked) > 1 and margin < self.ambiguity_margin:
            status = "ambiguous"
        else:
            status = "resolved"

        resolution = HotelResolution(
            status=status,
            input_name=hotel_name,
            input_city=city,
            hotel_id=best["hotel_id"] if status == "resolved" else None,
            canonical_name=best["hotel_name"] if status == "resolved" else None,
            matched_alias=hotel_name if status == "resolved" else None,
            confidence=round(best["score"] / 100.0, 4),
            candidates=[
                {
                    "hotel_id": item["hotel_id"],
                    "hotel_name": item["hotel_name"],
                    "city": item["city"],
                    "score": item["score"],
                    "raw": item.get("raw") or {},
                }
                for item in ranked
            ],
        )

        if status == "resolved":
            self._resolved_cache[cache_key] = (best["hotel_id"], best["hotel_name"])

        return resolution

    @staticmethod
    def _score(
        input_name: str,
        candidate: HotelCandidate,
        input_city: str | None,
    ) -> float:
        normalized_input = normalize_hotel_text(input_name)
        input_tokens = _important_tokens(input_name)

        destination_match = (
            1.0
            if input_city
            and candidate.city
            and normalize_hotel_text(input_city) == normalize_hotel_text(candidate.city)
            else 0.0
        )

        best_score = 0.0
        for alias in _name_aliases(candidate.hotel_name):
            normalized_candidate = normalize_hotel_text(alias)
            candidate_tokens = _important_tokens(alias)
            coverage = (
                len(input_tokens & candidate_tokens) / len(input_tokens)
                if input_tokens
                else 0.0
            )

            score = (
                0.35 * fuzz.WRatio(normalized_input, normalized_candidate)
                + 0.25 * fuzz.token_set_ratio(normalized_input, normalized_candidate)
                + 0.20 * fuzz.token_sort_ratio(normalized_input, normalized_candidate)
                + 15.0 * coverage
                + 5.0 * destination_match
            )

            compact_input = normalized_input.replace(" ", "")
            compact_candidate = normalized_candidate.replace(" ", "")

            if input_tokens and input_tokens == candidate_tokens:
                score = max(score, 98.0 + 2.0 * destination_match)
            elif compact_input and compact_input in compact_candidate:
                score = max(score, 92.0 + 5.0 * destination_match)

            best_score = max(best_score, score)

        return float(min(best_score, 100.0))


hotel_entity_resolver = HotelEntityResolver()

