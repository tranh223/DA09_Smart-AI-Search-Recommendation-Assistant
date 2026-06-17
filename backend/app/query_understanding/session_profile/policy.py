from __future__ import annotations

AMENITY_LIKE_REVIEW_TAGS = frozenset({"Dịch vụ"})

GRAPH_EXPANSION_SEED_CATEGORIES = frozenset(
    {
        "HOTEL_AMENITY",
        "ROOM_AMENITY",
        "ROOM_VIEW",
        "REVIEW_TAG",
        "SUITABLE_FOR",
        "HOTEL_TYPE",
        "PLACE_TYPE",
    }
)

BUDGET_LEVELS = frozenset({"low", "medium", "high"})
