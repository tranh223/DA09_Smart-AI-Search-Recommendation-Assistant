"""
Pydantic models cho toàn bộ Recommendation Pipeline.
Input: output của Intent Extraction (profile + session_context).
Output: MergedCandidate list → sang Ranking.
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 1.  INPUT - từ Intent Extraction
# ─────────────────────────────────────────────

class PriceRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str | None = "VND"


class InteractionScore(BaseModel):
    """Dùng cho các trường dạng {tag_name: {count, last_interaction}}."""
    count: int = 1
    last_interaction: str | None = None   # "YYYY-MM-DD"


class NegativePreferences(BaseModel):
    avoid_hotel_types: dict[str, float] = Field(default_factory=dict)
    avoid_amenities: dict[str, float] = Field(default_factory=dict)
    avoid_preference_habits: dict[str, float] = Field(default_factory=dict)
    avoid_nearby_places: dict[str, float] = Field(default_factory=dict)
    avoid_locations: dict[str, float] = Field(default_factory=dict)


class Profile(BaseModel):
    nationality: str | None = None
    age_group: str | None = None
    current_workplace: str | None = None
    is_enough: bool = False

    # {tag_name: {count, last_interaction}} — ánh xạ vào INTERESTED_IN trên Neo4j
    traveler_type: dict[str, InteractionScore] = Field(default_factory=dict)
    long_term_preference_habits: dict[str, InteractionScore] = Field(default_factory=dict)

    # {trip_type_name: {count, last_interaction}}
    long_term_trip_types: dict[str, InteractionScore] = Field(default_factory=dict)

    # {budget_level: {count, last_interaction}}
    long_term_budget_levels: dict[str, InteractionScore] = Field(default_factory=dict)

    long_term_price_range: PriceRange = Field(default_factory=PriceRange)
    long_term_hotel_types: dict[str, Any] = Field(default_factory=dict)
    long_term_room_views: dict[str, Any] = Field(default_factory=dict)
    long_term_amenities: dict[str, Any] = Field(default_factory=dict)
    long_term_negative_preferences: NegativePreferences = Field(default_factory=NegativePreferences)

    recommendation_clicks: dict[str, list] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class SessionContext(BaseModel):
    destination: str | None = None          # city — key field cho mọi query
    current_location: str | None = None
    nearby_place: str | None = None         # điểm landmark/khu vực quan tâm
    number_of_guests: int | None = None
    has_pet: bool | None = None
    has_children: bool | None = None
    check_in: str | None = None             # "YYYY-MM-DD"
    check_out: str | None = None
    session_price_range: PriceRange = Field(default_factory=PriceRange)

    class Config:
        extra = "allow"


class RecommendInput(BaseModel):
    """Input vào Recommendation Engine từ Intent Extraction."""
    user_id: str
    profile: Profile
    session_context: SessionContext
    original_query: str = ""
    limit_per_source: int = 10


# ─────────────────────────────────────────────
# 2.  CANDIDATE OUTPUT - từ mỗi nguồn
# ─────────────────────────────────────────────

class CandidateHotel(BaseModel):
    hotel_id: int
    hotel_name: str | None = None
    source: str                             # "embedding_search" | "personalization"
    score: float = 0.0
    matched_paths: list[str] = Field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)   # star_rating, review_score, v.v.


# ─────────────────────────────────────────────
# 3.  MERGED CANDIDATE - sau REC_MERGE
# ─────────────────────────────────────────────

class MergedCandidate(BaseModel):
    hotel_id: int
    hotel_name: str | None = None
    sources: list[str] = Field(default_factory=list)
    source_scores: dict[str, float] = Field(default_factory=dict)
    matched_paths: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    pre_rank_score: float = 0.0             # điểm sơ bộ trước Ranking
    metadata: dict[str, Any] = Field(default_factory=dict)
