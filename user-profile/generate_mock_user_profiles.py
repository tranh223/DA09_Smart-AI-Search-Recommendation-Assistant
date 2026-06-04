"""
Generate mock OTA user profiles.

Output:
    mock_user_profiles.json

Schema:
    Matches the latest user profile schema:
    - user_id
    - name
    - long_term_profile
    - session_context

Usage:
    python generate_mock_user_profiles.py

Optional:
    Change USER_COUNT below if you want more or fewer users.
"""

import json
import random
from pathlib import Path


USER_COUNT = 50
OUTPUT_FILE = "user-profile/mock_user_profiles.json"
RANDOM_SEED = 20260604

random.seed(RANDOM_SEED)


HOTEL_TYPES = [
    "hotel",
    "homestay",
    "guesthouse",
    "hostel",
    "resort",
    "villa",
    "boutique_hotel",
    "budget_hotel",
    "premium_hotel",
    "luxury_hotel",
]

AMENITIES = [
    "pool",
    "wifi",
    "spa",
    "breakfast",
    "bar",
    "parking",
    "elevator",
    "kids_club",
    "shuttle_service",
    "pet_friendly",
    "soundproof",
]

SESSION_AMENITIES = AMENITIES + ["smoke"]

LONG_TERM_PREFERENCE_TAGS = [
    "luxury",
    "comfort",
    "quiet",
    "privacy",
    "unique",
    "safe",
    "lively",
]

SESSION_PREFERENCE_TAGS = LONG_TERM_PREFERENCE_TAGS + [
    "near_attraction",
    "near_beach",
    "city_center",
    "fast_checkin",
    "pet_friendly",
]

AVOID_TAGS = [
    "noisy",
    "nightlife",
    "city_center",
    "far_from_center",
    "shared_room",
    "low_rating",
    "old_facility",
    "small_room",
    "unsafe_area",
    "crowded",
    "limited_service",
    "poor_cleanliness",
]

AVOID_LOCATIONS = [
    "red_light_area",
    "crowded_center",
    "remote_area",
    "industrial_area",
    "night_market_area",
    "isolated_area",
    "far_from_airport",
]

DESTINATIONS = [
    "Phu Quoc",
    "Da Nang",
    "Nha Trang",
    "Da Lat",
    "Ha Noi",
    "Ho Chi Minh City",
    "Hoi An",
    "Hue",
    "Vung Tau",
    "Sa Pa",
    None,
]

CURRENT_LOCATIONS = [
    "Ha Noi",
    "Ho Chi Minh City",
    "Da Nang",
    "Can Tho",
    "Hai Phong",
    "Tokyo",
    "Seoul",
    "Singapore",
    "Paris",
    "London",
    "Berlin",
    "Sydney",
    "Bangkok",
    "Kuala Lumpur",
    None,
]

NEARBY_PLACES = [
    "VinWonders",
    "My Khe Beach",
    "Old Quarter",
    "Dragon Bridge",
    "Long Beach",
    "Airport",
    "City Center",
    "Night Market",
    "Ancient Town",
    "Hoan Kiem Lake",
    "Beach",
    "Imperial City",
    "Marble Mountains",
    "Back Beach",
    None,
]

VIETNAMESE_NAMES = [
    "Minh Anh Nguyen",
    "Hoang Nam Tran",
    "Thu Ha Le",
    "Gia Huy Pham",
    "Thanh Tung Do",
    "Quoc Bao Nguyen",
    "Mai Linh Hoang",
    "Duc Anh Bui",
    "Anh Khoa Vo",
    "Phuong Thao Mai",
    "Gia Bao Le",
    "Khanh Vy Nguyen",
    "Thanh Son Pham",
    "Linh Nguyen",
    "Ngoc Tran",
    "Duc Manh Hoang",
    "Thu Trang Pham",
    "Van Phuc Nguyen",
    "Bao Chau Nguyen",
    "Minh Tri Phan",
    "Minh Quan Dang",
    "Ngoc Huyen Nguyen",
    "Minh Khoi Le",
    "Gia Bao Tran",
    "Thanh Lam Bui",
    "Ngoc Lan Pham",
    "Bao Anh Le",
    "Quang Huy Nguyen",
    "Phuong Linh Tran",
    "Tuan Anh Do",
]

FOREIGN_NAMES = [
    "Emily Carter",
    "Michael Brown",
    "Yuki Sato",
    "Minjun Kim",
    "Claire Dubois",
    "Robert Wilson",
    "Anna Muller",
    "Sarah Johnson",
    "Thomas Lee",
    "Ivan Petrov",
    "Chen Wei",
    "Aisha Rahman",
    "Olivia Smith",
    "Mark Davis",
    "James Miller",
    "Maria Garcia",
    "Luca Rossi",
    "Hannah Schmidt",
    "Noah Anderson",
    "Emma Taylor",
    "David Wilson",
    "Sofia Martinez",
    "Daniel Lee",
    "Yuna Park",
    "Lucas Martin",
    "Sophie Martin",
    "Oliver Smith",
    "Isabella Garcia",
    "Ethan Brown",
    "Mia Johnson",
]


def maybe_null(value, probability=0.06):
    """Return None with a small probability."""
    return None if random.random() < probability else value


def sample_list(items, min_n=1, max_n=4, null_p=0.08, empty_p=0.08):
    """
    Return a random list, None, or [].

    This is intentional because recommendation systems need to handle:
    - complete profiles
    - sparse profiles
    - cold-start users
    """
    r = random.random()

    if r < null_p:
        return None

    if r < null_p + empty_p:
        return []

    n = random.randint(min_n, min(max_n, len(items)))
    return random.sample(items, n)


def price_range(level):
    """Return VND price range from budget level."""
    if level == "low":
        return random.choice(
            [
                (300000, 1500000),
                (500000, 1800000),
                (None, 2000000),
            ]
        )

    if level == "medium":
        return random.choice(
            [
                (1500000, 3500000),
                (2000000, 5000000),
                (None, 4500000),
            ]
        )

    if level == "high":
        return random.choice(
            [
                (4000000, 9000000),
                (5000000, 12000000),
                (7000000, 15000000),
            ]
        )

    return None, None


def budget_from_profile(nationality, age_group):
    """
    Generate a realistic long-term budget level.

    These are mock assumptions only.
    They should be treated as soft recommendation signals, not hard rules.
    """
    if nationality == "foreign":
        return random.choice(["medium", "high", "high", "unknown", None])

    if age_group == "under_25":
        return random.choice(["low", "low", "medium", "unknown"])

    if age_group == "25_35":
        return random.choice(["medium", "medium", "high", "unknown"])

    if age_group == "over_35":
        return random.choice(["medium", "high", "high", "unknown"])

    return random.choice(["unknown", "medium", None])


def make_negative_preferences():
    """Generate negative preference object."""
    if random.random() < 0.18:
        return {
            "avoid_hotel_types": [],
            "avoid_amenities": [],
            "avoid_tags": [],
            "avoid_nearby_places": [],
            "avoid_locations": [],
        }

    nearby_places_no_null = [place for place in NEARBY_PLACES if place is not None]

    return {
        "avoid_hotel_types": sample_list(HOTEL_TYPES, 0, 2, null_p=0, empty_p=0.35) or [],
        "avoid_amenities": sample_list(AMENITIES, 0, 2, null_p=0, empty_p=0.35) or [],
        "avoid_tags": sample_list(AVOID_TAGS, 1, 3, null_p=0, empty_p=0.25) or [],
        "avoid_nearby_places": sample_list(nearby_places_no_null, 0, 2, null_p=0, empty_p=0.45) or [],
        "avoid_locations": sample_list(AVOID_LOCATIONS, 0, 2, null_p=0, empty_p=0.45) or [],
    }


def make_date_pair():
    """Generate check-in/check-out datetime strings or nulls."""
    if random.random() < 0.42:
        return None, None

    month = random.choice([7, 8, 9, 10, 11, 12])
    day = random.randint(1, 24)
    stay = random.randint(1, 5)

    check_in = f"2026-{month:02d}-{day:02d}T14:00:00"
    check_out = f"2026-{month:02d}-{day + stay:02d}T12:00:00"

    return check_in, check_out


def guests_for_trip(trip_type):
    """Generate number of guests from trip type."""
    if trip_type == "solo":
        return 1

    if trip_type == "couple":
        return 2

    if trip_type == "business":
        return random.choice([1, 2])

    if trip_type == "family":
        return random.choice([3, 4, 5, 6])

    if trip_type == "group":
        return random.choice([4, 5, 6, 8])

    if trip_type == "tourist":
        return random.choice([1, 2, 3])

    return None


def cold_start_user(index, name, nationality):
    """Generate a sparse profile for cold-start testing."""
    return {
        "user_id": f"user_{index:03d}",
        "name": name,
        "long_term_profile": {
            "nationality": nationality,
            "age_group": random.choice(["unknown", None]),
            "current_workplace": None,
            "traveler_type": random.choice(["unknown", None]),
            "long_term_trip_type": "unknown",
            "long_term_budget_level": "unknown",
            "long_term_price_range": {
                "min": None,
                "max": None,
                "currency": None,
            },
            "long_term_preference_tags": None,
            "long_term_hotel_types": None,
            "long_term_amenities": None,
            "long_term_negative_preferences": {
                "avoid_hotel_types": [],
                "avoid_amenities": [],
                "avoid_tags": [],
                "avoid_nearby_places": [],
                "avoid_locations": [],
            },
        },
        "session_context": {
            "destination": random.choice(DESTINATIONS),
            "current_location": None,
            "nearby_place": None,
            "number_of_guests": None,
            "has_pet": None,
            "has_children": None,
            "check_in": None,
            "check_out": None,
            "session_trip_type": random.choice(["unknown", None]),
            "session_budget_level": "unknown",
            "session_price_range": {
                "min": None,
                "max": None,
                "currency": None,
            },
            "session_preference_tags": None,
            "session_hotel_types": None,
            "session_amenities": None,
            "session_negative_preferences": {
                "avoid_hotel_types": [],
                "avoid_amenities": [],
                "avoid_tags": [],
                "avoid_nearby_places": [],
                "avoid_locations": [],
            },
        },
    }


def make_user(index, name, nationality):
    """Generate one mock user profile."""
    if index in [8, 19, 31, 45, 60]:
        return cold_start_user(
            index=index,
            name=None if index == 60 else name,
            nationality=random.choice([nationality, "unknown", None]),
        )

    age_group = maybe_null(
        random.choice(["under_25", "25_35", "over_35", "unknown"]),
        probability=0.05,
    )

    traveler_type = maybe_null(
        random.choice(["explorer", "comfort_seeker", "planner", "spontaneous", "unknown"]),
        probability=0.05,
    )

    long_trip_type = maybe_null(
        random.choice(["solo", "tourist", "business", "family", "couple", "group", "unknown"]),
        probability=0.06,
    )

    long_budget_level = budget_from_profile(nationality, age_group)
    long_min_price, long_max_price = price_range(long_budget_level)

    session_trip_type = maybe_null(
        random.choice(["solo", "tourist", "business", "family", "couple", "group", "unknown"]),
        probability=0.06,
    )

    guests = guests_for_trip(session_trip_type)

    has_children = (
        True
        if session_trip_type == "family" and random.random() < 0.7
        else random.choice([False, False, None])
    )

    has_pet = True if random.random() < 0.12 else random.choice([False, False, None])

    session_budget_level = random.choice([long_budget_level, "low", "medium", "high", "unknown", None])
    session_min_price, session_max_price = price_range(session_budget_level)

    check_in, check_out = make_date_pair()

    return {
        "user_id": f"user_{index:03d}",
        "name": maybe_null(name, probability=0.04),
        "long_term_profile": {
            "nationality": maybe_null(nationality, probability=0.04),
            "age_group": age_group,
            "current_workplace": random.choice(CURRENT_LOCATIONS),
            "traveler_type": traveler_type,
            "long_term_trip_type": long_trip_type,
            "long_term_budget_level": long_budget_level,
            "long_term_price_range": {
                "min": long_min_price,
                "max": long_max_price,
                "currency": "VND" if (long_min_price is not None or long_max_price is not None) else None,
            },
            "long_term_preference_tags": sample_list(LONG_TERM_PREFERENCE_TAGS, 1, 3),
            "long_term_hotel_types": sample_list(HOTEL_TYPES, 1, 4),
            "long_term_amenities": sample_list(AMENITIES, 1, 5),
            "long_term_negative_preferences": make_negative_preferences(),
        },
        "session_context": {
            "destination": random.choice(DESTINATIONS),
            "current_location": random.choice(CURRENT_LOCATIONS),
            "nearby_place": random.choice(NEARBY_PLACES),
            "number_of_guests": guests,
            "has_pet": has_pet,
            "has_children": has_children,
            "check_in": check_in,
            "check_out": check_out,
            "session_trip_type": session_trip_type,
            "session_budget_level": session_budget_level,
            "session_price_range": {
                "min": session_min_price,
                "max": session_max_price,
                "currency": "VND" if (session_min_price is not None or session_max_price is not None) else None,
            },
            "session_preference_tags": sample_list(SESSION_PREFERENCE_TAGS, 1, 4),
            "session_hotel_types": sample_list(HOTEL_TYPES, 1, 3),
            "session_amenities": sample_list(SESSION_AMENITIES, 1, 5),
            "session_negative_preferences": make_negative_preferences(),
        },
    }


def generate_profiles(user_count=USER_COUNT):
    """Generate all mock profiles."""
    profiles = []

    for index in range(1, user_count + 1):
        if index <= user_count // 2:
            name = VIETNAMESE_NAMES[(index - 1) % len(VIETNAMESE_NAMES)]
            nationality = random.choice(["vietnamese", "vietnamese", "vietnamese", "unknown"])
        else:
            name = FOREIGN_NAMES[(index - 1 - user_count // 2) % len(FOREIGN_NAMES)]
            nationality = random.choice(["foreign", "foreign", "foreign", "unknown"])

        profiles.append(make_user(index, name, nationality))

    apply_demo_overrides(profiles)

    return profiles


def apply_demo_overrides(profiles):
    """
    Make a few profiles more intentional for easy demo/testing.
    This helps when testing recommendation behavior manually.
    """
    if len(profiles) < 15:
        return

    profiles[0].update(
        {
            "user_id": "user_001",
            "name": "Minh Anh Nguyen",
        }
    )
    profiles[0]["long_term_profile"].update(
        {
            "nationality": "vietnamese",
            "age_group": "under_25",
            "traveler_type": "explorer",
            "long_term_trip_type": "tourist",
            "long_term_budget_level": "low",
            "long_term_price_range": {"min": 500000, "max": 1800000, "currency": "VND"},
            "long_term_preference_tags": ["unique", "lively", "safe"],
            "long_term_hotel_types": ["homestay", "hostel", "guesthouse"],
            "long_term_amenities": ["wifi", "breakfast"],
        }
    )
    profiles[0]["session_context"].update(
        {
            "destination": "Da Nang",
            "current_location": "Ho Chi Minh City",
            "nearby_place": "My Khe Beach",
            "number_of_guests": 2,
            "has_pet": False,
            "has_children": False,
            "check_in": None,
            "check_out": None,
            "session_trip_type": "tourist",
            "session_budget_level": "low",
            "session_price_range": {"min": 500000, "max": 1500000, "currency": "VND"},
            "session_preference_tags": ["unique", "near_beach", "lively"],
            "session_hotel_types": ["homestay", "budget_hotel"],
            "session_amenities": ["wifi"],
        }
    )

    profiles[4]["long_term_profile"].update(
        {
            "nationality": "vietnamese",
            "age_group": "over_35",
            "traveler_type": "comfort_seeker",
            "long_term_trip_type": "business",
            "long_term_budget_level": "high",
            "long_term_hotel_types": ["premium_hotel", "luxury_hotel", "resort"],
            "long_term_amenities": ["wifi", "spa", "breakfast", "shuttle_service", "soundproof"],
        }
    )
    profiles[4]["session_context"].update(
        {
            "session_trip_type": "business",
            "destination": "Ho Chi Minh City",
            "nearby_place": "City Center",
            "number_of_guests": 1,
            "session_amenities": ["wifi", "shuttle_service", "soundproof"],
            "session_negative_preferences": {
                "avoid_hotel_types": ["hostel", "guesthouse"],
                "avoid_amenities": ["bar"],
                "avoid_tags": ["noisy", "old_facility", "low_rating"],
                "avoid_nearby_places": ["Night Market"],
                "avoid_locations": ["crowded_center"],
            },
        }
    )

    profiles[14]["session_context"].update(
        {
            "session_trip_type": "family",
            "destination": "Phu Quoc",
            "nearby_place": "VinWonders",
            "number_of_guests": 4,
            "has_children": True,
            "has_pet": False,
            "session_budget_level": "medium",
            "session_price_range": {"min": 2000000, "max": 5000000, "currency": "VND"},
            "session_preference_tags": ["comfort", "safe", "near_attraction"],
            "session_hotel_types": ["resort", "hotel"],
            "session_amenities": ["pool", "kids_club", "breakfast"],
        }
    )

    if len(profiles) > 31:
        profiles[31]["long_term_profile"].update(
            {
                "nationality": "foreign",
                "age_group": "25_35",
                "traveler_type": "explorer",
                "long_term_budget_level": "high",
                "long_term_preference_tags": ["unique", "comfort", "lively"],
                "long_term_hotel_types": ["boutique_hotel", "resort", "hotel"],
            }
        )
        profiles[31]["session_context"].update(
            {
                "session_trip_type": "tourist",
                "destination": "Ha Noi",
                "nearby_place": "Old Quarter",
                "session_preference_tags": ["unique", "city_center", "lively"],
                "session_amenities": ["wifi", "breakfast"],
            }
        )


def validate_ascii_only(path):
    """Ensure the generated file contains only ASCII characters."""
    raw = Path(path).read_text(encoding="utf-8")
    non_ascii = sorted(set(ch for ch in raw if ord(ch) > 127))

    if non_ascii:
        raise ValueError(f"Generated file contains non-ASCII characters: {non_ascii[:10]}")


def main():
    profiles = generate_profiles(USER_COUNT)

    output = {
        "schema_version": "user_profile_mock",
        "language": "en",
        "count": len(profiles),
        "users": profiles,
    }

    output_path = Path(OUTPUT_FILE)
    output_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    validate_ascii_only(output_path)

    print(f"Created {output_path.resolve()}")
    print(f"Users: {len(profiles)}")
    print("Language: English only")
    print("ASCII validation: passed")


if __name__ == "__main__":
    main()
