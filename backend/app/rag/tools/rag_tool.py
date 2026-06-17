"""tools.rag_tool

FAISS-based vector retrieval for hotels.

- Embeddings are stored in FAISS.
- Metadata is NOT embedded; instead stored in a sidecar JSON.
- Metadata filtering is performed in Python after FAISS candidate retrieval.

Expected data files (default under data/):
- faiss_hotels.index
- faiss_hotels_meta.json        (vector_id -> metadata dict)
- faiss_hotels_chunks.json      (vector_id -> {chunk_id, section, content, metadata})
- faiss_hotels_config.json

Note: FAISS itself does not provide built-in metadata filtering; we retrieve candidates first
and then apply filter predicates in Python.
"""

from __future__ import annotations

import json
import re
import unicodedata

from utils.langsmith_tracer import tracer
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

_INDEX = None
_META: Dict[str, Any] | None = None
_CHUNKS: Dict[str, Any] | None = None


def _normalize_lookup_text(value: str) -> str:
    value = value.lower().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _resolve_hotel_ids(hotel_name: str) -> Set[int]:
    """Resolve hotel ids from loaded vector metadata by hotel name."""

    if not hotel_name or not hotel_name.strip():
        return set()

    global _META
    if _META is None:
        meta_path = Path(__file__).resolve().parents[1] / "data" / "faiss_hotels_meta.json"
        _META = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    needle = _normalize_lookup_text(hotel_name)
    needle_compact = needle.replace(" ", "")
    if not needle:
        return set()

    resolved: Set[int] = set()
    for meta in (_META or {}).values():
        if not isinstance(meta, dict):
            continue

        candidate_name = meta.get("hotel_name")
        hotel_id = meta.get("hotel_id")
        if not candidate_name or hotel_id is None:
            continue

        haystack = _normalize_lookup_text(str(candidate_name))
        haystack_compact = haystack.replace(" ", "")
        if (
            needle in haystack
            or needle_compact in haystack_compact
            or all(part in haystack.split() for part in needle.split())
        ):
            try:
                resolved.add(int(hotel_id))
            except (TypeError, ValueError):
                continue

    return resolved


def _load_once() -> None:
    global _INDEX, _META, _CHUNKS
    if _INDEX is not None and _META is not None and _CHUNKS is not None:
        return

    base_dir = Path(__file__).resolve().parents[1] / "data"
    idx_path = base_dir / "faiss_hotels.index"
    meta_path = base_dir / "faiss_hotels_meta.json"
    chunks_path = base_dir / "faiss_hotels_chunks.json"

    if not idx_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found at {idx_path}. Run scripts/build_faiss_hotels_index.py first."
        )

    import faiss  # type: ignore

    _INDEX = faiss.read_index(str(idx_path))

    if meta_path.exists():
        _META = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        _META = {}

    if chunks_path.exists():
        _CHUNKS = json.loads(chunks_path.read_text(encoding="utf-8"))
    else:
        _CHUNKS = {}


def _embed_query(query: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    # Prefer the model used when building the index.
    # We read it from faiss_hotels_config.json if available.
    if not hasattr(_embed_query, "_model"):
        model_name = "BAAI/bge-m3"
        try:
            base_dir = Path(__file__).resolve().parents[1] / "data"
            cfg_path = base_dir / "faiss_hotels_config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                model_name = cfg.get("embedding_model") or model_name
        except Exception:
            pass

        _embed_query._model = SentenceTransformer(model_name)

    model = _embed_query._model
    vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    return np.array(vec, dtype=np.float32)



def _metadata_match(meta: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Match a chunk metadata dict against filter constraints.

    Supported semantics:
    - scalar equality (actual == wanted)
    - if actual is list, then:
        - wanted is str: membership
        - wanted is list: all members must be in actual
    """

    if not filters:
        return True

    for key, wanted in filters.items():
        actual = meta.get(key)

        if wanted is None:
            continue

        if isinstance(actual, list):
            if isinstance(wanted, str):
                if wanted not in actual:
                    return False
            elif isinstance(wanted, list):
                if not all(x in actual for x in wanted):
                    return False
            else:
                return False
        elif isinstance(wanted, list):
            if actual not in wanted:
                return False
        else:
            if actual != wanted:
                return False

    return True


@tracer.trace("tool_rag_search")
def search_rag(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search the hotels RAG vector DB.

    This matches the existing call site in modules/retrieval.py:
        search_rag(query, top_k)

    Returns list of dict results:
      [{score, chunk_id, section, content, metadata}, ...]

    Metadata filtering hook:
      If later you extend this to accept filters, you can call internal search
      with a `filters` param; for now we keep current signature.
    """

    _load_once()

    if not query or not query.strip():
        return []

    k = max(int(top_k), 1)
    candidate_k = min(max(k * 8, 20), 500)

    qvec = _embed_query(query)

    # Embeddings were normalized at indexing and at query time.
    # Use inner product as cosine similarity.
    # _load_once guarantees _INDEX is initialized
    scores, ids = _INDEX.search(qvec, candidate_k)  # type: ignore[union-attr]
    ids = ids[0]
    scores = scores[0]

    out: List[Dict[str, Any]] = []

    for vid, score in zip(ids, scores):
        if int(vid) < 0:
            continue

        vid_str = str(int(vid))
        meta = (_META or {}).get(vid_str, {})
        chunk_payload = (_CHUNKS or {}).get(vid_str, {})

        # No filter by default
        if not _metadata_match(meta, filters=None):
            continue

        out.append(
            {
                "score": float(score),
                "chunk_id": chunk_payload.get("chunk_id"),
                "section": chunk_payload.get("section"),
                "content": chunk_payload.get("content"),
                "metadata": chunk_payload.get("metadata") or meta,
            }
        )

        if len(out) >= k:
            break

    return out

