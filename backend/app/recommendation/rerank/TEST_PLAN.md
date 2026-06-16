# Test Plan

- Profile normalizer: count groups, null groups, malformed values, missing counts, Vietnamese labels, string IDs.
- Trend scorer: empty bookings, fixed current date, 7-day and 30-day windows, growth, confirmed-only filtering.
- Rule scorer: hard filters, budget overlap, amenity/view matching, personalization, penalties.
- Mock rerank: full terminal-compatible flow with no MongoDB or API key, mock LLM merge, LLM fallback.
- Schema: score clamps, string IDs, required output fields.

