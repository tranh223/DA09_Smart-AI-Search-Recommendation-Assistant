"""
BGE-M3 embedder (BAAI/bge-m3) via FlagEmbedding.
Dense vectors only — 1024 dimensions.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
VECTOR_SIZE = 1024
DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm < 1e-9:
        return vec
    return vec / norm


def compose_weighted_vectors(
    vectors: list[list[float]],
    weights: list[float],
) -> list[float] | None:
    """Weighted average + L2 normalize."""
    if not vectors:
        return None
    arr = np.array(vectors, dtype=np.float32)
    w = np.array(weights, dtype=np.float32)
    if w.sum() <= 0:
        w = np.ones(len(vectors), dtype=np.float32)
    blended = (arr * w[:, None]).sum(axis=0) / w.sum()
    return _l2_normalize(blended).tolist()


def blend_vectors(
    a: list[float],
    b: list[float],
    weight_a: float = 0.35,
    weight_b: float = 0.65,
) -> list[float]:
    """Blend two vectors then L2 normalize."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    blended = weight_a * va + weight_b * vb
    return _l2_normalize(blended).tolist()


class BGEEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        use_fp16: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        from FlagEmbedding import BGEM3FlagModel

        logger.info("Loading embedding model: %s", self.model_name)
        self._model = BGEM3FlagModel(self.model_name, use_fp16=self.use_fp16)

    def encode(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[list[float]]:
        """
        Encode texts to dense vectors.
        is_query=True prepends retrieval instruction for asymmetric search.
        """
        if not texts:
            return []

        self._load_model()

        if is_query:
            inputs = [
                f"Represent this sentence for searching relevant passages: {t}"
                for t in texts
            ]
        else:
            inputs = texts

        output = self._model.encode(
            inputs,
            batch_size=self.batch_size,
            max_length=512,
        )
        dense = output["dense_vecs"]
        return [v.tolist() if hasattr(v, "tolist") else list(v) for v in dense]

    def encode_one(self, text: str, *, is_query: bool = False) -> list[float]:
        return self.encode([text], is_query=is_query)[0]


@lru_cache(maxsize=1)
def get_embedder() -> BGEEmbedder:
    return BGEEmbedder()
