from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Callable

try:
    import faiss
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    faiss = None

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    np = None
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    def load_dotenv() -> bool:
        return False

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    OpenAI = None

from query_understanding.config.settings import (
    SEMANTIC_CLOSE_SCORE_DELTA,
    SEMANTIC_SCORE_THRESHOLD,
    SEMANTIC_TOP_K,
)
from query_understanding.models.intent import (
    MappedSemanticItem,
    SemanticMappingResult,
    SemanticPreferenceItem,
)


# Fix path resolution: parents[3] = backend folder, then go up to project root
BACKEND_DIR = Path(__file__).resolve().parents[3]  # backend/
PROJECT_ROOT = BACKEND_DIR.parent  # d:/VFS/DA09/DA09_Smart-AI-Search-Recommendation-Assistant/ parent
DEFAULT_VECTOR_DB_DIR = PROJECT_ROOT.parent / "data" / "vector_db"  # d:/VFS/DA09/data/vector_db/

DEFAULT_TAG_INDEX_PATH = Path(
    os.getenv("QU_TAG_INDEX_PATH", str(DEFAULT_VECTOR_DB_DIR / "tag_hotel.faiss"))
)
DEFAULT_TAG_METADATA_PATH = Path(
    os.getenv("QU_TAG_METADATA_PATH", str(DEFAULT_VECTOR_DB_DIR / "tag_hotel_metadata.json"))
)


class SemanticTagMapper:
    def __init__(
        self,
        *,
        index_path: str | Path = DEFAULT_TAG_INDEX_PATH,
        metadata_path: str | Path = DEFAULT_TAG_METADATA_PATH,
        embedding_model: str = "text-embedding-3-small",
        score_threshold: float = SEMANTIC_SCORE_THRESHOLD,
        close_score_delta: float = SEMANTIC_CLOSE_SCORE_DELTA,
        top_k: int = SEMANTIC_TOP_K,
        embedding_fn: Callable[[list[str]], np.ndarray] | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.embedding_model = embedding_model
        self.score_threshold = score_threshold
        self.close_score_delta = close_score_delta
        self.top_k = max(1, top_k)
        self.keep_close_matches = _env_flag("QU_SEMANTIC_KEEP_CLOSE_MATCHES")
        self.embedding_fn = embedding_fn
        self.last_trace: dict[str, object] = {}
        self._client: OpenAI | None = None
        self._category_indexes: dict[str, faiss.IndexFlatIP] = {}
        self._category_rows: dict[str, list[dict[str, object]]] = {}
        self._loaded = False

    def map_items(self, items: list[SemanticPreferenceItem]) -> SemanticMappingResult:
        if not items:
            self.last_trace = {
                "path": "semantic_mapping",
                "mapped_items": [],
                "status": "empty",
            }
            return SemanticMappingResult()

        if not self._ensure_loaded():
            result = self._fallback_result(items, reason="index_unavailable")
            load_trace = dict(self.last_trace)
            self.last_trace = {
                "path": "semantic_mapping",
                **load_trace,
                "status": "index_unavailable",
                "mapped_items": [asdict(item) for item in result.mapped_items],
            }
            return result

        texts = [item.text for item in items]
        try:
            embeddings = self._embed_texts(texts)
        except Exception as exc:  # noqa: BLE001
            result = self._fallback_result(items, reason=str(exc))
            self.last_trace = {
                "path": "semantic_mapping",
                "status": "embedding_error",
                "error": f"{type(exc).__name__}: {exc}",
                "mapped_items": [asdict(item) for item in result.mapped_items],
            }
            return result

        mapped_items: list[MappedSemanticItem] = []
        for index, item in enumerate(items):
            candidates = self._search_matches(
                embedding=embeddings[index],
                category=item.category,
            )
            if not candidates:
                mapped_items.append(
                    MappedSemanticItem(
                        text=item.text,
                        target_field=item.target_field,
                        category=item.category,
                        matched_category=None,
                        matched_tag=None,
                        score=None,
                        priority=item.priority,
                    )
                )
                continue

            best_score = candidates[0][1]
            if self.keep_close_matches:
                selected_candidates = [
                    candidate
                    for candidate in candidates[: self.top_k]
                    if candidate[1] > self.score_threshold
                    and best_score - candidate[1] <= self.close_score_delta
                ]
            else:
                selected_candidates = [candidates[0]] if best_score > self.score_threshold else []

            if not selected_candidates:
                mapped_items.append(
                    MappedSemanticItem(
                        text=item.text,
                        target_field=item.target_field,
                        category=item.category,
                        matched_category=None,
                        matched_tag=None,
                        score=float(best_score),
                        priority=item.priority,
                    )
                )
                continue

            for matched_row, score, matched_category in selected_candidates:
                matched_tag = str(matched_row["tag_name"])
                mapped_items.append(
                    MappedSemanticItem(
                        text=item.text,
                        target_field=item.target_field,
                        category=item.category,
                        matched_category=matched_category,
                        matched_tag=matched_tag,
                        score=float(score),
                        priority=item.priority,
                    )
                )

        result = SemanticMappingResult(
            mapped_items=mapped_items,
        )
        self.last_trace = {
            "path": "semantic_mapping",
            "status": "ok",
            "score_threshold": self.score_threshold,
            "close_score_delta": self.close_score_delta,
            "top_k": self.top_k,
            "selection": "top_k_close_score" if self.keep_close_matches else "best_match",
            "keep_close_matches": self.keep_close_matches,
            "mapped_items": [asdict(item) for item in result.mapped_items],
        }
        return result

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return True
        self.last_trace = {
            "path": "semantic_mapping",
            "status": "loading_index",
            "index_path": str(self.index_path),
            "metadata_path": str(self.metadata_path),
            "index_exists": self.index_path.exists(),
            "metadata_exists": self.metadata_path.exists(),
            "faiss_available": faiss is not None,
            "numpy_available": np is not None,
        }
        if faiss is None or np is None:
            self.last_trace["load_error"] = "missing_dependency"
            return False
        if not self.index_path.exists() or not self.metadata_path.exists():
            self.last_trace["load_error"] = "missing_index_or_metadata_file"
            return False

        try:
            # Ensure proper UTF-8 encoding for Vietnamese text
            metadata_payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            metadata_items = metadata_payload.get("items", [])
            if not isinstance(metadata_items, list) or not metadata_items:
                self.last_trace["load_error"] = "empty_or_invalid_metadata_items"
                return False

            base_index = faiss.read_index(str(self.index_path))
            category_rows: dict[str, list[dict[str, object]]] = {}
            category_vectors: dict[str, list[np.ndarray]] = {}
            for row in metadata_items:
                item_id = int(row["id"])
                category = str(row["category"])
                vector = np.asarray(base_index.reconstruct(item_id), dtype=np.float32)
                category_rows.setdefault(category, []).append(row)
                category_vectors.setdefault(category, []).append(vector)
        except Exception as exc:  # noqa: BLE001
            self.last_trace["load_error"] = f"{type(exc).__name__}: {exc}"
            return False

        for category, vectors in category_vectors.items():
            matrix = np.vstack(vectors).astype(np.float32)
            faiss.normalize_L2(matrix)
            category_index = faiss.IndexFlatIP(matrix.shape[1])
            category_index.add(matrix)
            self._category_indexes[category] = category_index
            self._category_rows[category] = category_rows[category]

        self._loaded = True
        self.last_trace = {
            "path": "semantic_mapping",
            "status": "index_loaded",
            "index_path": str(self.index_path),
            "metadata_path": str(self.metadata_path),
            "metadata_items": len(metadata_items),
            "categories": {category: len(rows) for category, rows in self._category_rows.items()},
        }
        return True

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        if self.embedding_fn is not None:
            if np is None:
                raise RuntimeError("numpy is required for semantic tag mapping.")
            embeddings = self.embedding_fn(texts)
            matrix = np.asarray(embeddings, dtype=np.float32)
            if matrix.ndim != 2:
                raise RuntimeError("Custom embedding_fn must return a 2D array.")
            if faiss is None:
                raise RuntimeError("faiss is required for semantic tag mapping.")
            faiss.normalize_L2(matrix)
            return matrix

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for semantic tag mapping.")
        if faiss is None or np is None:
            raise RuntimeError("faiss and numpy are required for semantic tag mapping.")
        if OpenAI is None:
            raise RuntimeError("openai is required for semantic tag mapping.")
        if self._client is None:
            embedding_base_url = (
                os.getenv("OPENAI_EMBEDDINGS_BASE_URL")
                or os.getenv("OPENAI_EMBEDDING_BASE_URL")
                or os.getenv("BASE_URL")
                or "https://api.openai.com/v1"
            )
            self._client = OpenAI(api_key=api_key, base_url=embedding_base_url)
        response = self._client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        matrix = np.asarray([item.embedding for item in response.data], dtype=np.float32)
        faiss.normalize_L2(matrix)
        return matrix

    def _search_matches(
        self,
        *,
        embedding: np.ndarray,
        category: str,
    ) -> list[tuple[dict[str, object], float, str]]:
        candidates: list[tuple[dict[str, object], float, str]] = []
        query = np.asarray([embedding], dtype=np.float32)

        for candidate_category in self._candidate_categories(category):
            category_index = self._category_indexes.get(candidate_category)
            category_rows = self._category_rows.get(candidate_category)
            if category_index is None or not category_rows:
                continue
            scores, ids = category_index.search(query, min(self.top_k, len(category_rows)))
            for score, row_id in zip(scores[0], ids[0]):
                best_id = int(row_id)
                if best_id < 0:
                    continue
                candidates.append(
                    (
                        category_rows[best_id],
                        float(score),
                        candidate_category,
                    )
                )

        if not candidates:
            return []

        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[: self.top_k]

    @staticmethod
    def _candidate_categories(category: str) -> list[str]:
        if category == "ROOM_VIEW":
            return ["ROOM_VIEW", "REVIEW_TAG"]
        if category == "REVIEW_TAG":
            return ["REVIEW_TAG", "ROOM_VIEW"]
        return [category]

    @staticmethod
    def _fallback_result(items: list[SemanticPreferenceItem], reason: str) -> SemanticMappingResult:
        mapped_items = [
            MappedSemanticItem(
                text=item.text,
                target_field=item.target_field,
                category=item.category,
                matched_category=None,
                matched_tag=None,
                score=None,
                priority=item.priority,
            )
            for item in items
        ]
        return SemanticMappingResult(
            mapped_items=mapped_items,
        )


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
