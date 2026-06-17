"""Internal reranking pipeline.

Reranking is implemented by HuggingFace bge-reranker (e.g. BAAI/bge-reranker-base).
Used by modules/retrieval.py as a black-box reranker.

Contract:
- input: (query, candidates)
- output: reranked candidates (top_n)

For each candidate we only use its `content` field (fallback to json(metadata)).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import json


_MODEL_CACHE: dict[str, Tuple[Any, Any]] = {}


def _get_reranker_model(model_name: str = "BAAI/bge-reranker-base"):
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()

    _MODEL_CACHE[model_name] = (tokenizer, model)
    return tokenizer, model


def llm_rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = 3,
    model_name: str = "BAAI/bge-reranker-base",
) -> List[Dict[str, Any]]:
    """Rerank candidates with bge-reranker.

    Kept the function name as `llm_rerank` for backward compatibility with existing call sites.
    """

    if not candidates:
        return []

    tokenizer, model = _get_reranker_model(model_name)

    # Build (query, passage) pairs.
    pairs: List[tuple[str, str]] = []
    for it in candidates:
        passage = (it.get("content") or "").strip()
        if not passage:
            passage = json.dumps(it.get("metadata") or {}, ensure_ascii=False)
        pairs.append((query, passage[:800]))

    # Batch tokenize pairs.
    texts_a = [p[0] for p in pairs]
    texts_b = [p[1] for p in pairs]

    import torch

    with torch.no_grad():
        inputs = tokenizer(
            texts_a,
            texts_b,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        outputs = model(**inputs)
        logits = outputs.logits

        # logits can be [batch, 1] or [batch]
        scores = logits.squeeze(-1).detach().cpu().tolist()

    scored: List[tuple[int, float]] = list(enumerate(scores))
    scored.sort(key=lambda x: float(x[1]), reverse=True)

    k = max(int(top_n), 0)
    selected_indices = [idx for idx, _ in scored[:k]]

    return [candidates[i] for i in selected_indices]

