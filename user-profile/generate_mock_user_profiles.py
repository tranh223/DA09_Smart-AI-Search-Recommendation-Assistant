"""
Generate weighted graph-friendly mock OTA user profiles.

Output:
    mock_user_profiles.json

Usage:
    python user-profile/generate_mock_user_profiles.py
"""

import json
import random
from pathlib import Path


USER_COUNT = 50
RANDOM_SEED = 20260604
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "mock_user_profiles.json"

random.seed(RANDOM_SEED)


TRAVELER_TYPES = ["explorer", "comfort_seeker", "planner", "spontaneous"]
TRIP_TYPES = ["solo", "tourist", "business", "family", "couple", "group"]
BUDGET_LEVELS = ["low", "medium", "high"]

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

HOTEL_IDS = [f"hotel_{index:04d}" for index in range(1, 121)]

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
    "Maria Garcia",
    "Luca Rossi",
    "Hannah Schmidt",
    "Noah Anderson",
    "Emma Taylor",
    "David Wilson",
]


def maybe_null(value, probability=0.06):
    return None if random.random() < probability else value


def positive_weight():
    return round(random.uniform(0.15, 1.0), 2)


def negative_weight():
    return round(random.uniform(-1.0, -0.15), 2)


def weighted_map(items, min_n=1, max_n=4, null_p=0.08, empty_p=0.1):
    r = random.random()
    if r < null_p:
        return None
    if r < null_p + empty_p:
        return {}

    n = random.randint(min_n, min(max_n, len(items)))
    return {item: positive_weight() for item in random.sample(items, n)}


def negative_weighted_map(items, min_n=0, max_n=3, empty_p=0.35):
    if random.random() < empty_p:
        return {}

    n = random.randint(min_n, min(max_n, len(items)))
    if n == 0:
        return {}

    return {item: negative_weight() for item in random.sample(items, n)}


def price_range(levels):
    if not levels:
        return {"min": None, "max": None, "currency": None}

    level = max(levels, key=levels.get)
    ranges = {
        "low": [(300000, 1500000), (500000, 1800000), (None, 2000000)],
        "medium": [(1500000, 3500000), (2000000, 5000000), (None, 4500000)],
        "high": [(4000000, 9000000), (5000000, 12000000), (7000000, 15000000)],
    }
    min_price, max_price = random.choice(ranges.get(level, [(None, None)]))
    return {
        "min": min_price,
        "max": max_price,
        "currency": "VND" if min_price is not None or max_price is not None else None,
    }


def make_date_pair():
    if random.random() < 0.4:
        return None, None

    month = random.choice([7, 8, 9, 10, 11, 12])
    day = random.randint(1, 23)
    stay = random.randint(1, 5)
    return f"2026-{month:02d}-{day:02d}T14:00:00", f"2026-{month:02d}-{day + stay:02d}T12:00:00"


def make_click_time():
    month = random.choice([1, 2, 3, 4, 5, 6])
    day = random.randint(1, 26)
    hour = random.randint(8, 23)
    minute = random.choice([0, 5, 10, 15, 20, 30, 45])
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


def click_map(ids, min_n=0, max_n=5, null_time_p=0.12):
    n = random.randint(min_n, min(max_n, len(ids)))
    if n == 0:
        return {}

    return {
        item_id: {
            "click_count": random.randint(1, 18),
            "last_clicked_at": maybe_null(make_click_time(), null_time_p),
        }
        for item_id in random.sample(ids, n)
    }


def make_recommendation_clicks(empty_p=0.18, null_p=0.06):
    r = random.random()
    if r < null_p:
        return None
    if r < null_p + empty_p:
        return {
            "hotel": {},
        }

    return {
        "hotel": click_map(HOTEL_IDS, 1, 5),
    }


def guests_for_trip(trip_types):
    if not trip_types:
        return None

    trip_type = max(trip_types, key=trip_types.get)
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
    return random.choice([1, 2, 3])


def make_negative_preferences():
    nearby_places = [place for place in NEARBY_PLACES if place is not None]
    return {
        "avoid_hotel_types": negative_weighted_map(HOTEL_TYPES, 0, 2),
        "avoid_amenities": negative_weighted_map(SESSION_AMENITIES, 0, 2),
        "avoid_tags": negative_weighted_map(AVOID_TAGS, 1, 3, empty_p=0.22),
        "avoid_nearby_places": negative_weighted_map(nearby_places, 0, 2, empty_p=0.5),
        "avoid_locations": negative_weighted_map(AVOID_LOCATIONS, 0, 2, empty_p=0.45),
    }


def maybe_omit(data, keys, probability=0.06):
    for key in keys:
        if key in data and random.random() < probability:
            del data[key]


def make_cold_start_user(index, name, nationality):
    profile = {
        "user_id": f"user_{index:03d}",
        "name": maybe_null(name, 0.35),
        "long_term_profile": {
            "nationality": maybe_null(nationality, 0.45),
            "age_group": None,
            "current_workplace": None,
            "traveler_type": {},
            "long_term_trip_types": {},
            "long_term_budget_levels": {},
            "long_term_price_range": {"min": None, "max": None, "currency": None},
            "long_term_preference_tags": {},
            "long_term_hotel_types": {},
            "long_term_amenities": {},
            "recommendation_clicks": make_recommendation_clicks(empty_p=0.7, null_p=0.1),
            "long_term_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_tags": {},
                "avoid_nearby_places": {},
                "avoid_locations": {},
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
            "session_trip_types": {},
            "session_budget_levels": {},
            "session_price_range": {"min": None, "max": None, "currency": None},
            "session_preference_tags": {},
            "session_hotel_types": {},
            "session_amenities": {},
            "session_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_tags": {},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
        },
    }
    maybe_omit(profile["long_term_profile"], ["traveler_type", "long_term_preference_tags"], 0.25)
    maybe_omit(profile["session_context"], ["nearby_place", "session_amenities"], 0.25)
    return profile


def make_user(index, name, nationality):
    if index in {8, 19, 31, 45}:
        return make_cold_start_user(index, name, nationality)

    age_group = maybe_null(random.choice(["under_25", "25_35", "over_35"]), 0.08)
    traveler_type = weighted_map(TRAVELER_TYPES, 1, 2, null_p=0.06, empty_p=0.08)
    long_trip_types = weighted_map(TRIP_TYPES, 1, 2, null_p=0.05, empty_p=0.06)
    long_budget_levels = weighted_map(BUDGET_LEVELS, 1, 2, null_p=0.06, empty_p=0.05)
    session_trip_types = weighted_map(TRIP_TYPES, 1, 2, null_p=0.05, empty_p=0.08)
    session_budget_levels = weighted_map(BUDGET_LEVELS, 1, 2, null_p=0.08, empty_p=0.08)

    check_in, check_out = make_date_pair()
    guests = guests_for_trip(session_trip_types)
    top_session_trip = max(session_trip_types, key=session_trip_types.get) if session_trip_types else None

    profile = {
        "user_id": f"user_{index:03d}",
        "name": maybe_null(name, 0.04),
        "long_term_profile": {
            "nationality": maybe_null(nationality, 0.05),
            "age_group": age_group,
            "current_workplace": random.choice(CURRENT_LOCATIONS),
            "traveler_type": traveler_type,
            "long_term_trip_types": long_trip_types,
            "long_term_budget_levels": long_budget_levels,
            "long_term_price_range": price_range(long_budget_levels),
            "long_term_preference_tags": weighted_map(LONG_TERM_PREFERENCE_TAGS, 1, 3),
            "long_term_hotel_types": weighted_map(HOTEL_TYPES, 1, 4),
            "long_term_amenities": weighted_map(AMENITIES, 1, 5),
            "recommendation_clicks": make_recommendation_clicks(),
            "long_term_negative_preferences": make_negative_preferences(),
        },
        "session_context": {
            "destination": random.choice(DESTINATIONS),
            "current_location": random.choice(CURRENT_LOCATIONS),
            "nearby_place": random.choice(NEARBY_PLACES),
            "number_of_guests": guests,
            "has_pet": True if random.random() < 0.12 else random.choice([False, False, None]),
            "has_children": True if top_session_trip == "family" and random.random() < 0.7 else random.choice([False, False, None]),
            "check_in": check_in,
            "check_out": check_out,
            "session_trip_types": session_trip_types,
            "session_budget_levels": session_budget_levels,
            "session_price_range": price_range(session_budget_levels),
            "session_preference_tags": weighted_map(SESSION_PREFERENCE_TAGS, 1, 4),
            "session_hotel_types": weighted_map(HOTEL_TYPES, 1, 3),
            "session_amenities": weighted_map(SESSION_AMENITIES, 1, 5),
            "session_negative_preferences": make_negative_preferences(),
        },
    }

    maybe_omit(profile["long_term_profile"], ["current_workplace", "long_term_amenities"], 0.05)
    maybe_omit(profile["session_context"], ["nearby_place", "check_out", "session_hotel_types"], 0.06)
    return profile


def apply_demo_overrides(profiles):
    if len(profiles) < 15:
        return

    profiles[0] = {
        "user_id": "user_001",
        "name": "Minh Anh Nguyen",
        "long_term_profile": {
            "nationality": "vietnamese",
            "age_group": "under_25",
            "current_workplace": "Ho Chi Minh City",
            "traveler_type": {"explorer": 0.92},
            "long_term_trip_types": {"tourist": 0.95},
            "long_term_budget_levels": {"low": 0.9},
            "long_term_price_range": {"min": 500000, "max": 1800000, "currency": "VND"},
            "long_term_preference_tags": {"unique": 0.9, "lively": 0.7, "safe": 0.55},
            "long_term_hotel_types": {"homestay": 0.86, "hostel": 0.72, "guesthouse": 0.6},
            "long_term_amenities": {"wifi": 0.9, "breakfast": 0.5},
            "recommendation_clicks": {
                "hotel": {
                    "hotel_0007": {
                        "click_count": 8,
                        "last_clicked_at": "2026-05-22T20:15:00",
                    },
                    "hotel_0021": {
                        "click_count": 3,
                        "last_clicked_at": "2026-05-28T21:30:00",
                    },
                },
            },
            "long_term_negative_preferences": {
                "avoid_hotel_types": {"luxury_hotel": -0.4},
                "avoid_amenities": {},
                "avoid_tags": {"low_rating": -0.95, "unsafe_area": -0.9},
                "avoid_nearby_places": {},
                "avoid_locations": {"crowded_center": -0.45},
            },
        },
        "session_context": {
            "destination": "Da Nang",
            "current_location": "Ho Chi Minh City",
            "nearby_place": "My Khe Beach",
            "number_of_guests": 2,
            "has_pet": False,
            "has_children": False,
            "check_in": None,
            "check_out": None,
            "session_trip_types": {"tourist": 0.9},
            "session_budget_levels": {"low": 0.85},
            "session_price_range": {"min": 500000, "max": 1500000, "currency": "VND"},
            "session_preference_tags": {"unique": 0.8, "near_beach": 0.92, "lively": 0.6},
            "session_hotel_types": {"homestay": 0.82, "budget_hotel": 0.7},
            "session_amenities": {"wifi": 0.95},
            "session_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_tags": {"low_rating": -0.9},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
        },
    }

    profiles[4]["long_term_profile"].update(
        {
            "traveler_type": {"comfort_seeker": 0.88, "planner": 0.55},
            "long_term_trip_types": {"business": 0.9},
            "long_term_budget_levels": {"high": 0.9},
            "long_term_hotel_types": {"premium_hotel": 0.9, "luxury_hotel": 0.76, "resort": 0.45},
            "long_term_amenities": {"wifi": 0.95, "spa": 0.65, "breakfast": 0.7, "soundproof": 0.88},
            "recommendation_clicks": {
                "hotel": {
                    "hotel_0090": {
                        "click_count": 12,
                        "last_clicked_at": "2026-06-01T09:45:00",
                    }
                },
            },
        }
    )
    profiles[4]["session_context"].update(
        {
            "session_trip_types": {"business": 0.92},
            "destination": "Ho Chi Minh City",
            "nearby_place": "City Center",
            "number_of_guests": 1,
            "session_amenities": {"wifi": 0.95, "shuttle_service": 0.8, "soundproof": 0.85},
            "session_negative_preferences": {
                "avoid_hotel_types": {"hostel": -0.9, "guesthouse": -0.6},
                "avoid_amenities": {"bar": -0.5},
                "avoid_tags": {"noisy": -0.95, "old_facility": -0.8, "low_rating": -0.9},
                "avoid_nearby_places": {"Night Market": -0.45},
                "avoid_locations": {"crowded_center": -0.65},
            },
        }
    )

    profiles[14]["session_context"].update(
        {
            "session_trip_types": {"family": 0.96},
            "destination": "Phu Quoc",
            "nearby_place": "VinWonders",
            "number_of_guests": 4,
            "has_children": True,
            "has_pet": False,
            "session_budget_levels": {"medium": 0.82},
            "session_price_range": {"min": 2000000, "max": 5000000, "currency": "VND"},
            "session_preference_tags": {"comfort": 0.8, "safe": 0.9, "near_attraction": 0.9},
            "session_hotel_types": {"resort": 0.86, "hotel": 0.5},
            "session_amenities": {"pool": 0.75, "kids_club": 0.95, "breakfast": 0.65},
        }
    )


def generate_profiles(user_count=USER_COUNT):
    profiles = []
    for index in range(1, user_count + 1):
        if index <= user_count // 2:
            name = VIETNAMESE_NAMES[(index - 1) % len(VIETNAMESE_NAMES)]
            nationality = "vietnamese"
        else:
            name = FOREIGN_NAMES[(index - 1 - user_count // 2) % len(FOREIGN_NAMES)]
            nationality = "foreign"
        profiles.append(make_user(index, name, nationality))

    apply_demo_overrides(profiles)
    return profiles


def validate_ascii_only(path):
    raw = Path(path).read_text(encoding="utf-8")
    non_ascii = sorted(set(ch for ch in raw if ord(ch) > 127))
    if non_ascii:
        raise ValueError(f"Generated file contains non-ASCII characters: {non_ascii[:10]}")


def main():
    profiles = generate_profiles(USER_COUNT)
    output = {
        "schema_version": "weighted_user_profile_mock",
        "language": "en",
        "count": len(profiles),
        "users": profiles,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    validate_ascii_only(OUTPUT_FILE)

    print(f"Created {OUTPUT_FILE.resolve()}")
    print(f"Users: {len(profiles)}")
    print("Language: English only")
    print("ASCII validation: passed")


if __name__ == "__main__":
    main()
