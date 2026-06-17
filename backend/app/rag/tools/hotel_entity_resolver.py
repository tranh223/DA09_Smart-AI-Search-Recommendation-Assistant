"""Resolve imperfect hotel names to canonical hotel IDs from a small candidate set."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field
from rapidfuzz import fuzz


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
    """Resolve names using exact alias lookup followed by fuzzy reranking."""

    def __init__(
        self,
        *,
        auto_resolve_threshold: float = 75.0,
        ambiguity_margin: float = 2.0,
        max_ranked_candidates: int = 5,
    ) -> None:
        self.auto_resolve_threshold = auto_resolve_threshold
        self.ambiguity_margin = ambiguity_margin
        self.max_ranked_candidates = max_ranked_candidates
        self._alias_cache: dict[tuple[str, str], tuple[int, str]] = {}

    def resolve(
        self,
        hotel_name: str,
        candidates: Sequence[HotelCandidate | Mapping[str, Any]],
        *,
        city: str | None = None,
    ) -> HotelResolution:
        normalized_name = normalize_hotel_text(hotel_name)
        normalized_city = normalize_hotel_text(city)
        cache_key = (normalized_name, normalized_city)

        cached = self._alias_cache.get(cache_key)
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

        coerced = [
            candidate
            if isinstance(candidate, HotelCandidate)
            else HotelCandidate.model_validate(candidate)
            for candidate in candidates
        ]
        scored = sorted(
            (
                {
                    "hotel_id": candidate.hotel_id,
                    "hotel_name": candidate.hotel_name,
                    "city": candidate.city,
                    "score": self._score(hotel_name, candidate, city),
                }
                for candidate in coerced
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
            candidates=ranked,
        )
        if status == "resolved":
            self._alias_cache[cache_key] = (best["hotel_id"], best["hotel_name"])
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

        return min(best_score, 100.0)


hotel_entity_resolver = HotelEntityResolver()
