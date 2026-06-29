from __future__ import annotations

from typing import Any

from .utils import clamp


def apply_trend_scores(signals: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    max_7d = max((float(s.get("booking_count_7d", 0) or 0) for s in signals.values()), default=0.0)
    max_30d = max((float(s.get("booking_count_30d", 0) or 0) for s in signals.values()), default=0.0)
    max_growth = max((float(s.get("booking_growth_7d_vs_30d", 0) or 0) for s in signals.values()), default=0.0)

    for signal in signals.values():
        n7 = 0.0 if max_7d <= 0 else float(signal.get("booking_count_7d", 0) or 0) / max_7d
        n30 = 0.0 if max_30d <= 0 else float(signal.get("booking_count_30d", 0) or 0) / max_30d
        ng = 0.0 if max_growth <= 0 else float(signal.get("booking_growth_7d_vs_30d", 0) or 0) / max_growth
        signal["trend_score"] = round(clamp(0.60 * n7 + 0.30 * ng + 0.10 * n30), 3)
    return signals

