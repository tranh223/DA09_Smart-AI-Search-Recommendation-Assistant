"""Skill agent for intent routing.

This module provides 3-intent classification:
- INFORMATION
- HOTEL_SIMILAR
- SPECIAL_FEATURE

It is used to decide which retrieval paths to call.
"""

from __future__ import annotations

import time

from typing import Any, Dict, Literal

from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from utils.llm_client import llm_client

logger = get_logger(__name__)

# Keep as a type alias for readability.
IntentType = Literal["INFORMATION", "HOTEL_SIMILAR", "SPECIAL_FEATURE"]


SKILL_AGENT_SYSTEM_PROMPT = """You are a routing skill agent for a hotel RAG system.

Given a user query, classify intent into exactly one of:
1) INFORMATION: asking for general hotel/hospitality information (amenities, location, things to do, descriptions)
2) HOTEL_SIMILAR: asking to find hotels similar to a named hotel OR compare options (best alternative, similar stay)
3) SPECIAL_FEATURE: asking about a specific feature/constraint like family with kids, pet policy, check-in/check-out policy, activities included/excluded, or any special rule

Return STRICT JSON with this schema:
{
  "intent_type": "INFORMATION" | "HOTEL_SIMILAR" | "SPECIAL_FEATURE",
  "source": "SKILL_AGENT",
  "parameters": {
    "query": string,
    "features": {
      "hotel_name": string | null,
      "destination": string | null,
      "amenities": string[],
      "expectations": string[]
    }
  }
}

If you cannot determine hotel_name, set it to null.
"""


@tracer.trace("skill_agent_route")
def route_intent(query: str) -> Dict[str, Any]:
    start = time.perf_counter()

    messages = [
        {
            "role": "user",
            "content": f"Query: {query}\n\nClassify intent and extract features as JSON.",
        }
    ]

    result = llm_client.call_with_structured_output(
        messages,
        system_prompt=SKILL_AGENT_SYSTEM_PROMPT,
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if isinstance(result, dict):
        result.setdefault("parameters", {})
        result["parameters"].setdefault("query", query)
        result.setdefault("metadata", {})
        result["metadata"].update({"routing_time_ms": elapsed_ms})

    return result

