# Implementation Plan

1. Load configuration from `.env`.
2. Resolve profile source: direct `user_context`, mock JSON, MongoDB `Users`, or empty fallback.
3. Normalize count-based profile groups into 0..1 weights.
4. Normalize candidate hotels and IDs.
5. Load `Booking` documents and compute per-hotel trend signals from `booked_at` or `booking_date`.
6. Apply hard filters.
7. Score remaining candidates with transparent rule features.
8. Optionally rerank top-N candidates with LLM.
9. Validate LLM JSON and merge scores.
10. Build explanations, debug metadata, and JSONL logs.
