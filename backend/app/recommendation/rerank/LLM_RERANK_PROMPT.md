# LLM Rerank Prompt

The LLM receives only top-N rule-scored candidates.

Default OpenRouter model:

```text
nvidia/nemotron-3-ultra-550b-a55b:free
```

Required instructions:

```text
You are an OTA hotel reranking assistant.
Only use the provided data.
Do not invent hotel facts.
Respect hard constraints.
Return strict JSON only.
Rerank the provided hotel IDs.
Do not include hotel IDs that are not in the candidate list.
Vietnamese labels such as hotel_type, amenities, room_views, trip_types must be preserved.
```

Expected JSON:

```json
{
  "ranked_items": [
    {
      "item_id": "569205",
      "llm_score": 0.93,
      "rank": 1,
      "reasons": ["..."],
      "warnings": []
    }
  ]
}
```
