"""
Build tag & hotel embeddings with BAAI/bge-m3 and upsert into Qdrant.

Data sources:
  - data/raw/tag_hotel.json          → tag catalog (embed once per tag)
  - data/raw/hotel_tag_embedding.json → hotel ↔ tag mapping (compose, no re-embed tag)

Usage (from backend/):
  python scripts/build_qdrant_embeddings.py
  python scripts/build_qdrant_embeddings.py --recreate
  python scripts/build_qdrant_embeddings.py --tags-only
  python scripts/build_qdrant_embeddings.py --hotels-only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

from qdrant_client.models import PointStruct

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.vector_store.qdrant_store import (
    COLLECTION_HOTELS,
    COLLECTION_TAGS,
    QdrantStore,
    tag_point_uuid,
    make_tag_id,
)
from app.recommendation.embedding.bge_embedder import (
    BGEEmbedder,
    blend_vectors,
    compose_weighted_vectors,
)
from app.recommendation.candidate_generation.hotel_search.embedding_search import HotelBM25Index

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAG_CATALOG_PATH = PROJECT_ROOT / "data" / "raw" / "tag_hotel.json"
HOTEL_TAG_PATH = PROJECT_ROOT / "data" / "raw" / "hotel_tag_embedding.json"

TOP_TAGS_PER_HOTEL = 20
HOTEL_BASE_WEIGHT = 0.35
TAG_PART_WEIGHT = 0.65


def load_tag_catalog(path: Path) -> dict[str, dict]:
    items = json.loads(path.read_text(encoding="utf-8-sig"))
    catalog: dict[str, dict] = {}
    for item in items:
        tag_id = make_tag_id(item["tagCategory"], item["tagName"])
        catalog[tag_id] = {
            "tag_id": tag_id,
            "tag_category": item["tagCategory"],
            "tag_name": item["tagName"],
            "description": item.get("Description") or item.get("description") or "",
        }
    return catalog


def tag_embed_text(tag: dict) -> str:
    return (
        f"[{tag['tag_category']}] {tag['tag_name']}. "
        f"{tag['description']}"
    ).strip()


def load_hotels_grouped(path: Path) -> dict[int, dict]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    hotels: dict[int, dict] = {}
    for row in rows:
        hid = int(row["hotelId"])
        if hid not in hotels:
            hotels[hid] = {
                "hotel_id": hid,
                "hotel_name": row["hotelName"],
                "city_name": row["cityName"],
                "tags": [],
            }
        tag_id = make_tag_id(row["tagCategory"], row["tagName"])
        hotels[hid]["tags"].append(
            {"tag_id": tag_id, "weight": float(row.get("weight") or 1.0)}
        )
    return hotels


def embed_tags(
    store: QdrantStore,
    embedder: BGEEmbedder,
    catalog: dict[str, dict],
) -> dict[str, list[float]]:
    tag_ids = list(catalog.keys())
    texts = [tag_embed_text(catalog[tid]) for tid in tag_ids]
    logger.info("Embedding %d unique tags...", len(tag_ids))

    vectors = embedder.encode(texts, is_query=False)
    tag_vectors = dict(zip(tag_ids, vectors))

    points = [
        PointStruct(
            id=tag_point_uuid(tid),
            vector=vec,
            payload={
                "tag_id": tid,
                "tag_category": catalog[tid]["tag_category"],
                "tag_name": catalog[tid]["tag_name"],
                "description": catalog[tid]["description"],
            },
        )
        for tid, vec in tag_vectors.items()
    ]
    store.upsert_tags(points)
    logger.info("Upserted %d tags → Qdrant collection '%s'", len(points), COLLECTION_TAGS)
    return tag_vectors


def _top_tags(tags: list[dict], limit: int) -> list[dict]:
    return sorted(tags, key=lambda t: t["weight"], reverse=True)[:limit]


def embed_hotels(
    store: QdrantStore,
    embedder: BGEEmbedder,
    hotels: dict[int, dict],
    tag_vectors: dict[str, list[float]],
) -> int:
    hotel_ids = list(hotels.keys())
    base_texts = [
        f"{hotels[hid]['hotel_name']} tại {hotels[hid]['city_name']}"
        for hid in hotel_ids
    ]
    logger.info("Embedding base text for %d hotels...", len(hotel_ids))
    base_vectors = embedder.encode(base_texts, is_query=False)

    points: list[PointStruct] = []
    skipped = 0
    missing_tag_refs = 0

    for hid, base_vec in zip(hotel_ids, base_vectors):
        hotel = hotels[hid]
        selected = _top_tags(hotel["tags"], TOP_TAGS_PER_HOTEL)

        vecs: list[list[float]] = []
        weights: list[float] = []
        resolved_tags: list[dict] = []

        for t in selected:
            vec = tag_vectors.get(t["tag_id"])
            if vec is None:
                missing_tag_refs += 1
                continue
            vecs.append(vec)
            weights.append(t["weight"])
            resolved_tags.append(t)

        tag_part = compose_weighted_vectors(vecs, weights)
        if tag_part is None:
            skipped += 1
            continue

        hotel_vec = blend_vectors(
            base_vec,
            tag_part,
            weight_a=HOTEL_BASE_WEIGHT,
            weight_b=TAG_PART_WEIGHT,
        )

        points.append(
            PointStruct(
                id=hid,
                vector=hotel_vec,
                payload={
                    "hotel_id": hid,
                    "hotel_name": hotel["hotel_name"],
                    "city_name": hotel["city_name"],
                    "tags": resolved_tags,
                    "tag_count": len(resolved_tags),
                },
            )
        )

    store.upsert_hotels(points)
    logger.info(
        "Upserted %d hotels → Qdrant collection '%s' (skipped=%d, missing_tag_refs=%d)",
        len(points),
        COLLECTION_HOTELS,
        skipped,
        missing_tag_refs,
    )
    return len(points)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build BGE-M3 embeddings in Qdrant")
    parser.add_argument("--recreate", action="store_true", help="Drop & recreate collections")
    parser.add_argument("--tags-only", action="store_true", help="Only embed tag catalog")
    parser.add_argument("--hotels-only", action="store_true", help="Only embed hotels (tags must exist)")
    parser.add_argument("--bm25-only", action="store_true", help="Only build BM25 keyword index")
    parser.add_argument("--tag-catalog", type=Path, default=TAG_CATALOG_PATH)
    parser.add_argument("--hotel-tags", type=Path, default=HOTEL_TAG_PATH)
    args = parser.parse_args()

    if args.bm25_only:
        if not args.hotel_tags.exists():
            raise FileNotFoundError(f"Hotel-tag file not found: {args.hotel_tags}")
        hotels = load_hotels_grouped(args.hotel_tags)
        logger.info("Building BM25 index for %d hotels...", len(hotels))
        HotelBM25Index.build(hotels).save()
        logger.info("BM25 index build complete.")
        return

    if not args.tag_catalog.exists():
        raise FileNotFoundError(f"Tag catalog not found: {args.tag_catalog}")
    if not args.hotels_only and not args.hotel_tags.exists():
        raise FileNotFoundError(f"Hotel-tag file not found: {args.hotel_tags}")

    store = QdrantStore()
    embedder = BGEEmbedder()

    store.ensure_collections(recreate=args.recreate)

    tag_vectors: dict[str, list[float]] = {}

    if not args.hotels_only:
        catalog = load_tag_catalog(args.tag_catalog)
        logger.info("Loaded %d tags from catalog", len(catalog))
        tag_vectors = embed_tags(store, embedder, catalog)

    if not args.tags_only:
        if args.hotels_only and not tag_vectors:
            logger.info("Loading tag vectors from Qdrant for hotel composition...")
            tag_vectors = store.scroll_all_tag_vectors()
            logger.info("Loaded %d tag vectors from Qdrant", len(tag_vectors))

        hotels = load_hotels_grouped(args.hotel_tags)
        logger.info("Loaded %d hotels (%d tag rows)", len(hotels), sum(len(h["tags"]) for h in hotels.values()))
        embed_hotels(store, embedder, hotels, tag_vectors)
        logger.info("Building BM25 keyword index...")
        HotelBM25Index.build(hotels).save()

    logger.info(
        "Done. Qdrant counts — tags: %d, hotels: %d",
        store.count(COLLECTION_TAGS),
        store.count(COLLECTION_HOTELS),
    )


if __name__ == "__main__":
    main()
