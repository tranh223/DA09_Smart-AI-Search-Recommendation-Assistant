from __future__ import annotations

from typing import Any

from .config import Settings, postgres_debug_info


try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - depends on optional local Postgres setup.
    psycopg = None
    dict_row = None

try:
    import psycopg2
    import psycopg2.extras
except ModuleNotFoundError:  # pragma: no cover - depends on optional local Postgres setup.
    psycopg2 = None


def postgres_driver_debug_info() -> dict[str, Any]:
    return {
        "psycopg3_available": psycopg is not None,
        "psycopg2_available": psycopg2 is not None,
    }


HOTEL_SELECT = """
SELECT
  h.id,
  h.name,
  h.accommodation_type,
  h.star_rating,
  h.is_luxury,
  h.review_score,
  h.review_count,
  h.address,
  h.city,
  h.latitude,
  h.longitude,
  h.description,
  h.amenities,
  h.useful_info,
  h.policyNotes,
  h.suitable_for,
  h.images,
  h.source_url,
  MIN(r.price) AS min_price,
  MAX(r.price) AS max_price,
  COUNT(DISTINCT r.id) AS room_count,
  MAX(r.max_occupancy) AS max_occupancy,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.room_view), NULL) AS room_views,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT ra.room_amenity), NULL) AS room_amenities,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT p.name), NULL) AS nearby_place_names,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT p.type), NULL) AS nearby_place_types,
  MIN(p.distance_km) AS nearest_place_distance_km,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT a.title), NULL) AS activity_titles,
  MIN(a.price_amount) AS min_activity_price,
  MAX(a.review_score) AS best_activity_review_score
FROM hotels h
LEFT JOIN rooms r ON r.hotel_id = h.id
LEFT JOIN LATERAL UNNEST(r.room_amenities) AS ra(room_amenity) ON TRUE
LEFT JOIN nearby_places p ON p.hotel_id = h.id
LEFT JOIN activities a ON a.hotel_id = h.id
{where_clause}
GROUP BY h.id
"""


HOTEL_BY_IDS_SQL = HOTEL_SELECT.format(
    where_clause="WHERE h.id = ANY(%(hotel_ids)s)"
) + """
ORDER BY array_position(%(hotel_ids)s, h.id);
"""


class PostgresCandidateStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.postgres_dsn:
            raise RuntimeError("missing_postgres_dsn")
        if psycopg is None and psycopg2 is None:
            raise RuntimeError("missing_postgres_driver")
        self.settings = settings
        self.debug_info = postgres_debug_info(settings.postgres_dsn)

    def get_hotels_by_ids(self, hotel_ids: list[str]) -> list[dict[str, Any]]:
        numeric_ids = []
        for item in hotel_ids:
            try:
                numeric_ids.append(int(item))
            except (TypeError, ValueError):
                continue
        if not numeric_ids:
            return []
        return self._fetch(HOTEL_BY_IDS_SQL, {"hotel_ids": numeric_ids})

    def enrich_candidates(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        candidate_ids = [str(item.get("item_id") or item.get("hotel_id") or item.get("id") or "") for item in candidates]
        rows = self.get_hotels_by_ids(candidate_ids)
        rows_by_id = {str(row.get("id")): row for row in rows}
        enriched: list[dict[str, Any]] = []
        enriched_ids: list[str] = []
        missing_ids: list[str] = []
        for candidate in candidates:
            item_id = str(candidate.get("item_id") or candidate.get("hotel_id") or candidate.get("id") or "")
            row = rows_by_id.get(item_id)
            if row:
                merged = {**candidate, **row, "item_id": item_id}
                enriched.append(merged)
                enriched_ids.append(item_id)
            else:
                enriched.append(candidate)
                if item_id:
                    missing_ids.append(item_id)
        debug = {
            "postgres": self.debug_info,
            "requested_ids": [item_id for item_id in candidate_ids if item_id],
            "enriched_ids": enriched_ids,
            "missing_ids": missing_ids,
        }
        return enriched, debug

    def _fetch(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if psycopg is not None:
            with psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return [self._normalize_row(dict(row)) for row in cursor.fetchall()]

        with psycopg2.connect(self.settings.postgres_dsn) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(sql, params)
                return [self._normalize_row(dict(row)) for row in cursor.fetchall()]

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        row["item_id"] = str(row.get("id") or "")
        row["room_amenities"] = _flatten(row.get("room_amenities", []))
        row["nearby_places"] = row.pop("nearby_place_names", []) or []
        row["tags"] = _dedupe(
            row.get("suitable_for") or [],
            row.get("policyNotes") or [],
            row.get("nearby_place_types") or [],
            row.get("activity_titles") or [],
        )
        row["available"] = bool(row.get("room_count"))
        row["available_rooms"] = int(row.get("room_count") or 0)
        return row


def _flatten(values: Any) -> list[str]:
    result: list[str] = []
    for value in values or []:
        if isinstance(value, list):
            result.extend(str(item) for item in value if item is not None)
        elif value is not None:
            result.append(str(value))
    return _dedupe(result)


def _dedupe(*groups: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        values = group if isinstance(group, list) else [group]
        for value in values:
            if value is None:
                continue
            text = str(value)
            if text not in seen:
                seen.add(text)
                result.append(text)
    return result
