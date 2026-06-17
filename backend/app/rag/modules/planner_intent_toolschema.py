"""planner_intent_toolschema

Một tiện ích để chuẩn hoá "tool inputs" trong context output của planner.

Yêu cầu từ task: planner schema cần chứa:
- list các entities cần phân tích
- input đầu vào của các tool (RAG/Graph/Hotel SQL)

Hiện tại pipeline đã có:
- modules/planner.py: LLM planner (needs_rag/needs_graph/needs_hotel_sql...)
- modules/planner_intents_aux.py + hotel_entity_intent_planner: extract hotel entities

Module này cung cấp hàm:
  build_tool_inputs_from_context(query, plan_result, aux_intents)

trả về dict chuẩn hóa có thể được gắn vào plan_result['tool_inputs']
"""

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
        "rag": {"query": query, "top_k": 3},
        "graph": {"query": query, "top_k": 3},
        "hotel_sql": {"query": query, "need": ["detail","policies","activities"], "hotel_ids": [...]} 
      }
    }
    """

    aux_intents = aux_intents or {}
    hotel_entities = (aux_intents.get("hotel_entity_intent") or {}).get("entities") or []

    hotel_ids = _uniq_ints([e.get("hotel_id") for e in hotel_entities if isinstance(e, dict)])

    # tool top_k: lấy từ planner if provided, otherwise default
    # (hiện pipeline retrieval.py hardcodes top_k=3; đây là context để sau này nâng cấp)
    rag_top_k = plan_result.get("rag_top_k", 3)
    graph_top_k = plan_result.get("graph_top_k", 3)

    # hotel_sql need: keep same default
    need = plan_result.get("hotel_sql_need", ["detail", "policies", "activities"])
    if not isinstance(need, list) or not need:
        need = ["detail", "policies", "activities"]

    return {
        "entities": {
            "hotels": hotel_entities,
            "hotel_ids": hotel_ids,
        },
        "tools": {
            "rag": {
                "query": query,
                "top_k": int(rag_top_k) if rag_top_k is not None else 3,
            },
            "graph": {
                "query": query,
                "top_k": int(graph_top_k) if graph_top_k is not None else 3,
            },
            "hotel_sql": {
                "query": query,
                "need": need,
                "hotel_ids": hotel_ids,
            },
        },
    }

