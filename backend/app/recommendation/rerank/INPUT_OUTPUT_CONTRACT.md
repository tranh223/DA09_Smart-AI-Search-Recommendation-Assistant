# Input/Output Contract

## Function

```python
def rerank(
    user_id: str | None,
    user_context: dict | None,
    candidate_items: list[dict],
    query: str | None,
    options: dict | None
) -> dict:
```

`Users` should contain only long-term profile fields. Request/session intent fields are passed at call time in `options.session_context` or as direct option keys such as `destination`, `number_of_guests`, `session_price_range`, `session_trip_types`, `session_room_views`, and `session_amenities`.

## Candidate Hotel

Supports `item_id`, `item_type`, `name`, `destination`, `hotel_type`, price fields, `amenities`, `room_views`, `preference_habits`, `tags`, `location_tags`, `nearby_places`, `rating`, `review_sentiment`, `available`, `available_rooms`, and `keyword_score`.

Recommended production input is a lightweight candidate shell from the search/retrieval layer:

```json
{
  "candidate_items": [
    {"item_id": 11024791, "item_type": "hotel", "search_rank": 1, "search_score": 0.78},
    {"item_id": 1370955, "item_type": "hotel", "search_rank": 2, "search_score": 0.74}
  ],
  "options": {
    "enrich_postgres_candidates": true
  }
}
```

`search_score`, `retrieval_score`, and `semantic_score` are accepted as aliases for `keyword_score`. Full hotel descriptions, images, amenities, rooms, nearby places, and reviews should come from PostgreSQL enrichment, not from the rerank input.

The normalizer also accepts PostgreSQL hotel rows using `id`, `city`, `accommodation_type`, `review_score`, `star_rating`, `suitable_for`, `policyNotes`, `min_price`/`max_price`, `room_views`, `room_amenities`, `nearby_place_names`, and `room_count`.

PostgreSQL enrichment query shape:

```sql
SELECT
  h.id,
  h.name,
  h.city,
  h.accommodation_type,
  h.review_score,
  h.amenities,
  h.suitable_for,
  MIN(r.price) AS min_price,
  MAX(r.price) AS max_price,
  COUNT(r.id) AS room_count,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.room_view), NULL) AS room_views,
  ARRAY_REMOVE(ARRAY_AGG(DISTINCT p.name), NULL) AS nearby_place_names
FROM hotels h
LEFT JOIN rooms r ON r.hotel_id = h.id
LEFT JOIN nearby_places p ON p.hotel_id = h.id
WHERE h.id = ANY(:candidate_ids)
GROUP BY h.id;
```

Preferred production flow: upstream search passes `candidate_items`, then rerank can enrich those IDs from PostgreSQL before scoring:

```json
{
  "options": {
    "enrich_postgres_candidates": true
  }
}
```

This keeps the candidate set fixed and only fills missing hotel/room/nearby/activity data.
PostgreSQL is never used to discover or append extra candidates inside this rerank module.

## Output

Returns `ranked_items` with `item_id`, `rank`, `final_score`, `base_score`, optional `llm_score`, `feature_scores`, `negative_penalty`, `reasons`, and `warnings`.

Also returns `ranked_hotels`, a JSON list sorted in the same order as `ranked_items`. Each item starts from the enriched PostgreSQL hotel payload when enrichment is enabled and available, otherwise from the original candidate input, then adds `rank`, scores, `feature_scores`, `negative_penalty`, `reasons`, and `warnings`.

When `options.return_debug=true`, returns `debug` with candidate counts, source names, LLM/fallback flags, and mock mode.

Profile lookup expects `Users` to contain `long_term_profile` only. Session/search intent is request-scoped input and is merged into the normalized profile before scoring.
