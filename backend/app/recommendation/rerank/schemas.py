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
    is_luxury: bool = False
    review_count: int = 0

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

class ExternalHotelImage(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    url: Optional[str] = None
    is_primary: Optional[bool] = None

class ExternalHotelPolicy(BaseModel):
    hotel_id: Optional[int] = None
    check_in_from: Optional[str] = None
    check_out_until: Optional[str] = None
    service_fee_pct: Optional[int] = None
    child_policy: Optional[str] = None
    pet_policy: Optional[str] = None
    deposit_required: Optional[bool] = None
    policy_notes: Optional[str] = None

class ExternalHotelAmenity(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None

class ExternalHotelSuitability(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    suitable_for_tag: Optional[str] = None
    mention_count: Optional[int] = None
    score: Optional[float] = None

class ExternalHotelReviewGrade(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    grade_name: Optional[str] = None
    grade_score: Optional[float] = None

class ExternalHotelReviewAspect(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    aspect_name: Optional[str] = None
    mentioned: Optional[int] = None
    positive_pct: Optional[int] = None

class ExternalHotelReview(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    reviewer_country: Optional[str] = None
    rating: Optional[int] = None
    review_date: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    positive_text: Optional[str] = None
    negative_text: Optional[str] = None

class ExternalHotelRoom(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    room_type_id: Optional[int] = None
    name: Optional[str] = None
    price: Optional[int] = None
    room_size: Optional[str] = None
    max_occupancy: Optional[int] = None
    bed_type: Optional[str] = None
    room_view: Optional[str] = None
    room_amenities: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    review_score: Optional[float] = None

class ExternalHotelNearbyPlace(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    distance_km: Optional[float] = None

class ExternalHotelActivity(BaseModel):
    id: Optional[int] = None
    hotel_id: Optional[int] = None
    activity_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price_amount: Optional[int] = None
    review_score: Optional[float] = None

class ExternalHotel(BaseModel):
    id: Optional[int] = None
    score: Optional[float] = None
    name: Optional[str] = None
    property_type: Optional[str] = None
    accommodation_type: Optional[str] = None
    star_rating: Optional[float] = None
    is_luxury: Optional[bool] = None
    review_score: Optional[float] = None
    review_count: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    city_id: Optional[int] = None
    area: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    images: List[ExternalHotelImage] = Field(default_factory=list)
    policy: Optional[ExternalHotelPolicy] = None
    amenities: List[ExternalHotelAmenity] = Field(default_factory=list)
    suitability: List[ExternalHotelSuitability] = Field(default_factory=list)
    review_grades: List[ExternalHotelReviewGrade] = Field(default_factory=list)
    review_aspects: List[ExternalHotelReviewAspect] = Field(default_factory=list)
    reviews: List[ExternalHotelReview] = Field(default_factory=list)
    rooms: List[ExternalHotelRoom] = Field(default_factory=list)
    nearby_places: List[ExternalHotelNearbyPlace] = Field(default_factory=list)
    activities: List[ExternalHotelActivity] = Field(default_factory=list)
