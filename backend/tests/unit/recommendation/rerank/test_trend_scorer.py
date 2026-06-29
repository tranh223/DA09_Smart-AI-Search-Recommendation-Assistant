from datetime import datetime, timezone

from app.recommendation.rerank.booking_signals import compute_booking_signals
from app.recommendation.rerank.trend_scorer import apply_trend_scores


NOW = datetime(2026, 6, 9, tzinfo=timezone.utc)


def test_no_bookings_trend_zero():
    signals = apply_trend_scores(compute_booking_signals([], [{"item_id": "1"}], "u1", NOW))
    assert signals["1"]["trend_score"] == 0.0


def test_counts_windows_and_confirmed_only():
    bookings = [
        {"user_id": "x", "hotel_id": "1", "booking_date": "2026-06-08T00:00:00Z", "status": "confirmed"},
        {"user_id": "x", "hotel_id": "1", "booking_date": "2026-05-20T00:00:00Z", "status": "confirmed"},
        {"user_id": "x", "hotel_id": "1", "booking_date": "2026-06-07T00:00:00Z", "status": "cancelled"},
    ]
    signals = apply_trend_scores(compute_booking_signals(bookings, [{"item_id": "1"}], "u1", NOW))
    assert signals["1"]["booking_count_7d"] == 1
    assert signals["1"]["booking_count_30d"] == 2
    assert signals["1"]["trend_score"] > 0


def test_user_history_and_same_destination():
    bookings = [
        {"user_id": "u1", "hotel_id": "9", "booking_date": "2026-05-20T00:00:00Z", "destination": "Vung Tau", "status": "confirmed"}
    ]
    signals = compute_booking_signals(bookings, [{"item_id": "1", "destination": "Vung Tau"}], "u1", NOW)
    assert signals["1"]["same_destination_booking_count"] == 1


def test_booked_at_without_status_counts_as_history():
    bookings = [{"user_id": "x", "hotel_id": "1", "booked_at": "2026-06-08T00:00:00Z"}]
    signals = compute_booking_signals(bookings, [{"item_id": "1"}], "u1", NOW)
    assert signals["1"]["booking_count_7d"] == 1
    assert signals["1"]["booking_count_30d"] == 1
