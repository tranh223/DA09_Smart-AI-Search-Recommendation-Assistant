"""Hotel Ask retrieval tool for the RAG pipeline.

The old local FAISS hotel chunk search has been replaced by DA10 Hotel Ask:
    GET /hotel/{hotel_id}/ask?q=...&top_k=...&sections=...

Hotel entities are resolved via vector search in Qdrant using hotel_entity_resolver.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from app.rag.tools.hotel_entity_resolver import hotel_entity_resolver
from app.utils.langsmith_tracer import tracer

# Load .env from ../backend/.env (3 levels up from backend/app/rag/tools/)
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

DEFAULT_HOTEL_ASK_BASE_URL = "https://search-api-d6vrfitoma-as.a.run.app"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
VALID_SECTIONS = {"description", "room_type", "faq", "overview", "semantic_profile"}


class HotelAskInput(BaseModel):
    """Input payload for Hotel Ask retrieval."""

    model_config = ConfigDict(strict=False)

    query: str
    hotel_ids: list[int] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    top_k: int = 5


class HotelAskChunk(BaseModel):
    """Single normalized Hotel Ask evidence chunk."""

    model_config = ConfigDict(strict=False)

    score: float = 0.0
    chunk_id: str | None = None
    section: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class HotelAskOutput(BaseModel):
    """Normalized output for one or more Hotel Ask calls."""

    model_config = ConfigDict(strict=False)

    query: str
    hotel_ids: list[int]
    chunks: list[HotelAskChunk] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class HotelAskTool:
    """Retrieve chunk evidence from the DA10 Hotel Ask API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.4,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("HOTEL_ASK_BASE_URL")
            or os.getenv("DA10_SEARCH_API_BASE_URL")
            or DEFAULT_HOTEL_ASK_BASE_URL
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "HotelAskTool":
        self._get_client()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def ask(self, payload: HotelAskInput) -> HotelAskOutput:
        """Ask Hotel Ask for every provided hotel_id and normalize chunks."""

        hotel_ids = _uniq_ints(payload.hotel_ids)
        if not payload.query.strip():
            return HotelAskOutput(query=payload.query, hotel_ids=hotel_ids)
        if not hotel_ids:
            return HotelAskOutput(
                query=payload.query,
                hotel_ids=[],
                errors=["No hotel_id resolved for Hotel Ask."],
            )

        sections = _normalize_sections(payload.sections)
        top_k = min(max(int(payload.top_k), 1), 20)
        tasks = [
            self._ask_one(hotel_id=hotel_id, query=payload.query, top_k=top_k, sections=sections)
            for hotel_id in hotel_ids
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        chunks: list[HotelAskChunk] = []
        errors: list[str] = []
        for hotel_id, response in zip(hotel_ids, responses, strict=True):
            if isinstance(response, Exception):
                errors.append(f"hotel_id={hotel_id}: {response}")
                continue
            chunks.extend(_normalize_chunks(response, hotel_id=hotel_id, query=payload.query))

        chunks.sort(key=lambda item: item.score, reverse=True)
        return HotelAskOutput(
            query=payload.query,
            hotel_ids=hotel_ids,
            chunks=chunks[:top_k],
            errors=errors,
        )

    async def _ask_one(
        self,
        *,
        hotel_id: int,
        query: str,
        top_k: int,
        sections: Sequence[str],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "top_k": top_k}
        if sections:
            params["sections"] = list(sections)
        return await self._request_json("GET", f"/hotel/{hotel_id}/ask", params=params)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._get_client()
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    headers={"accept": "application/json"},
                    timeout=self.timeout,
                )
                if response.status_code in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, dict) else {"chunks": data}
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if not self._should_retry(exc, attempt):
                    logger.exception("Hotel Ask request failed: %s %s", method, url)
                    raise

                delay = self.retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "Retrying Hotel Ask request: method=%s url=%s attempt=%s delay=%.2fs error=%s",
                    method,
                    url,
                    attempt + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Hotel Ask request failed without an exception: {method} {url}")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        return False


def _uniq_ints(values: Sequence[Any]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            continue
        if int_value in seen:
            continue
        seen.add(int_value)
        out.append(int_value)
    return out


def _normalize_sections(sections: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    for section in sections or []:
        normalized = str(section).strip()
        if normalized in VALID_SECTIONS and normalized not in out:
            out.append(normalized)
    return out


def _normalize_chunks(data: Mapping[str, Any], *, hotel_id: int, query: str) -> list[HotelAskChunk]:
    raw_chunks = data.get("chunks") or data.get("results") or []
    if not isinstance(raw_chunks, list):
        return []

    chunks: list[HotelAskChunk] = []
    for item in raw_chunks:
        if not isinstance(item, Mapping):
            continue
        content = item.get("text") or item.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            continue

        metadata = {
            "hotel_id": hotel_id,
            "query": query,
            "source": "hotel_ask",
            "source_type": item.get("source_type"),
        }
        section = item.get("section")
        if isinstance(section, str):
            metadata["section"] = section

        chunks.append(
            HotelAskChunk(
                score=_coerce_float(item.get("score")),
                chunk_id=str(item.get("chunk_id")) if item.get("chunk_id") is not None else None,
                section=section if isinstance(section, str) else None,
                content=content,
                metadata=metadata,
            )
        )
    return chunks


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_candidate_hotels_from_query(query: str) -> list[dict[str, Any]]:
    if not query:
        return []

    chunks = []
    for sep in [";", ",", "|", "\n", "\r", " và ", " với ", " cho ", " khi "]:
        if sep in query:
            chunks = [c.strip() for c in query.split(sep) if c.strip()]
            break
    if not chunks:
        chunks = [query.strip()]

    key_markers = ["khach san", "khách sạn", "resort", "hotel", "villa", "apartment", "khu nghi", "nhà nghỉ"]

    candidates: list[dict[str, Any]] = []
    for ch in chunks:
        low = ch.lower()
        if any(m in low for m in key_markers) and len(ch) >= 3:
            candidates.append({"hotel_id": -1, "hotel_name": ch, "city": None, "raw": {}})

    return candidates


def _resolve_hotel_ids_from_query(query: str, max_hotels: int = 3) -> list[int]:
    """Extract hotel IDs from query text using vector-based entity resolution."""
    try:
        candidates = _extract_candidate_hotels_from_query(query) or []
        resolved_ids: list[int] = []
        for cand in candidates:
            name = str(cand.get("hotel_name") or "").strip()
            if not name:
                continue
            resolution = hotel_entity_resolver.resolve(name, candidates=[], city=None)
            if resolution.status == "resolved" and resolution.hotel_id is not None:
                resolved_ids.append(resolution.hotel_id)
        resolved_ids = resolved_ids[:max_hotels]
        if resolved_ids:
            logger.info(f"Resolved {len(resolved_ids)} hotel IDs from query: {resolved_ids}")
        else:
            logger.debug(f"No hotel IDs resolved from query: {query[:100]}")
        return resolved_ids
    except Exception as exc:
        logger.warning(f"Hotel entity extraction failed: {exc}")
        return []


@tracer.trace("tool_rag_search")
def search_rag(
    query: str,
    top_k: int = 5,
    *,
    hotel_ids: Sequence[int] | None = None,
    sections: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Search hotel-scoped RAG evidence via Hotel Ask.

    Returns the legacy list-of-dicts shape consumed by modules/retrieval.py:
    [{score, chunk_id, section, content, metadata}, ...]
    """

    if not query or not query.strip():
        return []

    resolved_ids = _uniq_ints(list(hotel_ids or []))
    if not resolved_ids:
        resolved_ids = _resolve_hotel_ids_from_query(query)
        logger.info(f"search_rag: query={query[:80]} resolved_ids={resolved_ids}")

    async def _run() -> HotelAskOutput:
        async with HotelAskTool() as tool:
            return await tool.ask(
                HotelAskInput(
                    query=query,
                    hotel_ids=resolved_ids,
                    sections=list(sections or []),
                    top_k=top_k,
                )
            )

    try:
        asyncio.get_running_loop()
        raise RuntimeError("search_rag must be called from a synchronous context.")
    except RuntimeError as exc:
        if "synchronous context" in str(exc):
            raise
        output = asyncio.run(_run())

    if output.errors:
        logger.warning("Hotel Ask completed with errors: %s", output.errors)

    result = [chunk.model_dump() for chunk in output.chunks]
    logger.info(f"search_rag returned {len(result)} chunks")
    return result
