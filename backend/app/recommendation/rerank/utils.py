from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import unicodedata


def clamp(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def round_score(value: Any, digits: int = 3) -> float:
    return round(clamp(value), digits)


def to_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_str_id(value: Any) -> str:
    return "" if value is None else str(value)


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def string_list(value: Any) -> list[str]:
    return [str(item) for item in as_list(value) if item is not None]


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join(without_marks.casefold().split())


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def weighted_overlap(required: dict[str, float], actual: set[str]) -> float:
    if not required:
        return 0.5
    total = sum(max(0.0, float(weight or 0)) for weight in required.values())
    if total <= 0:
        return 0.0
    matched = sum(max(0.0, float(weight or 0)) for key, weight in required.items() if key in actual)
    return clamp(matched / total)


def normalize_weighted_maps(session_map: dict[str, float], long_map: dict[str, float]) -> tuple[float, float]:
    has_session = bool(session_map)
    has_long = bool(long_map)
    if has_session and has_long:
        return 0.70, 0.30
    if has_session:
        return 1.0, 0.0
    if has_long:
        return 0.0, 1.0
    return 0.0, 0.0
