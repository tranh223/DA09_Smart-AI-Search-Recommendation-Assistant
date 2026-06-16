from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .utils import parse_datetime, to_str_id, utc_now


def compute_booking_signals(
    bookings: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    user_id: str | None,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    current = now or utc_now()
    candidate_ids = {to_str_id(item.get("item_id")) for item in candidates}
    destinations = {to_str_id(item.get("item_id")): item.get("destination") for item in candidates}
    signals = {
        item_id: {
            "booking_count_7d": 0,
            "booking_count_30d": 0,
            "booking_growth_7d_vs_30d": 0.0,
            "user_booked_before": False,
            "same_destination_booking_count": 0,
            "trend_score": 0.0,
        }
        for item_id in candidate_ids
    }
    destination_user_counts: dict[str, int] = defaultdict(int)

    for booking in bookings:
        hotel_id = to_str_id(booking.get("hotel_id") or booking.get("item_id"))
        booking_user = booking.get("user_id")
        status = str(booking.get("status") or "confirmed").lower()
        booking_dt = parse_datetime(booking.get("booked_at") or booking.get("booking_date"))

        if user_id and booking_user == user_id:
            destination_user_counts[str(booking.get("city") or booking.get("destination"))] += 1
            if hotel_id in signals:
                signals[hotel_id]["user_booked_before"] = True

        if hotel_id not in candidate_ids or status != "confirmed" or booking_dt is None:
            continue

        age_days = (current - booking_dt).total_seconds() / 86400
        if 0 <= age_days <= 30:
            signals[hotel_id]["booking_count_30d"] += 1
            if age_days <= 7:
                signals[hotel_id]["booking_count_7d"] += 1

    for item_id, signal in signals.items():
        older_30 = max(signal["booking_count_30d"] - signal["booking_count_7d"], 0)
        signal["booking_growth_7d_vs_30d"] = (
            float(signal["booking_count_7d"]) if older_30 == 0 else signal["booking_count_7d"] / older_30
        )
        signal["same_destination_booking_count"] = destination_user_counts.get(str(destinations.get(item_id)), 0)

    return signals
