"""planner_intents_aux

Tập hợp các intent/tiền xử lý phụ trợ cho pipeline planner.

Hiện tại bao gồm:
- hotel_entity_intent_planner: extract entity hotels from query and normalize by catalog.

"""

from __future__ import annotations

from typing import Any, Dict

from modules.hotel_entity_intent_planner import extract_entities_from_query


def parse_aux_intents(query: str) -> Dict[str, Any]:
    """Parse non-LLM auxiliary intents.

    Returns a dict merged into planner/skill routing context.
    """

    hotel_entities = extract_entities_from_query(query)

    return {
        "hotel_entity_intent": hotel_entities,
    }

