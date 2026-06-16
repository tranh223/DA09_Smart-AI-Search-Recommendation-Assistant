# Architecture

```text
run_demo.py
-> load example_request.json
-> candidate_items already exist
-> if user_context is missing and user_id exists:
      fetch user profile from Mongo or mock store
-> fetch bookings by user_id and candidate hotel_ids
-> compute booking_signals
-> compute trend_score / hotness_score for each hotel
-> normalize user profile count fields into weights
-> normalize candidate hotel fields
-> hard filter
-> rule-based score
-> take top N by base_score
-> call LLM reranker if options.use_llm_rerank = true
-> validate LLM output
-> merge base_score and llm_score
-> fallback to base_score if LLM fails
-> sort final_score desc
-> build explanations
-> write rerank log JSONL
-> print final result to terminal
```

Adapters isolate external systems:

- `mock_store.py`: local JSON files.
- `mongo_client.py`: MongoDB profile and booking lookup.
- `llm_reranker.py`: mock LLM response or OpenRouter chat completions.

