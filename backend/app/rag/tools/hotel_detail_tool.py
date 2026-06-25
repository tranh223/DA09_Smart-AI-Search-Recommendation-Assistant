"""Hotel detail API client for description-only evidence.

This tool is used when the user asks for detailed information about a
specific hotel. It calls the hotel detail endpoint by hotel_id and keeps only
the `description` field from the raw response.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

import requests
from dotenv import load_dotenv

from utils.logger import get_logger


load_dotenv()

logger = get_logger(__name__)

DEFAULT_HOTEL_DETAIL_BASE_URL = "https://supabase-ota-travel.onrender.com/api/hotels"
DEFAULT_TIMEOUT_SECONDS = 12.0
DEFAULT_MAX_DESCRIPTION_CHARS = 12000


def fetch_hotel_description(
    hotel_id: int,
    *,
    timeout_seconds: float | None = None,
    max_description_chars: int | None = None,
) -> dict[str, Any]:
    """Fetch one hotel's detail record and return only its description."""

    parsed_hotel_id = int(hotel_id)
    timeout = timeout_seconds or float(
        os.getenv("HOTEL_DETAIL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        or DEFAULT_TIMEOUT_SECONDS
    )
    max_chars = max_description_chars or int(
        os.getenv("HOTEL_DETAIL_DESCRIPTION_MAX_CHARS", str(DEFAULT_MAX_DESCRIPTION_CHARS))
        or DEFAULT_MAX_DESCRIPTION_CHARS
    )

    payload = fetch_hotel_detail_payload(parsed_hotel_id, timeout_seconds=timeout)

    description = _extract_description(payload)
    if not description:
        return {
            "success": False,
            "source": "hotel_detail_api",
            "hotel_id": parsed_hotel_id,
            "description": "",
            "error": "Hotel detail API returned no description.",
        }

    description = _clean_description(description)
    if len(description) > max_chars:
        description = description[:max_chars].rstrip() + "\n...[description truncated]"

    return {
        "success": True,
        "source": "hotel_detail_api",
        "hotel_id": parsed_hotel_id,
        "description": description,
        "description_chars": len(description),
    }


def fetch_hotel_detail_payload(
    hotel_id: int,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Fetch one hotel's raw detail payload for UI cards and internal tools."""

    parsed_hotel_id = int(hotel_id)
    timeout = timeout_seconds or float(
        os.getenv("HOTEL_DETAIL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        or DEFAULT_TIMEOUT_SECONDS
    )
    url = _build_hotel_detail_url(parsed_hotel_id)
    response = requests.get(url, headers=_build_headers(), timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, Mapping):
        for key in ("data", "hotel", "result"):
            nested = payload.get(key)
            if isinstance(nested, Mapping):
                return dict(nested)
        return dict(payload)
    return {}


def fetch_hotel_descriptions(hotel_ids: Sequence[Any], *, limit: int = 3) -> dict[str, Any]:
    """Fetch description-only evidence for hotel IDs."""

    descriptions: list[dict[str, Any]] = []
    errors: list[str] = []
    for hotel_id in _uniq_ints(hotel_ids)[: max(int(limit), 1)]:
        try:
            result = fetch_hotel_description(hotel_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Hotel detail API failed for hotel_id=%s: %s: %s",
                hotel_id,
                type(exc).__name__,
                exc,
            )
            errors.append(f"hotel_id={hotel_id}: {type(exc).__name__}: {exc}")
            continue

        if result.get("success"):
            descriptions.append(result)
        elif result.get("error"):
            errors.append(f"hotel_id={hotel_id}: {result.get('error')}")

    return {
        "success": bool(descriptions),
        "source": "hotel_detail_api",
        "results": descriptions,
        "count": len(descriptions),
        "errors": errors,
    }


def _build_hotel_detail_url(hotel_id: int) -> str:
    template = os.getenv("HOTEL_DETAIL_URL_TEMPLATE", "").strip()
    if template:
        return template.format(hotel_id=hotel_id)

    base_url = (
        os.getenv("HOTEL_DETAIL_BASE_URL")
        or os.getenv("DA10_HOTEL_DETAIL_BASE_URL")
        or DEFAULT_HOTEL_DETAIL_BASE_URL
    ).rstrip("/")
    return f"{base_url}/{hotel_id}"


def _build_headers() -> dict[str, str]:
    api_key = (
        os.getenv("HOTEL_API_KEY")
        or os.getenv("DA10_OTA_API_KEY")
        or os.getenv("OTA_API_KEY")
        or ""
    ).strip()
    headers = {"accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _extract_description(payload: Any) -> str:
    if isinstance(payload, Mapping):
        direct = payload.get("description")
        if isinstance(direct, str):
            return direct

        for key in ("data", "hotel", "result"):
            nested = payload.get(key)
            if isinstance(nested, Mapping) and isinstance(nested.get("description"), str):
                return str(nested["description"])

    return ""


def _clean_description(description: str) -> str:
    return " ".join(description.replace("\r", "\n").split())


def _uniq_ints(values: Sequence[Any]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
    return out
