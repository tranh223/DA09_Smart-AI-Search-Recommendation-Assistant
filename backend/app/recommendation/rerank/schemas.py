from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .utils import clamp, string_list, to_str_id


class CandidateHotel(BaseModel):
    item_id: str
    item_type: Literal["hotel"] = "hotel"
    name: str = ""
    destination: str = ""
    hotel_type: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    currency: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)
    room_views: List[str] = Field(default_factory=list)
    preference_habits: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    location_tags: List[str] = Field(default_factory=list)
    nearby_places: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    review_sentiment: Optional[float] = None
    available: bool = False
    available_rooms: Optional[int] = None
    keyword_score: Optional[float] = None
    primary_image: Optional[str] = None
    images: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("item_id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        return to_str_id(value)

    @field_validator("amenities", "room_views", "preference_habits", "tags", "location_tags", "nearby_places", mode="before")
    @classmethod
    def normalize_lists(cls, value: Any) -> list[str]:
        return string_list(value)


class RankedItem(BaseModel):
    item_id: str
    rank: int
    final_score: float
    base_score: float
    llm_score: Optional[float] = None
    feature_scores: Dict[str, float]
    negative_penalty: float
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @field_validator("final_score", "base_score", "negative_penalty", mode="before")
    @classmethod
    def clamp_scores(cls, value: Any) -> float:
        return clamp(value)
