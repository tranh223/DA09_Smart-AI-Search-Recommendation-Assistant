from dataclasses import dataclass, field

from query_understanding.enums import SearchTask


@dataclass(slots=True)
class CountInteractionValue:
    count: int
    last_interaction: str


ScoreMap = dict[str, CountInteractionValue]
NegativeScoreMap = dict[str, CountInteractionValue]


@dataclass(slots=True)
class PriceRange:
    min: float | None = None
    max: float | None = None
    currency: str | None = "VND"


@dataclass(slots=True)
class NegativePreferences:
    avoid_hotel_types: NegativeScoreMap = field(default_factory=dict)
    avoid_amenities: NegativeScoreMap = field(default_factory=dict)
    avoid_preference_habits: NegativeScoreMap = field(default_factory=dict)
    avoid_nearby_places: NegativeScoreMap = field(default_factory=dict)
    avoid_locations: NegativeScoreMap = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeTag:
    tag: str
    category: str
    score: float
    source: str
    relation_type: str | None = None
    edge_score: float | None = None
    confidence: float | None = None


@dataclass(slots=True)
class RuntimeTagExpansion:
    mapped_tags: list[RuntimeTag] = field(default_factory=list)
    expanded_tags: list[RuntimeTag] = field(default_factory=list)
    final_tags: list[RuntimeTag] = field(default_factory=list)


@dataclass(slots=True)
class RecommendationClicks:
    hotel: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LongTermProfile:
    nationality: str | None = None
    age_group: str | None = None
    current_workplace: str | None = None
    is_enough: bool | None = None
    traveler_type: ScoreMap = field(default_factory=dict)
    long_term_trip_types: ScoreMap = field(default_factory=dict)
    long_term_budget_levels: ScoreMap = field(default_factory=dict)
    long_term_price_range: PriceRange = field(default_factory=PriceRange)
    long_term_preference_habits: ScoreMap = field(default_factory=dict)
    long_term_hotel_types: ScoreMap = field(default_factory=dict)
    long_term_room_views: ScoreMap = field(default_factory=dict)
    long_term_amenities: ScoreMap = field(default_factory=dict)
    recommendation_clicks: RecommendationClicks = field(default_factory=RecommendationClicks)
    long_term_negative_preferences: NegativePreferences = field(default_factory=NegativePreferences)


@dataclass(slots=True)
class SessionContext:
    destination: str | None = None
    current_location: str | None = None
    nearby_place: str | None = None
    number_of_guests: int | None = None
    number_of_days: int | None = None
    number_of_nights: int | None = None
    has_pet: bool | None = None
    has_children: bool | None = None
    check_in: str | None = None
    check_out: str | None = None
    budget_type: str | None = None
    raw_budget_min: float | None = None
    raw_budget_max: float | None = None
    note_amenities: str | None = None
    is_enough_recommend: bool | None = None
    session_trip_types: ScoreMap = field(default_factory=dict)
    session_budget_levels: ScoreMap = field(default_factory=dict)
    session_price_range: PriceRange = field(default_factory=PriceRange)
    session_preference_habits: ScoreMap = field(default_factory=dict)
    session_hotel_types: ScoreMap = field(default_factory=dict)
    session_room_views: ScoreMap = field(default_factory=dict)
    session_amenities: ScoreMap = field(default_factory=dict)
    session_negative_preferences: NegativePreferences = field(default_factory=NegativePreferences)
    runtime_tag_expansion: RuntimeTagExpansion = field(default_factory=RuntimeTagExpansion)


@dataclass(slots=True)
class UserProfile:
    user_id: str
    name: str | None = None
    long_term_profile: LongTermProfile = field(default_factory=LongTermProfile)
    tagremoved_profile: LongTermProfile = field(default_factory=LongTermProfile)
    session_context: SessionContext = field(default_factory=SessionContext)


@dataclass(slots=True)
class SessionProfileUpdateResult:
    session_context: SessionContext
    applied_updates: dict[str, list[str] | str | None] = field(default_factory=dict)
    semantic_mapping: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ActiveProfile:
    nationality: str | None = None
    age_group: str | None = None
    current_workplace: str | None = None
    is_enough: bool | None = None
    traveler_type: ScoreMap = field(default_factory=dict)
    long_term_trip_types: ScoreMap = field(default_factory=dict)
    long_term_budget_levels: ScoreMap = field(default_factory=dict)
    long_term_price_range: PriceRange = field(default_factory=PriceRange)
    long_term_preference_habits: ScoreMap = field(default_factory=dict)
    long_term_hotel_types: ScoreMap = field(default_factory=dict)
    long_term_room_views: ScoreMap = field(default_factory=dict)
    long_term_amenities: ScoreMap = field(default_factory=dict)
    recommendation_clicks: RecommendationClicks = field(default_factory=RecommendationClicks)
    long_term_negative_preferences: NegativePreferences = field(default_factory=NegativePreferences)


@dataclass(slots=True)
class SearchPlanResult:
    execution_mode: str = "parallel"
    search_tasks: list[SearchTask | str] = field(default_factory=list)
    retrieval_sources: list[str] = field(default_factory=list)
    graph_operations: list[str] = field(default_factory=list)
