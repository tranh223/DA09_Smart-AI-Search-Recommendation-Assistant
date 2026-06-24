from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
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
    def apply(self, session: SessionContext, intent_result: Any) -> EntityUpdateResult:
        entities = intent_result.entities
        constraints = intent_result.constraints
        applied_updates: dict[str, list[str] | str | None] = {}
        amenity_tags: list[str] = []

        if entities.destination:
            session.destination = entities.destination
            applied_updates["destination"] = entities.destination
        if entities.nearby_place:
            session.nearby_place = entities.nearby_place
            applied_updates["nearby_place"] = entities.nearby_place
        if entities.number_of_guests is not None:
            session.number_of_guests = entities.number_of_guests
            applied_updates["number_of_guests"] = str(entities.number_of_guests)
        if entities.check_in:
            session.check_in = entities.check_in
            applied_updates["check_in"] = entities.check_in
        if entities.check_out:
            session.check_out = entities.check_out
            applied_updates["check_out"] = entities.check_out
        if entities.trip_type:
            trip_type = normalize_long_term_trip_type_value(entities.trip_type)
            session.session_trip_types = {
                trip_type: build_count_interaction_value(1),
            }
            applied_updates["session_trip_types"] = [trip_type]
            amenity_tags.append(trip_type)

        price_min, price_max = normalize_budget_by_scope(
            budget_scope=entities.budget_scope,
            price_min=entities.budget_min,
            price_max=entities.budget_max,
        )
        if price_min is not None:
            session.session_price_range.min = price_min
            applied_updates["session_price_range_min"] = str(price_min)
        if price_max is not None:
            session.session_price_range.max = price_max
            applied_updates["session_price_range_max"] = str(price_max)
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
                amenities.append(tag.tag)
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
    ) -> SessionProfileUpdateResult:
        session = user_profile.session_context
        if runtime_tag_expansion is not None:
            session.runtime_tag_expansion = runtime_tag_expansion

        entity_update = self.entity_updater.apply(session, intent_result)
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


def merge_score_map_values(
    target: dict[str, CountInteractionValue],
    values: list[str],
    default_weight: int = 1,
) -> list[str]:
    added: list[str] = []
    for value in values:
        if value not in target:
            target[value] = build_count_interaction_value(default_weight)
            added.append(value)
            continue
        current = target[value]
        target[value] = build_count_interaction_value(current.count + default_weight)
    return added


def build_count_interaction_value(count: int) -> CountInteractionValue:
    return CountInteractionValue(count=count, last_interaction=date.today().isoformat())


def normalize_long_term_trip_type_value(value: str) -> str:
    return value


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

    if budget_scope == "trip_total":
        if price_min is not None:
            price_min = price_min / 4
        if price_max is not None:
            price_max = price_max / 4

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
