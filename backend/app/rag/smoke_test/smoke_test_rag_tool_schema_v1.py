"""Common schema + helpers for smoke tests & benchmarks of tools.rag_tool.

All rag_tool smoke/bench scripts should emit JSON in the same structure.

This file defines:
- RESULT ITEM schema (as a doc)
- utility: normalize result to canonical payload
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


REQUIRED_ITEM_KEYS = {
    "score",
    "chunk_id",
    "section",
    "content",
    "metadata",
}


def validate_items(items: List[Dict[str, Any]]) -> List[str]:
    """Return list of error strings."""
    errors: List[str] = []
    for i, it in enumerate(items):
        missing = sorted(REQUIRED_ITEM_KEYS - set(it.keys()))
        if missing:
            errors.append(f"item[{i}] missing keys: {missing}")
    return errors


def canonicalize_retrieval_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure each item has keys; missing keys become None."""
    out: List[Dict[str, Any]] = []
    for it in items:
        out.append(
            {
                "score": it.get("score"),
                "chunk_id": it.get("chunk_id"),
                "section": it.get("section"),
                "content": it.get("content"),
                "metadata": it.get("metadata"),
                **{k: v for k, v in it.items() if k not in REQUIRED_ITEM_KEYS},
            }
        )
    return out


def canonical_result_payload(
    *,
    run_id: str,
    query: str,
    top_k: int,
    duration_ms: Optional[float],
    items: List[Dict[str, Any]],
    status: str,
    error: Optional[str] = None,
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "query": query,
        "top_k": top_k,
        "duration_ms": duration_ms,
        "status": status,  # PASS/FAIL/ERROR
        "error": error,
        "notes": notes or {},
        "items": canonicalize_retrieval_items(items),
    }

