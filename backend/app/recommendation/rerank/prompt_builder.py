from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You are an OTA hotel reranking assistant.
Only use the provided data.
Do not invent hotel facts.
Respect hard constraints.
Return strict JSON only.
Rerank the provided hotel IDs.
Do not include hotel IDs that are not in the candidate list.
Vietnamese labels such as hotel_type, amenities, room_views, trip_types must be preserved."""


def build_llm_messages(query: str | None, profile: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload = {
        "query": query,
        "normalized_profile": profile,
        "candidates": [
            {
                "item_id": item["item_id"],
                "name": item.get("name"),
                "destination": item.get("destination"),
                "hotel_type": item.get("hotel_type"),
                "price_min": item.get("price_min"),
                "price_max": item.get("price_max"),
                "amenities": item.get("amenities"),
                "room_views": item.get("room_views"),
                "preference_habits": item.get("preference_habits"),
                "tags": item.get("tags"),
                "location_tags": item.get("location_tags"),
                "nearby_places": item.get("nearby_places"),
                "base_score": item.get("base_score"),
                "feature_scores": item.get("feature_scores"),
            }
            for item in candidates
        ],
        "required_output_shape": {
            "ranked_items": [
                {
                    "item_id": "string",
                    "llm_score": "number 0..1",
                    "rank": "integer",
                    "reasons": ["string"],
                    "warnings": ["string"],
                }
            ]
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

