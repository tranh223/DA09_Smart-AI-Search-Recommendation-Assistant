from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WeatherRequest:
    destination: str


@dataclass(slots=True)
class WeatherResponse:
    destination: str
    summary: str | None = None
    temperature_c: float | None = None
    conditions: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
