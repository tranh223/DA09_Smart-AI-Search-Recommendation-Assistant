from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from query_understanding.merger.profile_retention_resolver import (
    ProfileRetentionResolver,
)
from query_understanding.models.planner import (
    ActiveProfile,
    CountInteractionValue,
    LongTermProfile,
    NegativePreferences,
    PriceRange,
    SessionContext,
    UserProfile,
)


PREFERENCE_PROMOTION_MIN_COUNT = 5


@dataclass(slots=True)
class CurrentProfileMerger:
    retention_resolver: ProfileRetentionResolver | None = None

    def merge(
        self,
        user_profile: UserProfile,
        *,
        hidden_profile_signals: list[Any] | None = None,
    ) -> ActiveProfile:
        long_term = user_profile.long_term_profile
        session = user_profile.session_context
        hidden_maps = self._build_hidden_signal_maps(
            hidden_profile_signals,
            has_explicit_budget=bool(session.session_budget_levels),
        )

        return ActiveProfile(
            nationality=long_term.nationality,
            age_group=long_term.age_group,
            current_workplace=long_term.current_workplace,
            is_enough=long_term.is_enough,
            traveler_type=self._merge_score_maps(
                long_term.traveler_type,
                hidden_maps.get("traveler_type", {}),
            ),
            long_term_trip_types=self._merge_score_maps(
                long_term.long_term_trip_types,
                session.session_trip_types,
            ),
            long_term_budget_levels=self._merge_score_maps(
                long_term.long_term_budget_levels,
                self._merge_score_maps(
                    session.session_budget_levels,
                    hidden_maps.get("long_term_budget_levels", {}),
                ),
            ),
            long_term_price_range=self._merge_price_range(long_term, session),
            long_term_preference_habits=self._merge_score_maps(
                long_term.long_term_preference_habits,
                self._merge_score_maps(
                    self._build_promoted_preference_habits(session),
                    hidden_maps.get("long_term_preference_habits", {}),
                ),
            ),
            long_term_hotel_types=self._merge_score_maps(
                long_term.long_term_hotel_types,
                session.session_hotel_types,
            ),
            long_term_room_views=self._merge_score_maps(
                long_term.long_term_room_views,
                session.session_room_views,
            ),
            long_term_amenities=self._merge_score_maps(
                long_term.long_term_amenities,
                session.session_amenities,
            ),
            recommendation_clicks=long_term.recommendation_clicks,
            long_term_negative_preferences=NegativePreferences(
                avoid_hotel_types=self._merge_score_maps(
                    long_term.long_term_negative_preferences.avoid_hotel_types,
                    session.session_negative_preferences.avoid_hotel_types,
                ),
                avoid_amenities=self._merge_score_maps(
                    long_term.long_term_negative_preferences.avoid_amenities,
                    session.session_negative_preferences.avoid_amenities,
                ),
                avoid_preference_habits=self._merge_score_maps(
                    long_term.long_term_negative_preferences.avoid_preference_habits,
                    session.session_negative_preferences.avoid_preference_habits,
                ),
                avoid_nearby_places=self._merge_score_maps(
                    long_term.long_term_negative_preferences.avoid_nearby_places,
                    session.session_negative_preferences.avoid_nearby_places,
                ),
                avoid_locations=self._merge_score_maps(
                    long_term.long_term_negative_preferences.avoid_locations,
                    session.session_negative_preferences.avoid_locations,
                ),
            ),
        )

    def merge_into_user_profile(
        self,
        user_profile: UserProfile,
        *,
        query: str,
        applied_updates: dict[str, Any] | None = None,
        hidden_profile_signals: list[Any] | None = None,
    ) -> ActiveProfile:
        merged_active_profile = self.merge(
            user_profile,
            hidden_profile_signals=hidden_profile_signals,
        )
        try:
            self._apply_long_term_retention(
                user_profile=user_profile,
                query=query,
                applied_updates=applied_updates,
                hidden_profile_signals=hidden_profile_signals,
            )
            return merged_active_profile
        except Exception:
            return merged_active_profile

    def _apply_long_term_retention(
        self,
        *,
        user_profile: UserProfile,
        query: str,
        applied_updates: dict[str, Any] | None = None,
        hidden_profile_signals: list[Any] | None = None,
    ) -> None:
        resolver = self.retention_resolver or ProfileRetentionResolver()
        self.retention_resolver = resolver
        old_profile = user_profile.long_term_profile
        tagremoved_profile = user_profile.tagremoved_profile
        retention_candidate_profile = self._build_retention_candidate_profile(
            old_profile=old_profile,
            session=user_profile.session_context,
            applied_updates=applied_updates,
            hidden_profile_signals=hidden_profile_signals,
        )
        session_signals = self._build_current_turn_session_signals(
            applied_updates=applied_updates,
            hidden_profile_signals=hidden_profile_signals,
        )
        decisions = resolver.resolve(
            query=query,
            old_profile=old_profile,
            tagremoved_profile=tagremoved_profile,
            session_signals=session_signals,
        )
        user_profile.long_term_profile = self._build_retained_long_term_profile(
            old_profile=old_profile,
            retention_candidate_profile=retention_candidate_profile,
            tagremoved_profile=tagremoved_profile,
            decisions=decisions,
        )
        user_profile.tagremoved_profile = self._build_tagremoved_profile(
            tagremoved_profile=tagremoved_profile,
            retention_candidate_profile=retention_candidate_profile,
            decisions=decisions,
        )

    @staticmethod
    def _build_retention_candidate_profile(
        *,
        old_profile: LongTermProfile,
        session: SessionContext,
        applied_updates: dict[str, Any] | None = None,
        hidden_profile_signals: list[Any] | None = None,
    ) -> ActiveProfile:
        candidate = CurrentProfileMerger._active_profile_from_long_term(old_profile)
        applied_updates = applied_updates or {}
        field_map = {
            "session_trip_types": "long_term_trip_types",
            "session_budget_levels": "long_term_budget_levels",
            "session_preference_habits": "long_term_preference_habits",
            "session_hotel_types": "long_term_hotel_types",
            "session_room_views": "long_term_room_views",
            "session_amenities": "long_term_amenities",
        }
        for update_field, profile_field in field_map.items():
            values = CurrentProfileMerger._read_applied_update_values(applied_updates.get(update_field))
            if values:
                CurrentProfileMerger._increment_score_map(getattr(candidate, profile_field), values)

        hidden_maps = CurrentProfileMerger._build_hidden_signal_maps(
            hidden_profile_signals,
            has_explicit_budget=bool(applied_updates.get("session_budget_levels")),
        )
        for profile_field, values in hidden_maps.items():
            CurrentProfileMerger._merge_score_map_into(getattr(candidate, profile_field), values)

        if "session_price_range_min" in applied_updates:
            candidate.long_term_price_range.min = session.session_price_range.min
        if "session_price_range_max" in applied_updates:
            candidate.long_term_price_range.max = session.session_price_range.max
        if "session_price_range_min" in applied_updates or "session_price_range_max" in applied_updates:
            candidate.long_term_price_range.currency = (
                session.session_price_range.currency or old_profile.long_term_price_range.currency
            )
        return candidate

    @staticmethod
    def _read_applied_update_values(raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            value = raw_value.strip()
            return [value] if value else []
        if not isinstance(raw_value, list):
            return []
        values: list[str] = []
        seen: set[str] = set()
        for item in raw_value:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values

    @staticmethod
    def _increment_score_map(target: dict[str, CountInteractionValue], values: list[str]) -> None:
        today = date.today().isoformat()
        for value in values:
            current = target.get(value)
            if current is None:
                target[value] = CountInteractionValue(count=1, last_interaction=today)
                continue
            target[value] = CountInteractionValue(
                count=current.count + 1,
                last_interaction=CurrentProfileMerger._latest_interaction(
                    current.last_interaction,
                    today,
                ),
            )

    @staticmethod
    def _merge_score_map_into(
        target: dict[str, CountInteractionValue],
        values: dict[str, CountInteractionValue],
    ) -> None:
        for key, value in values.items():
            current = target.get(key)
            if current is None:
                target[key] = CountInteractionValue(
                    count=value.count,
                    last_interaction=value.last_interaction,
                )
                continue
            target[key] = CountInteractionValue(
                count=current.count + value.count,
                last_interaction=CurrentProfileMerger._latest_interaction(
                    current.last_interaction,
                    value.last_interaction,
                ),
            )

    @staticmethod
    def _build_current_turn_session_signals(
        *,
        applied_updates: dict[str, Any] | None = None,
        hidden_profile_signals: list[Any] | None = None,
    ) -> dict[str, dict[str, CountInteractionValue]]:
        applied_updates = applied_updates or {}
        signals: dict[str, dict[str, CountInteractionValue]] = {
            "traveler_type": {},
            "long_term_trip_types": {},
            "long_term_budget_levels": {},
            "long_term_preference_habits": {},
            "long_term_hotel_types": {},
            "long_term_room_views": {},
            "long_term_amenities": {},
            "avoid_hotel_types": {},
            "avoid_amenities": {},
            "avoid_preference_habits": {},
            "avoid_nearby_places": {},
            "avoid_locations": {},
        }
        field_map = {
            "session_trip_types": "long_term_trip_types",
            "session_budget_levels": "long_term_budget_levels",
            "session_preference_habits": "long_term_preference_habits",
            "session_hotel_types": "long_term_hotel_types",
            "session_room_views": "long_term_room_views",
            "session_amenities": "long_term_amenities",
        }
        for update_field, profile_field in field_map.items():
            values = CurrentProfileMerger._read_applied_update_values(applied_updates.get(update_field))
            if values:
                CurrentProfileMerger._increment_score_map(signals[profile_field], values)

        hidden_maps = CurrentProfileMerger._build_hidden_signal_maps(
            hidden_profile_signals,
            has_explicit_budget=bool(applied_updates.get("session_budget_levels")),
        )
        for profile_field, values in hidden_maps.items():
            CurrentProfileMerger._merge_score_map_into(signals[profile_field], values)
        return signals

    def _build_retained_long_term_profile(
        self,
        *,
        old_profile: LongTermProfile,
        retention_candidate_profile: ActiveProfile,
        tagremoved_profile: LongTermProfile,
        decisions: dict[str, dict[str, list[str]]],
    ) -> LongTermProfile:
        return LongTermProfile(
            nationality=old_profile.nationality,
            age_group=old_profile.age_group,
            current_workplace=old_profile.current_workplace,
            is_enough=old_profile.is_enough,
            traveler_type=self._select_group_map(
                group_name="traveler_type",
                selected_keys=decisions.get("traveler_type", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_trip_types=self._select_group_map(
                group_name="long_term_trip_types",
                selected_keys=decisions.get("long_term_trip_types", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_budget_levels=self._select_group_map(
                group_name="long_term_budget_levels",
                selected_keys=decisions.get("long_term_budget_levels", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_price_range=PriceRange(
                min=retention_candidate_profile.long_term_price_range.min,
                max=retention_candidate_profile.long_term_price_range.max,
                currency=retention_candidate_profile.long_term_price_range.currency,
            ),
            long_term_preference_habits=self._select_group_map(
                group_name="long_term_preference_habits",
                selected_keys=decisions.get("long_term_preference_habits", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_hotel_types=self._select_group_map(
                group_name="long_term_hotel_types",
                selected_keys=decisions.get("long_term_hotel_types", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_room_views=self._select_group_map(
                group_name="long_term_room_views",
                selected_keys=decisions.get("long_term_room_views", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            long_term_amenities=self._select_group_map(
                group_name="long_term_amenities",
                selected_keys=decisions.get("long_term_amenities", {}).get("profile", []),
                primary_profile=retention_candidate_profile,
                secondary_profile=tagremoved_profile,
            ),
            recommendation_clicks=old_profile.recommendation_clicks,
            long_term_negative_preferences=NegativePreferences(
                avoid_hotel_types=self._select_group_map(
                    group_name="avoid_hotel_types",
                    selected_keys=decisions.get("avoid_hotel_types", {}).get("profile", []),
                    primary_profile=retention_candidate_profile,
                    secondary_profile=tagremoved_profile,
                ),
                avoid_amenities=self._select_group_map(
                    group_name="avoid_amenities",
                    selected_keys=decisions.get("avoid_amenities", {}).get("profile", []),
                    primary_profile=retention_candidate_profile,
                    secondary_profile=tagremoved_profile,
                ),
                avoid_preference_habits=self._select_group_map(
                    group_name="avoid_preference_habits",
                    selected_keys=decisions.get("avoid_preference_habits", {}).get("profile", []),
                    primary_profile=retention_candidate_profile,
                    secondary_profile=tagremoved_profile,
                ),
                avoid_nearby_places=self._select_group_map(
                    group_name="avoid_nearby_places",
                    selected_keys=decisions.get("avoid_nearby_places", {}).get("profile", []),
                    primary_profile=retention_candidate_profile,
                    secondary_profile=tagremoved_profile,
                ),
                avoid_locations=self._select_group_map(
                    group_name="avoid_locations",
                    selected_keys=decisions.get("avoid_locations", {}).get("profile", []),
                    primary_profile=retention_candidate_profile,
                    secondary_profile=tagremoved_profile,
                ),
            ),
        )

    def _build_tagremoved_profile(
        self,
        *,
        tagremoved_profile: LongTermProfile,
        retention_candidate_profile: ActiveProfile,
        decisions: dict[str, dict[str, list[str]]],
    ) -> LongTermProfile:
        return LongTermProfile(
            nationality=tagremoved_profile.nationality,
            age_group=tagremoved_profile.age_group,
            current_workplace=tagremoved_profile.current_workplace,
            is_enough=tagremoved_profile.is_enough,
            traveler_type=self._select_group_map(
                group_name="traveler_type",
                selected_keys=decisions.get("traveler_type", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_trip_types=self._select_group_map(
                group_name="long_term_trip_types",
                selected_keys=decisions.get("long_term_trip_types", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_budget_levels=self._select_group_map(
                group_name="long_term_budget_levels",
                selected_keys=decisions.get("long_term_budget_levels", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_price_range=PriceRange(
                min=tagremoved_profile.long_term_price_range.min,
                max=tagremoved_profile.long_term_price_range.max,
                currency=tagremoved_profile.long_term_price_range.currency,
            ),
            long_term_preference_habits=self._select_group_map(
                group_name="long_term_preference_habits",
                selected_keys=decisions.get("long_term_preference_habits", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_hotel_types=self._select_group_map(
                group_name="long_term_hotel_types",
                selected_keys=decisions.get("long_term_hotel_types", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_room_views=self._select_group_map(
                group_name="long_term_room_views",
                selected_keys=decisions.get("long_term_room_views", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            long_term_amenities=self._select_group_map(
                group_name="long_term_amenities",
                selected_keys=decisions.get("long_term_amenities", {}).get("tagremoved", []),
                primary_profile=tagremoved_profile,
                secondary_profile=retention_candidate_profile,
            ),
            recommendation_clicks=tagremoved_profile.recommendation_clicks,
            long_term_negative_preferences=NegativePreferences(
                avoid_hotel_types=self._select_group_map(
                    group_name="avoid_hotel_types",
                    selected_keys=decisions.get("avoid_hotel_types", {}).get("tagremoved", []),
                    primary_profile=tagremoved_profile,
                    secondary_profile=retention_candidate_profile,
                ),
                avoid_amenities=self._select_group_map(
                    group_name="avoid_amenities",
                    selected_keys=decisions.get("avoid_amenities", {}).get("tagremoved", []),
                    primary_profile=tagremoved_profile,
                    secondary_profile=retention_candidate_profile,
                ),
                avoid_preference_habits=self._select_group_map(
                    group_name="avoid_preference_habits",
                    selected_keys=decisions.get("avoid_preference_habits", {}).get("tagremoved", []),
                    primary_profile=tagremoved_profile,
                    secondary_profile=retention_candidate_profile,
                ),
                avoid_nearby_places=self._select_group_map(
                    group_name="avoid_nearby_places",
                    selected_keys=decisions.get("avoid_nearby_places", {}).get("tagremoved", []),
                    primary_profile=tagremoved_profile,
                    secondary_profile=retention_candidate_profile,
                ),
                avoid_locations=self._select_group_map(
                    group_name="avoid_locations",
                    selected_keys=decisions.get("avoid_locations", {}).get("tagremoved", []),
                    primary_profile=tagremoved_profile,
                    secondary_profile=retention_candidate_profile,
                ),
            ),
        )

    @staticmethod
    def _select_group_map(
        *,
        group_name: str,
        selected_keys: list[str],
        primary_profile: LongTermProfile | ActiveProfile,
        secondary_profile: LongTermProfile | ActiveProfile,
    ) -> dict[str, CountInteractionValue]:
        primary_map = CurrentProfileMerger._get_group_map(primary_profile, group_name)
        secondary_map = CurrentProfileMerger._get_group_map(secondary_profile, group_name)
        selected: dict[str, CountInteractionValue] = {}
        for key in selected_keys:
            primary_value = primary_map.get(key)
            secondary_value = secondary_map.get(key)
            if primary_value and secondary_value:
                selected[key] = CountInteractionValue(
                    count=primary_value.count + secondary_value.count,
                    last_interaction=CurrentProfileMerger._latest_interaction(
                        primary_value.last_interaction,
                        secondary_value.last_interaction,
                    ),
                )
            elif primary_value:
                selected[key] = CountInteractionValue(
                    count=primary_value.count,
                    last_interaction=primary_value.last_interaction,
                )
            elif secondary_value:
                selected[key] = CountInteractionValue(
                    count=secondary_value.count,
                    last_interaction=secondary_value.last_interaction,
                )
        return selected

    @staticmethod
    def _get_group_map(
        profile: LongTermProfile | ActiveProfile,
        group_name: str,
    ) -> dict[str, CountInteractionValue]:
        if group_name.startswith("avoid_"):
            return getattr(profile.long_term_negative_preferences, group_name)
        return getattr(profile, group_name)

    @staticmethod
    def _clone_score_map(values: dict[str, CountInteractionValue]) -> dict[str, CountInteractionValue]:
        return {
            key: CountInteractionValue(
                count=value.count,
                last_interaction=value.last_interaction,
            )
            for key, value in values.items()
        }

    @staticmethod
    def _active_profile_from_long_term(long_term: LongTermProfile) -> ActiveProfile:
        return ActiveProfile(
            nationality=long_term.nationality,
            age_group=long_term.age_group,
            current_workplace=long_term.current_workplace,
            is_enough=long_term.is_enough,
            traveler_type=CurrentProfileMerger._clone_score_map(long_term.traveler_type),
            long_term_trip_types=CurrentProfileMerger._clone_score_map(long_term.long_term_trip_types),
            long_term_budget_levels=CurrentProfileMerger._clone_score_map(long_term.long_term_budget_levels),
            long_term_price_range=PriceRange(
                min=long_term.long_term_price_range.min,
                max=long_term.long_term_price_range.max,
                currency=long_term.long_term_price_range.currency,
            ),
            long_term_preference_habits=CurrentProfileMerger._clone_score_map(
                long_term.long_term_preference_habits
            ),
            long_term_hotel_types=CurrentProfileMerger._clone_score_map(long_term.long_term_hotel_types),
            long_term_room_views=CurrentProfileMerger._clone_score_map(long_term.long_term_room_views),
            long_term_amenities=CurrentProfileMerger._clone_score_map(long_term.long_term_amenities),
            recommendation_clicks=long_term.recommendation_clicks,
            long_term_negative_preferences=NegativePreferences(
                avoid_hotel_types=CurrentProfileMerger._clone_score_map(
                    long_term.long_term_negative_preferences.avoid_hotel_types
                ),
                avoid_amenities=CurrentProfileMerger._clone_score_map(
                    long_term.long_term_negative_preferences.avoid_amenities
                ),
                avoid_preference_habits=CurrentProfileMerger._clone_score_map(
                    long_term.long_term_negative_preferences.avoid_preference_habits
                ),
                avoid_nearby_places=CurrentProfileMerger._clone_score_map(
                    long_term.long_term_negative_preferences.avoid_nearby_places
                ),
                avoid_locations=CurrentProfileMerger._clone_score_map(
                    long_term.long_term_negative_preferences.avoid_locations
                ),
            ),
        )

    @staticmethod
    def _build_promoted_preference_habits(session: SessionContext) -> dict[str, CountInteractionValue]:
        promoted: dict[str, CountInteractionValue] = {}
        for source in (
            session.session_preference_habits,
            session.session_amenities,
        ):
            for key, value in source.items():
                if value.count <= PREFERENCE_PROMOTION_MIN_COUNT:
                    continue
                current = promoted.get(key)
                if current is None:
                    promoted[key] = CountInteractionValue(
                        count=value.count,
                        last_interaction=value.last_interaction,
                    )
                    continue
                promoted[key] = CountInteractionValue(
                    count=current.count + value.count,
                    last_interaction=CurrentProfileMerger._latest_interaction(
                        current.last_interaction,
                        value.last_interaction,
                    ),
                )
        return promoted

    @staticmethod
    def _merge_score_maps(
        long_term_map: dict[str, CountInteractionValue],
        session_map: dict[str, CountInteractionValue],
    ) -> dict[str, CountInteractionValue]:
        merged: dict[str, CountInteractionValue] = {
            key: CountInteractionValue(count=value.count, last_interaction=value.last_interaction)
            for key, value in long_term_map.items()
        }
        for key, value in session_map.items():
            current = merged.get(key)
            if current is None:
                merged[key] = CountInteractionValue(
                    count=value.count,
                    last_interaction=value.last_interaction,
                )
                continue
            merged[key] = CountInteractionValue(
                count=current.count + value.count,
                last_interaction=CurrentProfileMerger._latest_interaction(
                    current.last_interaction,
                    value.last_interaction,
                ),
            )
        return merged

    @staticmethod
    def _build_hidden_signal_maps(
        hidden_profile_signals: list[Any] | None,
        *,
        has_explicit_budget: bool,
    ) -> dict[str, dict[str, CountInteractionValue]]:
        maps: dict[str, dict[str, CountInteractionValue]] = {
            "traveler_type": {},
            "long_term_budget_levels": {},
            "long_term_preference_habits": {},
        }
        if not hidden_profile_signals:
            return maps

        today = date.today().isoformat()
        for signal in hidden_profile_signals:
            group = CurrentProfileMerger._read_signal_attr(signal, "group")
            value = CurrentProfileMerger._read_signal_attr(signal, "value")
            if group not in maps or not value:
                continue
            if group == "long_term_budget_levels" and has_explicit_budget:
                continue
            current = maps[group].get(value)
            if current is None:
                maps[group][value] = CountInteractionValue(count=1, last_interaction=today)
                continue
            maps[group][value] = CountInteractionValue(
                count=current.count + 1,
                last_interaction=CurrentProfileMerger._latest_interaction(current.last_interaction, today),
            )
        return maps

    @staticmethod
    def _read_signal_attr(signal: Any, name: str) -> str:
        if isinstance(signal, dict):
            return str(signal.get(name, "")).strip()
        return str(getattr(signal, name, "")).strip()

    @staticmethod
    def _merge_price_range(long_term: LongTermProfile, session: SessionContext) -> PriceRange:
        return PriceRange(
            min=(
                session.session_price_range.min
                if session.session_price_range.min is not None
                else long_term.long_term_price_range.min
            ),
            max=(
                session.session_price_range.max
                if session.session_price_range.max is not None
                else long_term.long_term_price_range.max
            ),
            currency=session.session_price_range.currency or long_term.long_term_price_range.currency,
        )

    @staticmethod
    def _latest_interaction(first: str, second: str) -> str:
        return max(first, second)
