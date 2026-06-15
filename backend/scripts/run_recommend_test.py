"""Chạy thử recommend pipeline — bật trace in chi tiết từng bước."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.recommendation.models import RecommendInput
from app.recommendation.engine import run_candidate_pipeline

INTENT_OUTPUT = {
  "turn": 3,
  "user_id": "user_001",
  "profile": {
    "nationality": "vietnamese",
    "age_group": "under_25",
    "current_workplace": "Ho Chi Minh City",
    "is_enough": True,
    "traveler_type": {},
    "long_term_trip_types": {
      "Gia đình có trẻ con": {
        "count": 1,
        "last_interaction": "2026-06-12"
      }
    },
    "long_term_budget_levels": {
      "low": {
        "count": 1,
        "last_interaction": "2026-06-12"
      }
    },
    "long_term_preference_habits": {
      "có khu vực hút thuốc": {
        "count": 2,
        "last_interaction": "2026-06-12"
      },
    },
    "long_term_hotel_types": {},
    "long_term_room_views": {
      "gần bệnh viện": {
        "count": 2,
        "last_interaction": "2026-06-12"
      },
      "cách âm": {
        "count": 2,
        "last_interaction": "2026-06-12"
      }
    },
    "recommendation_clicks": {
      "hotel": []
    },
    "long_term_negative_preferences": {
      "avoid_hotel_types": {},
      "avoid_amenities": {},
      "avoid_preference_habits": {},
      "avoid_nearby_places": {},
      "avoid_locations": {}
    }
  },
    "session_context": {
        "destination": "Đà Lạt",
        "current_location": None,
        "nearby_place": "trung tâm",
        "number_of_guests": None,
        "has_pet": None,
        "has_children": None,
        "check_in": "2026-06-20",
        "check_out": "2026-06-21",
        "session_price_range": {"min": None, "max": None, "currency": "VND"},
    },
}


def main():
    inp = RecommendInput(
        user_id=INTENT_OUTPUT["user_id"],
        profile=INTENT_OUTPUT["profile"],
        session_context=INTENT_OUTPUT["session_context"],
        original_query="tìm khách sạn gia đình Đà Lạt",
        limit_per_source=10,
    )

    # trace=True → in chi tiết từng bước: intent → orchestrator → từng nguồn → merge
    merged = run_candidate_pipeline(inp, trace=True)

    if not merged:
        print("\n(Không có kết quả sau merge)")


if __name__ == "__main__":
    main()
