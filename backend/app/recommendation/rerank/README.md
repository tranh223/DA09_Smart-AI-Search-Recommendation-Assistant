# Hotel Reranking Demo

Self-contained Python 3.13 demo for hotel reranking. It accepts candidate hotels from another service and combines user profile signals, booking trends, rule scoring, and optional OpenRouter LLM reranking.

## Quick Start

```bash
cd /Users/tranvangiaban/Code/DA09_Smart-AI-Search-Recommendation-Assistant
python -m venv .venv
source .venv/bin/activate
pip install pydantic python-dotenv requests pymongo pytest tabulate
cp backend/app/recommendation/rerank/.env.example backend/app/recommendation/rerank/.env
python -m backend.app.recommendation.rerank.run_demo
python -m pytest backend/tests/unit/recommendation/rerank
```

`MOCK_MODE=true` is the default, so the demo runs without MongoDB or an OpenRouter API key.

To enrich passed-in candidates from PostgreSQL, set `POSTGRES_DSN` in `.env` and set `options.enrich_postgres_candidates=true`. This queries only the hotel IDs already present in `candidate_items` and fills room, nearby place, activity, price, and review fields before rerank scoring. PostgreSQL does not create or add candidates in this module.

To enrich candidates from a live OTA hotel API, set `HOTEL_API_BASE_URL` and `HOTEL_API_KEY` in `.env`, then pass `options={"enrich_hotel_api_candidates": True}`. The module will call `/api/hotels/{hotel_id}` and merge the returned hotel details into each candidate before scoring.

To prioritize amenity-rich hotels from session context, include `boost_amenity_rich_hotels: true` inside `options.session_context`.

## Public API

```python
from app.recommendation.rerank import rerank

result = rerank(
    user_id="user_002",
    user_context=None,
    candidate_items=[...],
    query="Tôi đi Vũng Tàu cùng gia đình...",
    options={"top_k": 10, "use_llm_rerank": True},
)
```

Assumptions:

- This module is only for hotel reranking, not OTA search, chat, or candidate generation.
- `user_context` takes precedence over profile lookup when provided.
- Item and hotel IDs are converted to strings internally and in output.
- Vietnamese labels are preserved and exact matching is attempted before aliases.
- MongoDB defaults to `Users` and `Booking`; request-scoped session/search intent is passed in `options.session_context`.
- Output includes both compact `ranked_items` and `ranked_hotels`, where `ranked_hotels` preserves the sorted hotel JSON payload from PostgreSQL enrichment or the original candidate input.
- If MongoDB or LLM is unavailable, the module falls back to mock/profile-empty and rule-based scoring.
