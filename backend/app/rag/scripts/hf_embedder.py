#!/usr/bin/env python3
"""HuggingFace embedder used for building Qdrant hotel vectors.

This is a lightweight fallback when the project's embedder module cannot be imported.

Environment variables (optional):
- HF_EMBED_MODEL: default 'BAAI/bge-small-en-v1.5'

It uses sentence-transformers for embeddings.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List


@lru_cache(maxsize=1)
def _load_model():
    model_name = os.getenv("HF_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    return model


def embed_one(text: str, *, is_query: bool) -> List[float]:
    model = _load_model()
    t = text or ""

    # Some bge models perform better with a simple query/document prefix,
    # but we keep it configurable.
    q_prefix = os.getenv("HF_QUERY_PREFIX", "")
    d_prefix = os.getenv("HF_DOC_PREFIX", "")

    if is_query and q_prefix:
        t = q_prefix + t
    elif (not is_query) and d_prefix:
        t = d_prefix + t

    vec = model.encode(t, normalize_embeddings=True)
    # sentence-transformers returns numpy array
    return [float(x) for x in vec]

