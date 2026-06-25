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
    if _looks_like_hotel_detail_query(query, plan_result):
        hotel_ids = hotel_ids[:1]

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


def _looks_like_hotel_detail_query(query: str, plan_result: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(query or ""),
            str(plan_result.get("query_type") or ""),
            str(plan_result.get("main_object") or ""),
            str(plan_result.get("sub_objects") or ""),
            str(plan_result.get("required_steps") or ""),
            str(plan_result.get("context") or ""),
        ]
    ).casefold()
    normalized = (
        text.replace("đ", "d")
        .replace("ô", "o")
        .replace("ơ", "o")
        .replace("ó", "o")
        .replace("ò", "o")
        .replace("ỏ", "o")
        .replace("õ", "o")
        .replace("ọ", "o")
        .replace("â", "a")
        .replace("ă", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("ả", "a")
        .replace("ã", "a")
        .replace("ạ", "a")
        .replace("ê", "e")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ẻ", "e")
        .replace("ẽ", "e")
        .replace("ẹ", "e")
        .replace("ư", "u")
        .replace("ú", "u")
        .replace("ù", "u")
        .replace("ủ", "u")
        .replace("ũ", "u")
        .replace("ụ", "u")
        .replace("í", "i")
        .replace("ì", "i")
        .replace("ỉ", "i")
        .replace("ĩ", "i")
        .replace("ị", "i")
        .replace("ý", "y")
        .replace("ỳ", "y")
        .replace("ỷ", "y")
        .replace("ỹ", "y")
        .replace("ỵ", "y")
    )
    return any(
        marker in normalized
        for marker in (
            "thong tin chi tiet",
            "xem thong tin",
            "mo ta",
            "gioi thieu",
            "hotel_feature_qa",
            "hotel_policy_qa",
            "information",
        )
    )

