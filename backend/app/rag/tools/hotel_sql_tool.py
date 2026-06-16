"""Hotel SQL retrieval tool for DA10 PostgreSQL API data.

This module only resolves hotel entities and retrieves raw DA10 JSON payloads.
It does not rank, recommend, summarize, or generate natural language answers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tools.hotel_entity_resolver import (
    HotelCandidate,
    HotelResolution,
    hotel_entity_resolver,
    normalize_hotel_text,
)

load_dotenv()

logger = logging.getLogger(__name__)


DEFAULT_DA10_API_BASE_URL = "https://supabase-ota-travel.onrender.com"
DEFAULT_NEEDS = ("detail", "policies", "activities")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
API_CITY_ALIASES = {
    "ba ria vung tau": "Bà Rịa - Vũng Tàu",
    "bac giang": "Bắc Giang",
    "bac kan": "Bắc Kạn",
    "bac lieu": "Bạc Liêu",
    "bac ninh": "Bắc Ninh",
    "ben tre": "Bến Tre",
    "binh dinh": "Bình Định",
    "binh duong": "Bình Dương",
    "binh phuoc": "Bình Phước",
    "binh thuan": "Bình Thuận",
    "ca mau": "Cà Mau",
    "can tho": "Cần Thơ",
    "cao bang": "Cao Bằng",
    "da lat": "Đà Lạt",
    "da nang": "Đà Nẵng",
    "dak lak": "Đắk Lắk",
    "dak nong": "Đắk Nông",
    "dien bien": "Điện Biên",
    "dong nai": "Đồng Nai",
    "dong thap": "Đồng Tháp",
    "gia lai": "Gia Lai",
    "ha giang": "Hà Giang",
    "ha nam": "Hà Nam",
    "ha noi": "Hà Nội",
    "ha tinh": "Hà Tĩnh",
    "hai duong": "Hải Dương",
    "hai phong": "Hải Phòng",
    "hau giang": "Hậu Giang",
    "ho chi minh": "Hồ Chí Minh",
    "hoa binh": "Hòa Bình",
    "hoi an": "Hội An",
    "hue": "Huế",
    "hung yen": "Hưng Yên",
    "khanh hoa": "Khánh Hòa",
    "kien giang": "Kiên Giang",
    "kon tum": "Kon Tum",
    "lai chau": "Lai Châu",
    "lam dong": "Lâm Đồng",
    "lang son": "Lạng Sơn",
    "lao cai": "Lào Cai",
    "long an": "Long An",
    "nam dinh": "Nam Định",
    "nghe an": "Nghệ An",
    "ninh binh": "Ninh Bình",
    "ninh thuan": "Ninh Thuận",
    "phu quoc": "Phú Quốc",
    "phu tho": "Phú Thọ",
    "phu yen": "Phú Yên",
    "quang binh": "Quảng Bình",
    "quang nam": "Quảng Nam",
    "quang ngai": "Quảng Ngãi",
    "quang ninh": "Quảng Ninh",
    "quang tri": "Quảng Trị",
    "quy nhon": "Quy Nhơn",
    "sa pa": "Sa Pa",
    "sapa": "Sa Pa",
    "soc trang": "Sóc Trăng",
    "son la": "Sơn La",
    "tay ninh": "Tây Ninh",
    "thai binh": "Thái Bình",
    "thai nguyen": "Thái Nguyên",
    "thanh hoa": "Thanh Hóa",
    "tien giang": "Tiền Giang",
    "tra vinh": "Trà Vinh",
    "tuyen quang": "Tuyên Quang",
    "vinh long": "Vĩnh Long",
    "vinh phuc": "Vĩnh Phúc",
    "vung tau": "Vũng Tàu",
    "yen bai": "Yên Bái",
}


class HotelNotFoundError(Exception):
    """Raised when a hotel name cannot be resolved to a hotel_id."""


class HotelLookupInput(BaseModel):
    """Input payload for hotel SQL lookup."""

    hotel_name: str | None = None
    hotel_id: int | None = None
    city: str | None = None
    need: list[str] = Field(default_factory=lambda: list(DEFAULT_NEEDS))


class HotelLookupOutput(BaseModel):
    """Raw DA10 hotel lookup result."""

    hotel_id: int
    resolved_name: str
    detail: dict[str, Any] | None = None
    policies: dict[str, Any] | None = None
    activities: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class HotelSqlTool:
    """Resolve hotels and retrieve raw hotel data from the DA10 API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.4,
        fuzzy_match_threshold: int = 80,
        fuzzy_token_set_threshold: int = 70,
        hotel_list_limit: int = 100,
        max_hotel_list_pages: int = 100,
        resolver_candidate_limit: int = 50,
        resolver_fallback_pages: int = 5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create a hotel SQL retrieval tool.

        Args:
            base_url: DA10 API base URL. Defaults to DA10_API_BASE_URL env var.
            api_key: DA10 OTA API key. Defaults to DA10_OTA_API_KEY env var, then OTA_API_KEY.
            timeout: Per-request timeout in seconds.
            max_retries: Number of retry attempts after the first request.
            retry_backoff_seconds: Base delay for exponential retry backoff.
            fuzzy_match_threshold: Minimum RapidFuzz score for hotel name match.
            fuzzy_token_set_threshold: Minimum token overlap score to avoid false matches.
            hotel_list_limit: Page size for /api/hotels resolver calls.
            max_hotel_list_pages: Safety cap for resolver pagination.
            client: Optional injected httpx.AsyncClient for unit tests.
        """

        self.base_url = (
            base_url
            or os.getenv("DA10_API_BASE_URL")
            or DEFAULT_DA10_API_BASE_URL
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.getenv("DA10_OTA_API_KEY")
            or os.getenv("OTA_API_KEY")
            or ""
        ).strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.fuzzy_match_threshold = fuzzy_match_threshold
        self.fuzzy_token_set_threshold = fuzzy_token_set_threshold
        self.hotel_list_limit = hotel_list_limit
        self.max_hotel_list_pages = max_hotel_list_pages
        self.resolver_candidate_limit = resolver_candidate_limit
        self.resolver_fallback_pages = resolver_fallback_pages
        self._client = client
        self._owns_client = client is None
        self._local_candidates: list[dict[str, Any]] | None = None

    async def __aenter__(self) -> "HotelSqlTool":
        """Return this tool for async context-manager usage."""

        self._get_client()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the owned HTTP client when leaving an async context."""

        await self.aclose()

    async def aclose(self) -> None:
        """Close the internally managed HTTP client."""

        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def lookup(self, payload: HotelLookupInput) -> HotelLookupOutput:
        """Resolve a hotel and fetch requested raw DA10 JSON payloads.

        Args:
            payload: Hotel lookup input with hotel_name or hotel_id.

        Returns:
            Structured object containing raw JSON dictionaries for requested data.

        Raises:
            ValueError: If neither hotel_id nor hotel_name is provided.
            HotelNotFoundError: If hotel_name cannot be resolved.
            httpx.HTTPError: If resolver API calls fail after retries.
        """

        hotel_id, resolved_name = await self._resolve_hotel(payload)
        requested_needs = set(payload.need or [])
        errors: list[str] = []
        fetch_tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

        if "detail" in requested_needs:
            fetch_tasks["detail"] = asyncio.create_task(
                self._request_json("GET", f"/api/hotels/{hotel_id}")
            )
        if "policies" in requested_needs:
            fetch_tasks["policies"] = asyncio.create_task(
                self._request_json("GET", f"/api/hotels/{hotel_id}/policies")
            )
        if "activities" in requested_needs:
            fetch_tasks["activities"] = asyncio.create_task(
                self._request_json("GET", f"/api/hotels/{hotel_id}/activities")
            )

        results: dict[str, dict[str, Any] | None] = {
            "detail": None,
            "policies": None,
            "activities": None,
        }

        if fetch_tasks:
            responses = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)
            for need_name, response in zip(fetch_tasks.keys(), responses, strict=True):
                if isinstance(response, Exception):
                    error = f"{need_name}: {response}"
                    logger.warning("Hotel lookup fetch failed for hotel_id=%s: %s", hotel_id, error)
                    errors.append(error)
                    continue
                results[need_name] = response

        detail = results["detail"]
        if "policies" not in requested_needs and isinstance(detail, dict):
            detail = dict(detail)
            detail.pop("policy", None)
            detail.pop("policies", None)
        if resolved_name == str(hotel_id) and isinstance(detail, Mapping):
            resolved_name = self._extract_hotel_name(detail) or resolved_name

        return HotelLookupOutput(
            hotel_id=hotel_id,
            resolved_name=resolved_name,
            detail=detail,
            policies=results["policies"],
            activities=results["activities"],
            errors=errors,
        )

    async def _resolve_hotel(self, payload: HotelLookupInput) -> tuple[int, str]:
        """Resolve payload hotel identity to a hotel_id and display name."""

        if payload.hotel_id is not None:
            logger.info("Using provided hotel_id=%s", payload.hotel_id)
            return payload.hotel_id, payload.hotel_name or str(payload.hotel_id)

        if not payload.hotel_name:
            raise ValueError("Either hotel_id or hotel_name is required.")

        resolution = await self.resolve_hotel(payload.hotel_name, city=payload.city)
        if resolution.status != "resolved" or resolution.hotel_id is None:
            raise HotelNotFoundError(
                f"Could not uniquely resolve '{payload.hotel_name}': "
                f"status={resolution.status}, candidates={resolution.candidates[:3]}"
            )

        logger.info(
            "Resolved hotel name=%r city=%r to hotel_id=%s resolved_name=%r confidence=%.3f",
            payload.hotel_name,
            payload.city,
            resolution.hotel_id,
            resolution.canonical_name,
            resolution.confidence,
        )
        return resolution.hotel_id, resolution.canonical_name or payload.hotel_name

    async def resolve_hotel(self, hotel_name: str, *, city: str | None = None) -> HotelResolution:
        """Resolve a hotel from a bounded SQL candidate search."""

        hotels = await self._fetch_hotel_candidates(hotel_name, city=city)
        candidates: list[HotelCandidate] = []
        for hotel in hotels:
            candidate_name = self._extract_hotel_name(hotel)
            candidate_id = self._extract_hotel_id(hotel)
            if candidate_name and candidate_id is not None:
                candidates.append(
                    HotelCandidate(
                        hotel_id=candidate_id,
                        hotel_name=candidate_name,
                        city=self._extract_city(hotel),
                        raw=dict(hotel),
                    )
                )
        return hotel_entity_resolver.resolve(hotel_name, candidates, city=city)

    async def _fetch_hotel_candidates(
        self,
        hotel_name: str,
        *,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        """Ask SQL API for a bounded candidate set, then fallback for compatibility."""

        params: dict[str, str | int] = {
            "page": 1,
            "limit": self.resolver_candidate_limit,
            os.getenv("DA10_HOTEL_SEARCH_PARAM", "search"): normalize_hotel_text(hotel_name),
        }
        if city:
            params["city"] = self._api_city_value(city)
        data = await self._request_json("GET", "/api/hotels", params=params)
        candidates = self._extract_items(data)

        resolution = hotel_entity_resolver.resolve(
            hotel_name,
            [
                HotelCandidate(
                    hotel_id=hotel_id,
                    hotel_name=candidate_name,
                    city=self._extract_city(hotel),
                    raw=dict(hotel),
                )
                for hotel in candidates
                if (candidate_name := self._extract_hotel_name(hotel))
                and (hotel_id := self._extract_hotel_id(hotel)) is not None
            ],
            city=city,
        )
        if resolution.status in {"resolved", "ambiguous"}:
            return candidates

        logger.warning(
            "DA10 bounded search did not resolve hotel=%r; using paginated city fallback",
            hotel_name,
        )
        local_candidates = self._fetch_local_hotel_candidates()
        local_resolution = hotel_entity_resolver.resolve(
            hotel_name,
            [
                HotelCandidate(
                    hotel_id=hotel_id,
                    hotel_name=candidate_name,
                    city=self._extract_city(hotel),
                    raw=dict(hotel),
                )
                for hotel in local_candidates
                if (candidate_name := self._extract_hotel_name(hotel))
                and (hotel_id := self._extract_hotel_id(hotel)) is not None
            ],
            city=city,
        )
        if local_resolution.status in {"resolved", "ambiguous"}:
            return local_candidates

        page_candidates = await self._fetch_hotel_pages(
            city=city,
            max_pages=self.resolver_fallback_pages,
        )
        page_resolution = hotel_entity_resolver.resolve(
            hotel_name,
            [
                HotelCandidate(
                    hotel_id=hotel_id,
                    hotel_name=candidate_name,
                    city=self._extract_city(hotel),
                    raw=dict(hotel),
                )
                for hotel in page_candidates
                if (candidate_name := self._extract_hotel_name(hotel))
                and (hotel_id := self._extract_hotel_id(hotel)) is not None
            ],
            city=city,
        )
        if page_resolution.status in {"resolved", "ambiguous"}:
            return page_candidates

        if city:
            return await self._fetch_hotel_pages(
                city=None,
                max_pages=self.resolver_fallback_pages,
            )

        return page_candidates

    def _fetch_local_hotel_candidates(self) -> list[dict[str, Any]]:
        """Load unique hotel candidates from local FAISS metadata sidecar."""

        if self._local_candidates is not None:
            return self._local_candidates

        meta_path = Path(__file__).resolve().parents[1] / "data" / "faiss_hotels_meta.json"
        if not meta_path.exists():
            self._local_candidates = []
            return self._local_candidates

        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not load local hotel metadata for resolver: %s", exc)
            self._local_candidates = []
            return self._local_candidates

        by_id: dict[int, dict[str, Any]] = {}
        if isinstance(raw, Mapping):
            values = raw.values()
        elif isinstance(raw, list):
            values = raw
        else:
            values = []

        for item in values:
            if not isinstance(item, Mapping):
                continue
            hotel_id = self._extract_hotel_id(item)
            hotel_name = self._extract_hotel_name(item)
            if hotel_id is None or not hotel_name:
                continue
            by_id.setdefault(
                hotel_id,
                {
                    "hotel_id": hotel_id,
                    "hotel_name": hotel_name,
                    "name": hotel_name,
                },
            )

        self._local_candidates = list(by_id.values())
        logger.info("Loaded %s local hotel candidates from FAISS metadata", len(self._local_candidates))
        return self._local_candidates

    async def _fetch_hotel_list(self, *, city: str | None = None) -> list[dict[str, Any]]:
        """Fetch paginated hotel list records from DA10."""

        hotels = await self._fetch_hotel_pages(city=city)

        if city and not hotels:
            logger.warning(
                "DA10 hotel list API returned no hotels for city=%r; "
                "falling back to unfiltered hotel list.",
                city,
            )
            hotels = await self._fetch_hotel_pages(city=None)
            locally_filtered_hotels = [
                hotel for hotel in hotels if self._city_matches(hotel, city)
            ]
            if locally_filtered_hotels:
                hotels = locally_filtered_hotels

        logger.info("Fetched %s hotel candidates from DA10 hotel list API", len(hotels))
        return hotels

    async def _fetch_hotel_pages(
        self,
        *,
        city: str | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch hotel list pages, optionally using DA10 city filter."""

        hotels: list[dict[str, Any]] = []

        page_limit = max_pages or self.max_hotel_list_pages
        for page in range(1, page_limit + 1):
            params: dict[str, str | int] = {
                "page": page,
                "limit": self.hotel_list_limit,
            }
            if city:
                params["city"] = self._api_city_value(city)

            data = await self._request_json("GET", "/api/hotels", params=params)
            items = self._extract_items(data)

            if not items:
                break

            hotels.extend(items)

            if len(items) < self.hotel_list_limit:
                break

        return hotels

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an HTTP request with timeout and retry handling."""

        client = self._get_client()
        url = f"{self.base_url}{path}"
        headers = self._headers()
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, dict) else {"items": data}
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if not self._should_retry(exc, attempt):
                    logger.exception("DA10 API request failed: %s %s", method, url)
                    raise

                delay = self.retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "Retrying DA10 API request after failure: method=%s url=%s "
                    "attempt=%s delay=%.2fs error=%s",
                    method,
                    url,
                    attempt + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error

        raise RuntimeError(f"DA10 API request failed without an exception: {method} {url}")

    def _get_client(self) -> httpx.AsyncClient:
        """Return the active AsyncClient, creating it if needed."""

        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    def _headers(self) -> dict[str, str]:
        """Build DA10 API request headers."""

        headers = {"accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        """Return whether a failed request should be retried."""

        if attempt >= self.max_retries:
            return False

        if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
            return True

        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES

        return False

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        """Extract hotel list items from common paginated response shapes."""

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if not isinstance(data, Mapping):
            return []

        for key in ("items", "data", "results", "hotels"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        return []

    @staticmethod
    def _extract_hotel_name(data: Mapping[str, Any]) -> str | None:
        """Extract a hotel name from common DA10 response fields."""

        for key in ("hotel_name", "name", "title", "resolved_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        hotel = data.get("hotel")
        if isinstance(hotel, Mapping):
            return HotelSqlTool._extract_hotel_name(hotel)

        return None

    @staticmethod
    def _extract_hotel_id(data: Mapping[str, Any]) -> int | None:
        """Extract a hotel ID from common DA10 response fields."""

        for key in ("hotel_id", "id"):
            value = data.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)

        hotel = data.get("hotel")
        if isinstance(hotel, Mapping):
            return HotelSqlTool._extract_hotel_id(hotel)

        return None

    @staticmethod
    def _extract_city(data: Mapping[str, Any]) -> str | None:
        for key in ("city", "destination", "location"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        hotel = data.get("hotel")
        if isinstance(hotel, Mapping):
            return HotelSqlTool._extract_city(hotel)
        return None

    @staticmethod
    def _city_matches(data: Mapping[str, Any], city: str) -> bool:
        """Return whether a hotel record city matches the requested city."""

        value = data.get("city")
        if not isinstance(value, str):
            return False

        normalized_value = HotelSqlTool._normalize_text(value)
        normalized_city = HotelSqlTool._normalize_text(city)
        return normalized_value == normalized_city

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Normalize text for accent-insensitive exact comparisons."""

        return normalize_hotel_text(value)

    @staticmethod
    def _api_city_value(city: str) -> str:
        """Return the accented city value expected by the DA10 API."""

        normalized_city = normalize_hotel_text(city)
        return API_CITY_ALIASES.get(normalized_city, city)
