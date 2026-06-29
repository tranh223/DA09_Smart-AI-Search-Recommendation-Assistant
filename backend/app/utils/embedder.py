from __future__ import annotations

"""Embedder loader for the RAG subsystem.

This avoids importing from `app.recommendation.embedding.*` because those
modules may not exist in this project layout.

We first try Qdrant-store embedder (if present), otherwise fall back to the
local HF/SentenceTransformers embedder in `app.rag.scripts.hf_embedder`.

Public API:
- get_embedder()
"""

import sys
from pathlib import Path


def get_embedder():
    # Ensure backend/ is on sys.path so `app.*` imports work when running
    # scripts directly.
    backend_root = Path(__file__).resolve().parents[3]  # .../backend
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    # 1) Try Qdrant store embedder (project-specific)
    try:
        from app.db.vector_store.qdrant_store import get_embedder as _get  # type: ignore

        return _get()
    except Exception:
        pass

    # 2) Local HF fallback
    try:
        from app.rag.scripts.hf_embedder import embed_one  # type: ignore

        class _HFEmbedder:
            def encode_one(self, text: str, *, is_query: bool):
                return embed_one(text, is_query=is_query)

        return _HFEmbedder()
    except Exception as e:
        raise RuntimeError(
            "Failed to load an embedder for RAG. Tried qdrant_store.get_embedder() and app.rag.scripts.hf_embedder."
        ) from e

