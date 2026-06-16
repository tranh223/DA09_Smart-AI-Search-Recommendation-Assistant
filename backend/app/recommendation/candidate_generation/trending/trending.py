"""
TOP TRENDING — aggregate Booking theo destination (field `destination`), không dùng Neo4j.
"""

from __future__ import annotations
import logging
import re

from app.db.mongo.mongo_client import get_collection
from app.recommendation.models import CandidateHotel
from app.recommendation.trace import RecommendTrace

logger = logging.getLogger(__name__)

TRENDING_COLLECTION = "Booking"


def _rows_to_candidates(rows: list[dict], destination: str) -> list[CandidateHotel]:
    candidates = []
    for i, row in enumerate(rows, start=1):
        hotel_id = row.get("hotel_id") or row.get("_id")
        if hotel_id is None:
            continue
        booking_count = int(row.get("booking_count") or 0)
        candidates.append(
            CandidateHotel(
                hotel_id=int(hotel_id),
                hotel_name=row.get("hotel_name"),
                source="trending",
                score=float(booking_count),
                matched_paths=[],
                reason=f"Top trending tại {destination}: {booking_count} lượt đặt",
                metadata={
                    "destination": destination,
                    "rank": i,
                    "booking_count": booking_count,
                    "strategy": "mongo_booking_aggregate",
                },
            )
        )
    return candidates


def get_trending_candidates(
    destination: str,
    limit: int = 10,
    trace: RecommendTrace | None = None,
) -> list[CandidateHotel]:
    if not destination or not destination.strip():
        if trace and trace.enabled:
            trace.info("Thiếu destination → bỏ qua trending")
        logger.info("[Trending] Không có destination → bỏ qua.")
        return []

    destination = destination.strip()

    city_regex = {"$regex": re.escape(destination), "$options": "i"}
    match_stage = {
        "$or": [
            {"destination": city_regex},
            {"city": city_regex},
        ]
    }

    if trace and trace.enabled:
        trace.step(
            "MongoDB aggregate",
            {
                "collection": TRENDING_COLLECTION,
                "match_fields": ["destination", "city"],
                "match_value": destination,
                "limit": limit,
            },
        )

    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": "$hotel_id",
                "hotel_name": {"$first": "$hotel_name"},
                "booking_count": {"$sum": 1},
            }
        },
        {"$sort": {"booking_count": -1}},
        {"$limit": limit},
    ]

    try:
        collection = get_collection(TRENDING_COLLECTION)
        rows = [
            {
                "hotel_id": r["_id"],
                "hotel_name": r.get("hotel_name"),
                "booking_count": r.get("booking_count", 0),
            }
            for r in collection.aggregate(pipeline)
        ]
        if trace and trace.enabled:
            trace.info(f"Match {len(rows)} hotel(s) có booking tại {destination}")
    except Exception as exc:
        if trace and trace.enabled:
            trace.info(f"Lỗi MongoDB: {exc}")
        logger.warning("[Trending][MongoDB] Aggregate lỗi: %s", exc)
        return []

    candidates = _rows_to_candidates(rows, destination)
    logger.info("[Trending] %d candidates tại %s.", len(candidates), destination)
    return candidates
