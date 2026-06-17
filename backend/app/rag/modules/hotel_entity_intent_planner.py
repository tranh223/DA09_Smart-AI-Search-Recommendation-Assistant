"""hotel_entity_intent_planner

Lớp intent phụ trợ: xác định các thực thể được nhắc tới trong query.

Chuẩn hoá theo catalog tạo từ:
  data/hotel_sql_local_export.csv

Output dạng dict JSON (thuận tiện tích hợp vào planner/skill routing):
{
  "entities": [{"hotel_id": int, "hotel_name": str, "matched_text": str, "confidence": float}, ...],
  "hotel_ids": [int, ...]
}

Nếu không match được: entities = []

"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from pathlib import Path

from utils.langsmith_tracer import tracer
from utils.logger import get_logger

from modules.hotel_entity_intent_helper import (
    HotelEntity,
    extract_hotel_entities,
    extract_hotel_ids,
    DEFAULT_EXPORT_CSV,
)

logger = get_logger(__name__)


def _coerce_export_csv_path() -> Path:
    # Optional override
    p = os.getenv("HOTEL_SQL_LOCAL_EXPORT_CSV")
    if p:
        return Path(p)
    return DEFAULT_EXPORT_CSV


@tracer.trace("hotel_entity_intent_planner_extract")
def extract_entities_from_query(query: str) -> Dict[str, Any]:
    export_csv = _coerce_export_csv_path()

    try:
        entities: List[HotelEntity] = extract_hotel_entities(
            query, export_csv_path=export_csv, max_entities=10
        )
        ids = [e.hotel_id for e in entities]

        return {
            "entities": [
                {
                    "hotel_id": e.hotel_id,
                    "hotel_name": e.hotel_name,
                    "matched_text": e.matched_text,
                    "confidence": e.confidence,
                }
                for e in entities
            ],
            "hotel_ids": ids,
        }
    except Exception as e:
        logger.error(f"Failed to extract hotel entities: {e}")
        return {"entities": [], "hotel_ids": []}

