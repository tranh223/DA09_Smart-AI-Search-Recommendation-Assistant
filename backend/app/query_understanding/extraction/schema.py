from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from query_understanding.contracts import UserProfile

# Temporarily disable weather/history inputs for intent extraction.
# Un-comment these imports and fields below when they are needed again.
# from query_understanding.contracts import UserHistoryResponse, WeatherResponse


@dataclass(slots=True)
class ExtractionRequest:
    query: str
    current_profile: UserProfile
    # weather_context: WeatherResponse | None = None
    # user_history: UserHistoryResponse | None = None


@dataclass(slots=True)
class ExtractionEntities:
    destination: str | None = None
    hotel_name: str | None = None
    nearby_place: str | None = None


@dataclass(slots=True)
class ExtractionExpectations:
    trip_type: dict[str, float] = field(default_factory=dict)
    hotel_type: dict[str, float] = field(default_factory=dict)
    tags: dict[str, float] = field(default_factory=dict)
    amenities: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResponse:
    entities: ExtractionEntities = field(default_factory=ExtractionEntities)
    expectations: ExtractionExpectations = field(default_factory=ExtractionExpectations)
    profile_updates: dict[str, Any] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
