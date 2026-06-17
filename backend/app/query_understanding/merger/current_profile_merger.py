from __future__ import annotations

from dataclasses import dataclass

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
    def merge(self, user_profile: UserProfile) -> ActiveProfile:
        long_term = user_profile.long_term_profile
        session = user_profile.session_context

        return ActiveProfile(
            nationality=long_term.nationality,
            age_group=long_term.age_group,
            current_workplace=long_term.current_workplace,
            is_enough=long_term.is_enough,
            traveler_type=self._merge_score_maps(long_term.traveler_type, {}),
            long_term_trip_types=self._merge_score_maps(
                long_term.long_term_trip_types,
                session.session_trip_types,
            ),
            long_term_budget_levels=self._merge_score_maps(
                long_term.long_term_budget_levels,
                session.session_budget_levels,
            ),
            long_term_price_range=self._merge_price_range(long_term, session),
            long_term_preference_habits=self._merge_score_maps(
                long_term.long_term_preference_habits,
                self._build_promoted_preference_habits(session),
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
