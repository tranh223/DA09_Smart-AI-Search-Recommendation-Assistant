from dataclasses import dataclass, field


@dataclass(slots=True)
class SemanticPreferenceItem:
    text: str
    target_field: str
    category: str
    priority: str = "soft"


@dataclass(slots=True)
class SemanticPreferenceSet:
    items: list[SemanticPreferenceItem] = field(default_factory=list)


@dataclass(slots=True)
class MappedSemanticItem:
    text: str
    target_field: str
    category: str
    matched_category: str | None = None
    matched_tag: str | None = None
    score: float | None = None
    priority: str = "soft"


@dataclass(slots=True)
class SemanticMappingResult:
    mapped_items: list[MappedSemanticItem] = field(default_factory=list)


@dataclass(slots=True)
class EntitySet:
    destination: str | None = None
    hotel_name: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    budget_scope: str | None = None
    budget_type: str | None = None
    trip_type: str | None = None
    nearby_place: str | None = None
    number_of_guests: int | None = None
    number_of_days: int | None = None
    number_of_nights: int | None = None
    check_in: str | None = None
    check_out: str | None = None


@dataclass(slots=True)
class ConstraintSet:
    budget_level: str | None = None
    location_hint: str | None = None
    note_amenities: str | None = None


@dataclass(slots=True)
class IntentResult:
    intent_components: list[str] = field(default_factory=list)
    entities: EntitySet = field(default_factory=EntitySet)
    semantic_preferences: SemanticPreferenceSet = field(default_factory=SemanticPreferenceSet)
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
