"""
Qdrant vector store for hotel & tag embeddings (BGE-M3, 1024-dim).
"""

from __future__ import annotations

import logging
import os
import uuid
from functools import lru_cache

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.recommendation.embedding.bge_embedder import VECTOR_SIZE

load_dotenv()
logger = logging.getLogger(__name__)

COLLECTION_TAGS = os.getenv("QDRANT_COLLECTION_TAGS", "hotel_tags")
COLLECTION_HOTELS = os.getenv("QDRANT_COLLECTION_HOTELS", "hotels")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None


def make_tag_id(tag_category: str, tag_name: str) -> str:
    return f"{tag_category}::{tag_name}"


def tag_point_uuid(tag_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, tag_id))


class QdrantStore:
    def __init__(
        self,
        url: str = QDRANT_URL,
        api_key: str | None = QDRANT_API_KEY,
    ):
        self.client = QdrantClient(url=url, api_key=api_key)

    def ensure_collections(self, *, recreate: bool = False) -> None:
        for name in (COLLECTION_TAGS, COLLECTION_HOTELS):
            exists = self.client.collection_exists(name)
            if exists and recreate:
                logger.info("Recreating collection: %s", name)
                self.client.delete_collection(name)
                exists = False
            if not exists:
                logger.info("Creating collection: %s (dim=%d)", name, VECTOR_SIZE)
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )

    def upsert_tags(self, points: list[PointStruct], *, batch_size: int = 64) -> int:
        return self._upsert_batched(COLLECTION_TAGS, points, batch_size)

    def upsert_hotels(self, points: list[PointStruct], *, batch_size: int = 64) -> int:
        return self._upsert_batched(COLLECTION_HOTELS, points, batch_size)

    def _upsert_batched(
        self,
        collection: str,
        points: list[PointStruct],
        batch_size: int,
    ) -> int:
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(collection_name=collection, points=batch)
        return len(points)

    def search_hotels(
        self,
        query_vector: list[float],
        *,
        city: str | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> list[dict]:
        query_filter = None
        if city:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="city_name",
                        match=MatchValue(value=city),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=COLLECTION_HOTELS,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        results = response.points
        return [
            {
                "hotel_id": hit.payload.get("hotel_id"),
                "hotel_name": hit.payload.get("hotel_name"),
                "city_name": hit.payload.get("city_name"),
                "score": hit.score,
                "tags": hit.payload.get("tags", []),
                "payload": hit.payload,
            }
            for hit in results
        ]

    def scroll_all_tag_vectors(self) -> dict[str, list[float]]:
        """Load all tag vectors from Qdrant (for hotels-only rebuild)."""
        tag_vectors: dict[str, list[float]] = {}
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=COLLECTION_TAGS,
                limit=256,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            for rec in records:
                tag_id = (rec.payload or {}).get("tag_id")
                if tag_id and rec.vector is not None:
                    vec = rec.vector
                    tag_vectors[tag_id] = vec.tolist() if hasattr(vec, "tolist") else list(vec)
            if offset is None:
                break
        return tag_vectors

    def get_tag_vector(self, tag_id: str) -> list[float] | None:
        pid = tag_point_uuid(tag_id)
        points = self.client.retrieve(
            collection_name=COLLECTION_TAGS,
            ids=[pid],
            with_vectors=True,
        )
        if not points:
            return None
        return points[0].vector  # type: ignore[return-value]

    def count(self, collection: str) -> int:
        info = self.client.get_collection(collection)
        return info.points_count or 0


@lru_cache(maxsize=1)
def get_qdrant_store() -> QdrantStore:
    return QdrantStore()
