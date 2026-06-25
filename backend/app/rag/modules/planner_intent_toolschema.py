"""Normalize planner tool inputs for the RAG pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _uniq_ints(xs: List[Any]) -> List[int]:
    out: List[int] = []
    seen = set()
    for x in xs:
        try:
            i = int(x)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def build_tool_inputs_from_context(
    query: str,
    plan_result: Dict[str, Any],
    aux_intents: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standardized tool inputs payload.

    Output schema (best-effort):
    {
      "entities": {"hotels": [{hotel_id, hotel_name, confidence, matched_text}, ...]},
      "tools": {
        "rag": {"query": query, "top_k": 3, "hotel_ids": [...], "sections": [...]},
        "graph": {"query": query, "top_k": 3}
      }
    }
    """

    aux_intents = aux_intents or {}
    hotel_entities = (aux_intents.get("hotel_entity_intent") or {}).get("entities") or []

    hotel_ids = _uniq_ints([e.get("hotel_id") for e in hotel_entities if isinstance(e, dict)])

    rag_top_k = plan_result.get("rag_top_k", 3)
    graph_top_k = plan_result.get("graph_top_k", 3)

    sections = plan_result.get("rag_sections", [])
    if not isinstance(sections, list):
        sections = []

    return {
        "entities": {
            "hotels": hotel_entities,
            "hotel_ids": hotel_ids,
        },
        "tools": {
            "rag": {
                "query": query,
                "top_k": int(rag_top_k) if rag_top_k is not None else 3,
                "hotel_ids": hotel_ids,
                "sections": sections,
            },
            "graph": {
                "query": query,
                "top_k": int(graph_top_k) if graph_top_k is not None else 3,
            },
        },
    }

