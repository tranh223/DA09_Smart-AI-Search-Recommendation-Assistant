from app.recommendation.rerank.profile_normalizer import normalize_count_group, normalize_profile


def test_normalize_count_group_preserves_labels_and_weights():
    group = {"Ryokan": {"count": 27}, "Nhà nghỉ": {"count": 2}}
    assert normalize_count_group(group) == {"Ryokan": 1.0, "Nhà nghỉ": 0.074}


def test_normalize_count_group_handles_bad_values():
    assert normalize_count_group(None) == {}
    assert normalize_count_group([]) == {}
    assert normalize_count_group({"x": {}}) == {"x": 0.0}


def test_normalize_profile_click_ids_are_strings():
    profile = {
        "user_id": "u1",
        "long_term_profile": {"recommendation_clicks": {"hotel": [1, "2", {"hotel_id": 3}]}},
        "session_context": {},
    }
    normalized = normalize_profile(profile)
    assert normalized["long_term"]["recommendation_clicks"]["hotel"] == ["1", "2", "3"]


def test_normalize_profile_session_examples():
    profile = {
        "user_id": "user_002",
        "session_context": {
            "session_room_views": {
                "Hướng Ngoài trời": {"count": 8},
                "Hướng Hồ": {"count": 28},
            }
        },
        "long_term_profile": {},
    }
    normalized = normalize_profile(profile)
    assert normalized["session"]["room_views"]["Hướng Hồ"] == 1.0
    assert normalized["session"]["room_views"]["Hướng Ngoài trời"] == 0.286
