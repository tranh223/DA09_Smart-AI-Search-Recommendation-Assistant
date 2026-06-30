from __future__ import annotations

from typing import Any


def build_reasons(item: dict[str, Any], profile: dict[str, Any], llm_reasons: list[str] | None = None) -> list[str]:
    reasons: list[str] = []
    session = profile.get("session", {})
    features = item.get("feature_scores", {})
    if session.get("destination") and item.get("destination") == session.get("destination"):
        reasons.append(f"Phù hợp chuyến đi gia đình tại {item.get('destination')}")
    if features.get("suitability", 0) >= 0.70:
        session_trip_types = set(session.get("trip_types", {}).keys())
        hotel_tags = set(item.get("tags", []))
        matching_types = session_trip_types.intersection(hotel_tags)
        if matching_types:
            reasons.append(f"Rất phù hợp cho {', '.join(matching_types)}")
        else:
            reasons.append("Phù hợp với loại hình chuyến đi của bạn")
    if features.get("personalization", 0) >= 0.75 and item.get("hotel_type"):
        reasons.append(f"Khớp loại {item.get('hotel_type')} mà session đang ưu tiên")
    matching_views = [view for view in item.get("room_views", []) if view in session.get("room_views", {})]
    if matching_views:
        reasons.append("Có " + " và ".join(matching_views))
    price_range = session.get("price_range") or {}
    if features.get("budget", 0) >= 0.70 and price_range.get("min") and price_range.get("max"):
        reasons.append(
            f"Giá nằm trong khoảng {int(price_range['min']):,} - {int(price_range['max']):,} {price_range.get('currency', 'VND')}".replace(",", ".")
        )
    if features.get("trend", 0) >= 0.65:
        reasons.append("Khách sạn đang có xu hướng được đặt nhiều gần đây")
    if llm_reasons:
        reasons.extend(llm_reasons[:2])
    return reasons or ["Có độ phù hợp tổng thể ổn với nhu cầu hiện tại"]


def build_warnings(item: dict[str, Any], llm_warnings: list[str] | None = None) -> list[str]:
    warnings = list(llm_warnings or [])
    if item.get("negative_penalty", 0) >= 0.2:
        warnings.append("Có một số tín hiệu không ưu tiên trong hồ sơ người dùng")
    return warnings

