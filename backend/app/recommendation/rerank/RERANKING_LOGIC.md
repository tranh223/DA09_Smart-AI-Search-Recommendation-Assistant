# Reranking Logic

Profile groups use:

```text
normalized_weight = count / max_count_in_same_group
```

Trend score:

```text
trend_score =
  0.60 * normalized_booking_count_7d
+ 0.30 * normalized_booking_growth
+ 0.10 * normalized_booking_count_30d
```

Base score:

```text
base_score =
  0.12 * keyword_score
+ 0.10 * budget_score
+ 0.14 * amenity_score
+ 0.10 * room_view_score
+ 0.10 * review_score
+ 0.13 * availability_score
+ 0.12 * personalization_score
+ 0.09 * location_score
+ 0.10 * trend_score
- negative_penalty
```

Hard filters remove destination mismatch, unavailable hotels, strong negative matches, and prices far outside the session price range.

