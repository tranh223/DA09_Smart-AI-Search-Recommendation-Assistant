"""Utilities for hotel_sql_tool integration."""

from __future__ import annotations

import re
from typing import Any, Optional


_CITY_PATTERNS = [
    "da nang|đà nẵng|da-nang",
    "ho chi minh|thành phố hồ chí minh|tp hcm|hồ chí minh|tphcm",
    "nha trang|nha-trang",
    "hanoi|hà nội|hn",
    "ha noi|hà nội",
    "can tho|cần thơ",
]


def best_effort_extract_city(query: str) -> Optional[str]:
    if not query:
        return None
    q = query.lower()
    for pat in _CITY_PATTERNS:
        if re.search(pat, q, flags=re.IGNORECASE):
            # return canonical-ish token
            if "đà nẵng" in pat or "da nang" in pat:
                return "Da Nang"
            if "hồ chí minh" in pat or "tp hcm" in pat:
                return "Ho Chi Minh City"
            if "nha trang" in pat:
                return "Nha Trang"
            if "hà nội" in pat or "hanoi" in pat:
                return "Hanoi"
            if "cần thơ" in pat:
                return "Can Tho"
    return None


def best_effort_extract_hotel_id(query: str) -> Optional[int]:
    if not query:
        return None
    m = re.search(r"\bhotel_id\b\s*[:=]?\s*(\d+)", query, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(khách sạn|hotel)\b.*?(\d{3,8})", query, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return int(m.group(2))
    return None


def best_effort_extract_hotel_name(query: str) -> Optional[str]:
    # Heuristic: take quoted/after keywords like 'hotel', 'khách sạn'
    if not query:
        return None
    m = re.search(r"(?:khách sạn|hotel)\s*([A-Za-zÀ-ỹ0-9][^,\n\.?]{2,80})", query, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: none
    return None


def build_hotel_lookup_input_from_query(query: str, need: list[str]) -> HotelLookupInput:  # type: ignore
    from modules.hotel_sql_utils import best_effort_extract_city, best_effort_extract_hotel_id, best_effort_extract_hotel_name
    city = best_effort_extract_city(query)
    hotel_id = best_effort_extract_hotel_id(query)
    hotel_name = None if hotel_id is not None else best_effort_extract_hotel_name(query)

    # local import to avoid circular
    from tools.hotel_sql_tool import HotelLookupInput

    return HotelLookupInput(hotel_name=hotel_name, hotel_id=hotel_id, city=city, need=need)

