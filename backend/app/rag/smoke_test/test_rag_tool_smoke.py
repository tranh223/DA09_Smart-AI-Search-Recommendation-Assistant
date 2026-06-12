"""Basic smoke tests for tools.rag_tool.search_rag.

This does NOT require calling the LLM.
It validates:
- index artifacts exist
- search returns items with required keys
- basic top_k behavior

Run:
  cd smoke_test
  python test_rag_tool_smoke.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.rag_tool import search_rag


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    data_dir = Path(__file__).resolve().parents[1] / "data"

    required_files = [
        "faiss_hotels.index",
        "faiss_hotels_meta.json",
        "faiss_hotels_chunks.json",
        "faiss_hotels_config.json",
    ]

    missing = [f for f in required_files if not (data_dir / f).exists()]
    _assert(not missing, f"Missing FAISS artifacts: {missing}. Build index first.")

    # Basic retrieval
    res: List[Dict[str, Any]] = search_rag("wifi bữa sáng", top_k=5)

    _assert(isinstance(res, list), "search_rag should return a list")
    _assert(len(res) <= 5, "returned more than top_k")

    required_keys = {"score", "chunk_id", "section", "content", "metadata"}
    for i, item in enumerate(res[:5]):
        missing_keys = required_keys - set(item.keys())
        _assert(
            not missing_keys,
            f"Item {i} missing keys: {sorted(missing_keys)}; got keys={sorted(item.keys())}",
        )

    # Cold/cached behavior: second call should be fast (informational)
    res2 = search_rag("check in policy", top_k=3)
    _assert(isinstance(res2, list), "second call returned non-list")

    print("=" * 70)
    print("SMOKE TEST: rag_tool")
    print("=" * 70)
    print(f"Artifacts OK in: {data_dir}")
    print(f"Example result count: {len(res)}")
    print("✓ ALL TESTS PASSED")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

