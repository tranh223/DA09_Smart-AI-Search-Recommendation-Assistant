"""planner_intents_aux

Tập hợp các intent/tiền xử lý phụ trợ cho pipeline planner.

Hiện tại bao gồm:
- hotel_entity_intent_planner: extract entity hotels from query and normalize by catalog.

"""

from __future__ import annotations

from typing import Any, Dict

from modules.hotel_entity_intent_helper import extract_hotel_entities


def parse_aux_intents(query: str) -> Dict[str, Any]:
    """Parse non-LLM auxiliary intents.

    Returns a dict merged into planner/skill routing context.
    """

    hotel_entities = extract_hotel_entities(query)

    return {
        "hotel_entity_intent": {
            "entities": [
                {
                    "hotel_id": entity.hotel_id,
                    "hotel_name": entity.hotel_name,
                    "matched_text": entity.matched_text,
                    "confidence": entity.confidence,
                }
                for entity in hotel_entities
            ]
        },
    }

