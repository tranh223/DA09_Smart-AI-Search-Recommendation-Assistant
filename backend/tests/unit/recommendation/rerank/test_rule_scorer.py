from app.recommendation.rerank.profile_normalizer import normalize_profile
from app.recommendation.rerank.rule_scorer import hard_filter, score_candidate


def profile():
    return normalize_profile(
        {
            "user_id": "u1",
            "session_context": {
                "destination": "Vung Tau",
                "session_price_range": {"min": 7000000, "max": 15000000, "currency": "VND"},
                "session_hotel_types": {"Resort": {"count": 10}},
                "session_room_views": {"Hướng Hồ": {"count": 5}},
                "session_amenities": {"Tắm suối nước nóng": {"count": 5}},
                "session_trip_types": {"Gia đình có trẻ nhỏ": {"count": 5}},
                "session_preference_habits": {"privacy": {"count": 3}},
                "session_negative_preferences": {
                    "avoid_amenities": {"Ban công sân hiên": {"count": 10}},
                    "avoid_preference_habits": {},
                    "avoid_hotel_types": {},
                    "avoid_nearby_places": {},
                    "avoid_locations": {},
                },
            },
            "long_term_profile": {},
        }
    )


def hotel(**overrides):
    data = {
        "item_id": "1",
        "destination": "Vung Tau",
        "hotel_type": "Resort",
        "price_min": 8000000,
        "price_max": 12000000,
        "amenities": ["Tắm suối nước nóng"],
        "room_views": ["Hướng Hồ"],
        "preference_habits": ["privacy"],
        "tags": ["Gia đình có trẻ nhỏ"],
        "location_tags": ["near_center"],
        "nearby_places": [],
        "rating": 4.6,
        "review_sentiment": 0.8,
        "available": True,
        "available_rooms": 6,
        "keyword_score": 0.8,
    }
    data.update(overrides)
    return data


def test_hard_filters_destination_and_availability():
    assert hard_filter(profile(), hotel(destination="Da Nang")) == (False, "destination_mismatch")
    assert hard_filter(profile(), hotel(available=False))[0] is False


def test_destination_filter_is_accent_insensitive():
    assert hard_filter(profile(), hotel(destination="Vũng Tàu")) == (True, None)


def test_strong_negative_filter():
    assert hard_filter(profile(), hotel(amenities=["Ban công sân hiên"])) == (False, "strong_avoid_amenity")


def test_rule_score_has_expected_features():
    result = score_candidate(profile(), hotel(), {"trend_score": 0.75})
    assert not result.filtered
    assert result.feature_scores["budget"] > 0.5
    assert result.feature_scores["amenity"] == 1.0
    assert result.feature_scores["room_view"] == 1.0
    assert result.feature_scores["trend"] == 0.75
    assert result.base_score > 0.6


def test_personalization_ignores_invented_tags():
    base = score_candidate(profile(), hotel(preference_habits=[], tags=["family_friendly", "nightlife", "near_center"]))
    matched = score_candidate(profile(), hotel(preference_habits=["privacy"], tags=["Gia đình có trẻ nhỏ"]))
    assert base.feature_scores["personalization"] < matched.feature_scores["personalization"]


def test_location_ignores_location_tags_for_positive_score():
    assert score_candidate(profile(), hotel(location_tags=["near_center", "tourist_area"])).feature_scores["location"] == 0.45

def test_boost_amenity_rich_hotels_session_note_increases_amenity_score():
    boosted_profile = normalize_profile(
        {
            "user_id": "u1",
            "session_context": {
                "destination": "Vung Tau",
                "boost_amenity_rich_hotels": True,
            },
            "long_term_profile": {},
        }
    )
    result = score_candidate(boosted_profile, hotel(amenities=["Spa", "Bể bơi", "Gym", "WiFi miễn phí", "Nhà hàng"]))
    assert result.feature_scores["amenity"] > 0.5
