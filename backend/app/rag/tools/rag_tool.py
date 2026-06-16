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
import hashlib
import re
import shutil
import tempfile
import unicodedata

from utils.langsmith_tracer import tracer
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

_INDEX = None
_META: Dict[str, Any] | None = None
_CHUNKS: Dict[str, Any] | None = None


def _faiss_readable_index_path(idx_path: Path) -> Path:
    """Return an ASCII-only path for FAISS builds that cannot open Unicode paths."""

    try:
        str(idx_path).encode("ascii")
        return idx_path
    except UnicodeEncodeError:
        stat = idx_path.stat()
        cache_key = hashlib.sha256(
            f"{idx_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
        ).hexdigest()[:16]
        cache_dir = Path(tempfile.gettempdir()) / "hotel_rag_faiss"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path = cache_dir / f"faiss_hotels_{cache_key}.index"
        if not cached_path.exists() or cached_path.stat().st_size != stat.st_size:
            shutil.copyfile(idx_path, cached_path)
        return cached_path


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

    _INDEX = faiss.read_index(str(_faiss_readable_index_path(idx_path)))

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
        else:
            if isinstance(wanted, list):
                if actual not in wanted:
                    return False
            elif actual != wanted:
                return False

    return True


def _normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _resolve_hotel_ids(hotel_name: str) -> set[int]:
    """Resolve a supplied hotel name against sidecar metadata without an LLM call."""

    wanted = _normalize_name(hotel_name)
    wanted_compact = wanted.replace(" ", "")
    wanted_tokens = {
        token for token in wanted.split() if token not in {"hotel", "resort", "khach", "san"}
    }
    matches: set[int] = set()

    for meta in (_META or {}).values():
        actual_name = str(meta.get("hotel_name") or "")
        actual = _normalize_name(actual_name)
        actual_compact = actual.replace(" ", "")
        actual_tokens = set(actual.split())
        if wanted_compact in actual_compact or actual_compact in wanted_compact:
            matches.add(int(meta["hotel_id"]))
        elif wanted_tokens and wanted_tokens.issubset(actual_tokens):
            matches.add(int(meta["hotel_id"]))
    return matches


@tracer.trace("tool_rag_search")
def search_rag(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Search the hotels RAG vector DB.

    This matches the existing call site in modules/retrieval.py:
        search_rag(query, top_k)

    Returns list of dict results:
      [{score, chunk_id, section, content, metadata}, ...]

    Optional filters support hotel_name, section, and other metadata fields.
    """

    _load_once()

    if not query or not query.strip():
        return []

    k = max(int(top_k), 1)
    candidate_k = min(max(k * 20, 100), 1000)
    metadata_filters = dict(filters or {})
    hotel_name = metadata_filters.pop("hotel_name", None)
    hotel_ids = _resolve_hotel_ids(str(hotel_name)) if hotel_name else set()

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

        if hotel_ids and meta.get("hotel_id") not in hotel_ids:
            continue
        if not _metadata_match(meta, filters=metadata_filters):
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

