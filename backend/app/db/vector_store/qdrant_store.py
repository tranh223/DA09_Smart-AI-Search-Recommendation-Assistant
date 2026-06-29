"""Qdrant vector store wrapper used by RAG hotel entity resolver.

The hotel Qdrant collection is expected to be built from:
  backend/app/rag/data/hotels_rows.csv

Vector: embedding of hotel name
Payload/metadata:
  - id
  - name
  - city
  - area (optional)
  - country
  - source_url

This module provides a stable API for the rest of the backend.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient


def _get_env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v is not None and v != "" else default


@lru_cache(maxsize=1)
def get_qdrant_store() -> "QdrantHotelStore":
    return QdrantHotelStore()


class QdrantHotelStore:
    def __init__(self) -> None:
        host = os.getenv("QDRANT_HOST", "127.0.0.1")
        port = _get_env_int("QDRANT_PORT", 6333)
        collection = os.getenv("QDRANT_COLLECTION", "hotels")
        self.collection = collection
        self.client = QdrantClient(host=host, port=port)

    def search_hotels(
        self,
        query_vector: list[float],
        *,
        city: str | None,
        limit: int,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search Qdrant for similar hotels.

        Returns list of dicts shaped like:
          {
            "hotel_id": int|str,
            "hotel_name": str,
            "city_name": str|None,
            "score": float,
            "payload": { ... }
          }
        """

        scroll_filter = None
        if city:
            # If payload has city, use it; otherwise Qdrant filter will just return none.
            # (Resolver will still fuzzy-rerank top-K if Qdrant returns empty.)
            normalized = city.strip()
            scroll_filter = {
                "must": [
                    {"key": "city", "match": {"value": normalized}},
                ]
            }

        # qdrant-client v1.x vs v0.x have different method names.
        # Prefer `search`, but fall back to `query_points`.
        if hasattr(self.client, "search"):
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=scroll_filter,
                with_payload=True,
            )
        else:
            # `query_points` returns a `QueryResponse` with `.points`.
            # Newer qdrant-client uses `query` arg name for the vector.
            # This keeps compatibility with your installed qdrant_client.
            resp = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=limit,
                query_filter=scroll_filter,
                with_payload=True,
            )
            hits = getattr(resp, "points", None) or []


        results: list[dict[str, Any]] = []
        for h in hits or []:
            payload = h.payload or {}
            results.append(
                {
                    "hotel_id": payload.get("id"),
                    "hotel_name": payload.get("name"),
                    "city_name": payload.get("city"),
                    "score": float(getattr(h, "score", 0.0) or 0.0),
                    "payload": payload,
                }
            )

        if score_threshold is not None:
            results = [r for r in results if r.get("score", 0.0) >= score_threshold]

        return results

