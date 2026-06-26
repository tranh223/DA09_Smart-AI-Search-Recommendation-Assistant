from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import re
import unicodedata
from typing import Any

from query_understanding.models.intent import SemanticMappingResult
from query_understanding.models.planner import (
    CountInteractionValue,
    RuntimeTag,
    RuntimeTagExpansion,
    SessionContext,
    SessionProfileUpdateResult,
    UserProfile,
)
from query_understanding.session_profile.policy import AMENITY_LIKE_REVIEW_TAGS, BUDGET_LEVELS


@dataclass(slots=True)
class EntityUpdateResult:
    applied_updates: dict[str, list[str] | str | None]
    amenity_tags: list[str]


class EntitySessionUpdater:
    def apply(self, session: SessionContext, intent_result: Any, *, query: str = "") -> EntityUpdateResult:
        entities = intent_result.entities
        constraints = intent_result.constraints
        applied_updates: dict[str, list[str] | str | None] = {}
        amenity_tags: list[str] = []

        destination_changed = False
        if entities.destination:
            if _is_different_destination(session.destination, entities.destination):
                destination_changed = True
                session.number_of_days = None
                session.number_of_nights = None
                applied_updates["number_of_days"] = None
                applied_updates["number_of_nights"] = None
                applied_updates["duration_reset_reason"] = "destination_changed"
            session.destination = entities.destination
            applied_updates["destination"] = entities.destination
        if entities.nearby_place:
            session.nearby_place = entities.nearby_place
            applied_updates["nearby_place"] = entities.nearby_place
        if entities.number_of_guests is not None:
            session.number_of_guests = entities.number_of_guests
            applied_updates["number_of_guests"] = str(entities.number_of_guests)
        duration_days, duration_nights = _extract_duration_from_query(query)
        number_of_days = entities.number_of_days if entities.number_of_days is not None else duration_days
        number_of_nights = entities.number_of_nights if entities.number_of_nights is not None else duration_nights
        if number_of_days is not None:
            session.number_of_days = number_of_days
            applied_updates["number_of_days"] = str(number_of_days)
        if number_of_nights is not None:
            session.number_of_nights = number_of_nights
            applied_updates["number_of_nights"] = str(number_of_nights)
        if entities.check_in:
            session.check_in = entities.check_in
            applied_updates["check_in"] = entities.check_in
        if entities.check_out:
            session.check_out = entities.check_out
            applied_updates["check_out"] = entities.check_out
        can_derive_nights_from_dates = (
            not destination_changed
            or bool(entities.check_in and entities.check_out)
        )
        if session.number_of_nights is None and can_derive_nights_from_dates:
            derived_nights = _derive_nights_from_dates(session.check_in, session.check_out)
            if derived_nights is not None:
                session.number_of_nights = derived_nights
                applied_updates["number_of_nights"] = str(derived_nights)
        if entities.trip_type:
            trip_type = normalize_long_term_trip_type_value(entities.trip_type)
            session.session_trip_types = {
                trip_type: build_count_interaction_value(1),
            }
            applied_updates["session_trip_types"] = [trip_type]

        raw_price_min, raw_price_max = _correct_approximate_budget_parse(
            query=query,
            price_min=entities.budget_min,
            price_max=entities.budget_max,
        )
        price_min, price_max = normalize_budget_by_scope(
            budget_scope=entities.budget_scope,
            price_min=raw_price_min,
            price_max=raw_price_max,
        )
        if raw_price_min != entities.budget_min or raw_price_max != entities.budget_max:
            applied_updates["budget_parse_correction"] = "approximate_budget"
        if raw_price_min is not None:
            session.raw_budget_min = raw_price_min
            applied_updates["raw_budget_min"] = str(raw_price_min)
        if raw_price_max is not None:
            session.raw_budget_max = raw_price_max
            applied_updates["raw_budget_max"] = str(raw_price_max)
        budget_type = _resolve_budget_type(
            query=query,
            extracted_budget_type=entities.budget_type,
            has_budget=price_min is not None or price_max is not None,
            current_budget_type=session.budget_type,
        )
        if budget_type:
            session.budget_type = budget_type
            applied_updates["budget_type"] = budget_type
        effective_min, effective_max = _effective_budget_range(
            raw_min=price_min,
            raw_max=price_max,
            budget_type=session.budget_type,
            number_of_nights=session.number_of_nights,
        )
        if effective_min is not None:
            session.session_price_range.min = effective_min
            applied_updates["session_price_range_min"] = str(effective_min)
        if effective_max is not None:
            session.session_price_range.max = effective_max
            applied_updates["session_price_range_max"] = str(effective_max)
        if entities.budget_scope:
            applied_updates["budget_scope"] = entities.budget_scope
        if constraints.budget_level in BUDGET_LEVELS:
            session.session_budget_levels = {
                constraints.budget_level: build_count_interaction_value(1),
            }
            applied_updates["session_budget_levels"] = [constraints.budget_level]
        if constraints.note_amenities == "max":
            session.note_amenities = "max"
            applied_updates["note_amenities"] = "max"

        return EntityUpdateResult(
            applied_updates=applied_updates,
            amenity_tags=amenity_tags,
        )


@dataclass(slots=True)
class RoutedTags:
    preference_tags: list[str]
    hotel_types: list[str]
    room_views: list[str]
    amenities: list[str]
    trip_types: list[str]


class TagSessionRouter:
    def route(self, tags: list[RuntimeTag]) -> RoutedTags:
        preference_tags: list[str] = []
        hotel_types: list[str] = []
        room_views: list[str] = []
        amenities: list[str] = []
        trip_types: list[str] = []

        for tag in tags:
            if tag.category == "SUITABLE_FOR":
                trip_types.append(normalize_long_term_trip_type_value(tag.tag))
            elif tag.category == "ROOM_VIEW":
                room_views.append(tag.tag)
            elif tag.category == "REVIEW_TAG":
                preference_tags.append(tag.tag)
                if tag.tag in AMENITY_LIKE_REVIEW_TAGS:
                    amenities.append(tag.tag)
            elif tag.category == "HOTEL_TYPE":
                hotel_types.append(tag.tag)
            elif tag.category in {"HOTEL_AMENITY", "ROOM_AMENITY"}:
                amenities.append(tag.tag)

        return RoutedTags(
            preference_tags=preference_tags,
            hotel_types=hotel_types,
            room_views=room_views,
            amenities=amenities,
            trip_types=trip_types,
        )


@dataclass(slots=True)
class SessionProfileUpdater:
    score_threshold: float
    entity_updater: EntitySessionUpdater = field(default_factory=EntitySessionUpdater)
    tag_router: TagSessionRouter = field(default_factory=TagSessionRouter)

    def apply(
        self,
        user_profile: UserProfile,
        intent_result: Any,
        semantic_mapping: SemanticMappingResult,
        runtime_tag_expansion: RuntimeTagExpansion | None = None,
        query: str = "",
    ) -> SessionProfileUpdateResult:
        session = user_profile.session_context
        if runtime_tag_expansion is not None:
            session.runtime_tag_expansion = runtime_tag_expansion

        entity_update = self.entity_updater.apply(session, intent_result, query=query)
        applied_updates = dict(entity_update.applied_updates)

        self._apply_nearby_place_from_mapping(
            session=session,
            intent_result=intent_result,
            semantic_mapping=semantic_mapping,
            applied_updates=applied_updates,
        )

        final_runtime_tags = list(session.runtime_tag_expansion.final_tags)
        if not final_runtime_tags:
            final_runtime_tags = runtime_tags_from_semantic_mapping(
                semantic_mapping,
                score_threshold=self.score_threshold,
            )

        routed_tags = self.tag_router.route(final_runtime_tags)
        mapped_amenities = list(routed_tags.amenities) + list(entity_update.amenity_tags)

        if not intent_result.entities.trip_type and routed_tags.trip_types:
            session.session_trip_types = {}
            added_trip_types = merge_score_map_values(session.session_trip_types, routed_tags.trip_types)
            if added_trip_types:
                applied_updates["session_trip_types"] = added_trip_types

        self._merge_routed_tags(
            session=session,
            applied_updates=applied_updates,
            preference_tags=routed_tags.preference_tags,
            hotel_types=routed_tags.hotel_types,
            room_views=routed_tags.room_views,
            amenities=mapped_amenities,
        )
        direct_runtime_tags = list(session.runtime_tag_expansion.mapped_tags)
        if not direct_runtime_tags:
            direct_runtime_tags = runtime_tags_from_semantic_mapping(
                semantic_mapping,
                score_threshold=self.score_threshold,
            )
        self._apply_direct_tag_updates(
            applied_updates=applied_updates,
            direct_routed_tags=self.tag_router.route(direct_runtime_tags),
            entity_amenity_tags=entity_update.amenity_tags,
            has_explicit_trip_type=bool(intent_result.entities.trip_type),
        )

        return SessionProfileUpdateResult(
            session_context=session,
            applied_updates=applied_updates,
            semantic_mapping={
                "mapped_items": [asdict(item) for item in semantic_mapping.mapped_items],
                "runtime_tag_expansion": (
                    asdict(runtime_tag_expansion)
                    if runtime_tag_expansion is not None
                    else asdict(session.runtime_tag_expansion)
                ),
            },
        )

    def _apply_nearby_place_from_mapping(
        self,
        *,
        session: SessionContext,
        intent_result: Any,
        semantic_mapping: SemanticMappingResult,
        applied_updates: dict[str, list[str] | str | None],
    ) -> None:
        if intent_result.entities.nearby_place:
            return
        for item in semantic_mapping.mapped_items:
            if item.target_field != "nearby_place":
                continue
            nearby_value = None
            if item.matched_tag and item.score is not None and item.score > self.score_threshold:
                nearby_value = item.matched_tag
            elif item.text:
                nearby_value = item.text
            if nearby_value:
                session.nearby_place = nearby_value
                applied_updates["nearby_place"] = nearby_value

    @staticmethod
    def _merge_routed_tags(
        *,
        session: SessionContext,
        applied_updates: dict[str, list[str] | str | None],
        preference_tags: list[str],
        hotel_types: list[str],
        room_views: list[str],
        amenities: list[str],
    ) -> None:
        added_tags = merge_score_map_values(session.session_preference_habits, preference_tags)
        if added_tags:
            applied_updates["session_preference_habits"] = added_tags

        added_hotel_types = merge_score_map_values(session.session_hotel_types, hotel_types)
        if added_hotel_types:
            applied_updates["session_hotel_types"] = added_hotel_types

        added_room_views = merge_score_map_values(session.session_room_views, room_views)
        if added_room_views:
            applied_updates["session_room_views"] = added_room_views

        added_amenities = merge_score_map_values(session.session_amenities, list(dict.fromkeys(amenities)))
        if added_amenities:
            applied_updates["session_amenities"] = added_amenities

    @staticmethod
    def _apply_direct_tag_updates(
        *,
        applied_updates: dict[str, list[str] | str | None],
        direct_routed_tags: RoutedTags,
        entity_amenity_tags: list[str],
        has_explicit_trip_type: bool,
    ) -> None:
        direct_updates = {
            "session_preference_habits": direct_routed_tags.preference_tags,
            "session_hotel_types": direct_routed_tags.hotel_types,
            "session_room_views": direct_routed_tags.room_views,
            "session_amenities": list(direct_routed_tags.amenities) + list(entity_amenity_tags),
        }
        if not has_explicit_trip_type:
            direct_updates["session_trip_types"] = direct_routed_tags.trip_types

        for field_name, values in direct_updates.items():
            deduped_values = _dedupe_values(values)
            if deduped_values:
                applied_updates[field_name] = deduped_values
            else:
                applied_updates.pop(field_name, None)


def runtime_tags_from_semantic_mapping(
    semantic_mapping: SemanticMappingResult,
    *,
    score_threshold: float,
) -> list[RuntimeTag]:
    tags: list[RuntimeTag] = []
    for item in semantic_mapping.mapped_items:
        if not item.matched_tag or not item.matched_category:
            continue
        if item.score is None or item.score <= score_threshold:
            continue
        tags.append(
            RuntimeTag(
                tag=item.matched_tag,
                category=item.matched_category,
                score=1.0,
                source="semantic_mapper",
            )
        )
    return tags


def _dedupe_values(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def merge_score_map_values(
    target: dict[str, CountInteractionValue],
    values: list[str],
    default_weight: int = 1,
) -> list[str]:
    touched: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        touched.append(value)
        if value not in target:
            target[value] = build_count_interaction_value(default_weight)
            continue
        current = target[value]
        target[value] = build_count_interaction_value(current.count + default_weight)
    return touched


def build_count_interaction_value(count: int) -> CountInteractionValue:
    return CountInteractionValue(count=count, last_interaction=date.today().isoformat())


def normalize_long_term_trip_type_value(value: str) -> str:
    return value


def _correct_approximate_budget_parse(
    *,
    query: str,
    price_min: float | None,
    price_max: float | None,
) -> tuple[float | None, float | None]:
    """Treat approximate budget wording as X..X before budget window expansion.

    LLMs sometimes parse "khoang/tam X" as only an upper bound. That would
    incorrectly route to the "duoi X" window. Keep explicit lower/upper bound
    wording untouched.
    """
    if price_min is None and price_max is None:
        return price_min, price_max
    if not _has_approximate_budget_cue(query):
        return price_min, price_max
    if _has_one_sided_budget_cue(query):
        return price_min, price_max
    if price_min is None and price_max is not None:
        return price_max, price_max
    if price_max is None and price_min is not None:
        return price_min, price_min
    return price_min, price_max


def _has_approximate_budget_cue(query: str) -> bool:
    text = _normalize_query_text(query)
    return bool(
        re.search(
            r"\b(khoang|tam|tam khoang|xap xi|gan|gan khoang|chung|khoang chung)\b",
            text,
        )
    )


def _has_one_sided_budget_cue(query: str) -> bool:
    text = _normalize_query_text(query)
    return bool(
        re.search(
            r"\b(duoi|khong qua|toi da|cao nhat|tren|hon|it nhat|tro len)\b",
            text,
        )
    )


def _normalize_query_text(query: str) -> str:
    normalized = unicodedata.normalize("NFD", str(query or "").lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip()


def _is_different_destination(current_destination: str | None, new_destination: str | None) -> bool:
    if not current_destination or not new_destination:
        return False
    return _normalize_query_text(current_destination) != _normalize_query_text(new_destination)


def normalize_budget_by_scope(
    *,
    budget_scope: str | None,
    price_min: float | None,
    price_max: float | None,
) -> tuple[float | None, float | None]:
    # OTA-style budget windowing:
    # - "duoi X": only price_max is extracted, then expand one-sided downward.
    # - "tren X": only price_min is extracted, then expand one-sided upward.
    # - "khoang X": both min/max equal X, then expand symmetrically around X.
    if price_min is None and price_max is None:
        return price_min, price_max

    if price_min is not None and price_max is not None:
        if price_min == price_max:
            return _expand_approximate_budget(price_min)
        return price_min, price_max

    if price_max is not None:
        return _expand_upper_bound_budget(price_max)
    if price_min is not None:
        return _expand_lower_bound_budget(price_min)
    return price_min, price_max


def _expand_upper_bound_budget(value: float) -> tuple[float | None, float | None]:
    ratio = _budget_window_ratio(value)
    return round(value * (1 - ratio), 2), round(value, 2)


def _expand_lower_bound_budget(value: float) -> tuple[float | None, float | None]:
    ratio = _budget_window_ratio(value)
    return round(value, 2), round(value * (1 + ratio), 2)


def _expand_approximate_budget(value: float) -> tuple[float | None, float | None]:
    ratio = _budget_window_ratio(value)
    return round(value * (1 - ratio), 2), round(value * (1 + ratio), 2)


def _budget_window_ratio(value: float) -> float:
    # Bucketed OTA behavior instead of a continuous formula.
    if value < 1_500_000:
        return 0.50
    if value < 3_000_000:
        return 0.40
    if value < 5_000_000:
        return 0.30
    if value < 10_000_000:
        return 0.25
    return 0.20


def _extract_duration_from_query(query: str) -> tuple[int | None, int | None]:
    text = _normalize_query_text(query)
    days: int | None = None
    nights: int | None = None
    day_match = re.search(r"\b(\d+)\s*(ngay|day|days)\b", text)
    night_match = re.search(r"\b(\d+)\s*(dem|night|nights)\b", text)
    if day_match:
        days = int(day_match.group(1))
    if night_match:
        nights = int(night_match.group(1))
    if nights is None and days is not None and days > 1:
        nights = days - 1
    if days is None and nights is not None:
        days = nights + 1
    return days, nights


def _derive_nights_from_dates(check_in: str | None, check_out: str | None) -> int | None:
    if not check_in or not check_out:
        return None
    try:
        start = datetime.fromisoformat(str(check_in)).date()
        end = datetime.fromisoformat(str(check_out)).date()
    except ValueError:
        return None
    nights = (end - start).days
    return nights if nights > 0 else None


def _resolve_budget_type(
    *,
    query: str,
    extracted_budget_type: str | None,
    has_budget: bool,
    current_budget_type: str | None,
) -> str | None:
    if extracted_budget_type in {"total", "per_night"}:
        return extracted_budget_type
    text = _normalize_query_text(query)
    if has_budget and re.search(r"\b(moi\s+dem|mot\s+dem|per\s+night|/dem|theo\s+dem)\b", text):
        return "per_night"
    if has_budget:
        return "total"
    return current_budget_type if current_budget_type in {"total", "per_night"} else None


def _effective_budget_range(
    *,
    raw_min: float | None,
    raw_max: float | None,
    budget_type: str | None,
    number_of_nights: int | None,
) -> tuple[float | None, float | None]:
    if raw_min is None and raw_max is None:
        return None, None
    if budget_type == "total" and number_of_nights and number_of_nights > 0:
        return (
            round(raw_min / number_of_nights, 2) if raw_min is not None else None,
            round(raw_max / number_of_nights, 2) if raw_max is not None else None,
        )
    return raw_min, raw_max
