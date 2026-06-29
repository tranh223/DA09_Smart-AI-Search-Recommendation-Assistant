"""
TraceStore — lưu và truy vấn request traces vào MongoDB collection `trace_runs`.

Schema một document trace_runs:
  {
    "request_id": str,          # unique key
    "user_id": str,
    "session_id": str,
    "query": str,
    "started_at": ISO8601 str,
    "total_ms": float,
    "intent": str,
    "n_recs": int,
    "needs_clarification": bool,
    "spans": [
      {
        "name": str,
        "elapsed_ms": float,
        "status": "ok"|"error"|"skip"|"warn",
        "error": str | null,
        "input": {...},    # state snapshot TRƯỚC khi node chạy
        "output": {...},   # output patch node TRẢ VỀ
        "context": {...},  # scalars + detail
        "sub_spans": [...]
      }
    ]
  }

Indexing:
  - request_id (unique)
  - user_id + started_at (query by user, time-sorted)
  - session_id + started_at (query by session)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_COLLECTION = "trace_runs"
_MAX_QUERY_LIMIT = 100
_TTL_SECONDS = int(60 * 60 * 24 * 7)  # 7 ngày


def _get_col():
    """Trả về pymongo collection, raise RuntimeError nếu MongoDB chưa sẵn sàng."""
    from app.db.mongo.mongo_client import get_collection  # noqa: PLC0415
    return get_collection(_COLLECTION)


def _ensure_indexes() -> None:
    """Tạo indexes một lần. Gọi tại startup (main.py lifespan)."""
    try:
        col = _get_col()
        col.create_index("request_id", unique=True, background=True)
        col.create_index(
            [("user_id", 1), ("started_at", -1)],
            background=True,
        )
        col.create_index(
            [("session_id", 1), ("started_at", -1)],
            background=True,
        )
        # TTL index — tự động xoá document sau 7 ngày
        col.create_index(
            "started_at",
            expireAfterSeconds=_TTL_SECONDS,
            background=True,
            sparse=True,
        )
        logger.info("[TraceStore] Indexes ensured on collection '%s'.", _COLLECTION)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] Index creation skipped: %s", exc)


def save_trace(doc: dict[str, Any]) -> None:
    """Persist trace document vào MongoDB (upsert by request_id).

    Fire-and-forget — caller không cần await kết quả.
    Lỗi được log warn, không raise ra ngoài.
    """
    try:
        col = _get_col()
        col.update_one(
            {"request_id": doc["request_id"]},
            {"$set": doc},
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] save_trace failed for request_id=%s: %s", doc.get("request_id"), exc)


def get_trace(request_id: str) -> dict[str, Any] | None:
    """Lấy trace document theo request_id."""
    try:
        col = _get_col()
        doc = col.find_one({"request_id": request_id}, {"_id": 0})
        return doc
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] get_trace failed request_id=%s: %s", request_id, exc)
        return None


def list_traces(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    intent: str | None = None,
    needs_clarification: bool | None = None,
) -> list[dict[str, Any]]:
    """Danh sách traces, mới nhất trước.

    Projection chỉ trả header (không bao gồm spans để response nhẹ).
    """
    limit = min(max(limit, 1), _MAX_QUERY_LIMIT)
    query: dict[str, Any] = {}
    if user_id:
        query["user_id"] = user_id
    if session_id:
        query["session_id"] = session_id
    if intent:
        query["intent"] = intent
    if needs_clarification is not None:
        query["needs_clarification"] = needs_clarification

    projection = {
        "_id": 0,
        "request_id": 1,
        "user_id": 1,
        "session_id": 1,
        "query": 1,
        "started_at": 1,
        "total_ms": 1,
        "intent": 1,
        "n_recs": 1,
        "needs_clarification": 1,
        # Trả về latency per stage từ analytics span nếu có
        "spans.name": 1,
        "spans.elapsed_ms": 1,
        "spans.status": 1,
        "spans.error": 1,
    }
    try:
        col = _get_col()
        cursor = (
            col.find(query, projection)
            .sort("started_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return list(cursor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] list_traces failed: %s", exc)
        return []


def get_node_trace(request_id: str, node_name: str) -> dict[str, Any] | None:
    """Lấy span của một node cụ thể từ trace."""
    try:
        col = _get_col()
        doc = col.find_one({"request_id": request_id}, {"_id": 0, "spans": 1})
        if not doc:
            return None
        for span in doc.get("spans") or []:
            if span.get("name") == node_name:
                return span
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] get_node_trace failed: %s", exc)
        return None


def count_traces(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
) -> int:
    """Đếm số traces theo filter."""
    try:
        query: dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if session_id:
            query["session_id"] = session_id
        col = _get_col()
        return col.count_documents(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TraceStore] count_traces failed: %s", exc)
        return 0
