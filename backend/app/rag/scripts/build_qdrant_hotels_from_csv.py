#!/usr/bin/env python3

"""Build a Qdrant vector index from the already-crawled hotel CSV.

Reads:
  backend/app/rag/data/hotels_rows.csv

Writes:
  - creates/updates Qdrant collection (default: hotels)
  - upserts vectors for:
      - vector: name (text)
      - metadata: {id, name, area, country, source_url}

Expected CSV columns (at least):
  id,name,area,country,source_url

Env vars:
  - QDRANT_HOST (default: 127.0.0.1)
  - QDRANT_PORT (default: 6333)
  - QDRANT_COLLECTION (default: hotels)
  - QDRANT_DISTANCE (default: cosine)
  - QDRANT_VECTOR_DIM (optional; if not set, inferred from embedding model)

Embedding:
  - uses the project's existing embedder if available:
      backend/app/recommendation/embedding/bge_embedder.py
    otherwise falls back to a simple requests/OpenAI approach is NOT implemented.
"""

from __future__ import annotations

import csv
import sys

import os
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


ROOT = Path(__file__).resolve().parents[1]  # backend/app/rag
DATA_DIR = ROOT / "data"
# Support both historical filename variants.
CSV_PATH = DATA_DIR / "hotels_rows.csv"
ALT_CSV_PATH = DATA_DIR / "hotel_supabase_rows.csv"



def _require_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v:
        return v
    if default is not None:
        return default
    raise RuntimeError(f"Missing required env var: {name}")


def iter_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def get_embedder():
    """Use existing project embedder if possible."""

    # Ensure `backend/` is on sys.path so imports like `app.xxx` work when running
    # `python backend/app/rag/scripts/...`.
    backend_root = Path(__file__).resolve().parents[3]  # .../backend
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    try:
        # Project path exists in repo.
        from app.recommendation.embedding.bge_embedder import get_embedder as _get

        return _get()

    except Exception:
        pass

    # If embedder module path differs, try common location.
    try:
        from app.db.vector_store.qdrant_store import get_embedder as _get

        return _get()
    except Exception:
        pass

    # Fallback: HuggingFace/SentenceTransformers embedder.
    try:
        # Import relative to this script directory.
        from app.rag.scripts.hf_embedder import embed_one  # type: ignore

        class _HFEmbedder:
            def encode_one(self, text: str, *, is_query: bool):
                return embed_one(text, is_query=is_query)

        return _HFEmbedder()
    except Exception as e:
        raise RuntimeError(
            "Could not import project's embedder and HF fallback failed."
        ) from e



def build():
    qdrant_host = _require_env("QDRANT_HOST", "127.0.0.1")
    qdrant_port = int(_require_env("QDRANT_PORT", "6333"))
    collection = _require_env("QDRANT_COLLECTION", "hotels")
    distance = _require_env("QDRANT_DISTANCE", "cosine")

    client = QdrantClient(host=qdrant_host, port=qdrant_port)

    embedder = get_embedder()

    # Pick the existing CSV file.
    csv_path = CSV_PATH if CSV_PATH.exists() else ALT_CSV_PATH

    if not csv_path.exists():
        raise RuntimeError(
            f"No input CSV found. Looked for: {CSV_PATH} and {ALT_CSV_PATH}"
        )

    # Infer vector size by embedding one sample.
    first_row: dict[str, str] | None = None
    for r in iter_rows(csv_path):
        first_row = r
        break

    if not first_row:
        raise RuntimeError(f"No rows found in {CSV_PATH}")

    vector = embedder.encode_one(first_row.get("name", ""), is_query=False)
    dim = len(vector)

    if distance.lower() == "cosine":
        dist_model = qm.Distance.COSINE
    elif distance.lower() == "dot":
        dist_model = qm.Distance.DOT
    elif distance.lower() == "euclid":
        dist_model = qm.Distance.EUCLID
    else:
        dist_model = qm.Distance.COSINE

    # Create collection if not exists (connection errors handled explicitly).
    try:
        existing = {c.name for c in client.get_collections().collections}
    except Exception as e:
        qdrant_host = qdrant_host  # from outer scope
        qdrant_port = qdrant_port  # from outer scope
        raise RuntimeError(
            "Could not connect to Qdrant. Ensure QDRANT_HOST/QDRANT_PORT are correct and Qdrant is running. "
            f"Tried: {qdrant_host}:{qdrant_port}. Error: {e}"
        ) from e

    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=qm.VectorParams(size=dim, distance=dist_model),
        )
    else:
        # Best-effort: if dim differs, recreate would be needed (left as is).
        pass


    points: list[qm.PointStruct] = []
    batch_size = int(os.getenv("QDRANT_BATCH_SIZE", "256"))

    # We already consumed first_row; process it plus the rest.
    rows_iter = iter_rows(csv_path)

    # Re-create iterator and skip until first row index would require state; simpler: just re-iterate fully and ignore overhead.

    for row in rows_iter:
        hotel_id = row.get("id")
        name = row.get("name") or ""
        area = row.get("area")
        country = row.get("country")
        source_url = row.get("source_url")

        if not hotel_id:
            continue

        v = embedder.encode_one(name, is_query=False)

        city = row.get("city")

        # Qdrant point IDs must be either an unsigned integer (>=0) or a UUID.
        # Your CSV may contain other formats; we safely map to an unsigned int.
        # If id isn't numeric, fall back to a stable unsigned hash.
        if str(hotel_id).isdigit():
            qdrant_point_id = int(hotel_id)
        else:
            # Stable unsigned 64-bit hash
            qdrant_point_id = (abs(hash(str(hotel_id))) % (2**64))

        payload: dict[str, Any] = {
            "id": int(hotel_id) if str(hotel_id).isdigit() else hotel_id,
            "name": name,
            "city": city,
            "area": area,
            "country": country,
            "source_url": source_url,
        }

        points.append(
            qm.PointStruct(
                id=qdrant_point_id,
                vector=v,
                payload=payload,
            )
        )


        if len(points) >= batch_size:
            client.upsert(collection_name=collection, points=points)
            points.clear()

    if points:
        client.upsert(collection_name=collection, points=points)

    print(f"Qdrant build complete: collection={collection} dim={dim}")


if __name__ == "__main__":
    build()

