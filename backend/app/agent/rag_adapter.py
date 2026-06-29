"""
RAG Adapter — bridge giữa LangGraph `rag_node` và `app/rag/rag_system.py`.

Vấn đề cần giải quyết:
  app/rag/ được build như một standalone module với relative imports
  (from utils.logger import ..., from modules.planner import ...).
  Không thể import trực tiếp từ app.agent.nodes vì sys.path không có app/rag/.

Giải pháp:
  Trước khi import rag_system, inject app/rag/ vào sys.path.
  Sau đó giữ singleton chatbot để tránh re-init (mỗi lần init = connect Qdrant + Neo4j).

Intent routing:
  RAG chỉ chạy cho intent liên quan đến Q&A / thông tin chi tiết.
  Hotel search / recommendation thuần tuý thì bỏ qua để tiết kiệm latency.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Intent routing ────────────────────────────────────────────────────────────
# Chỉ chạy RAG khi user hỏi thông tin / chính sách / đặc điểm đặc biệt.
# hotel_search / personalization không cần RAG (chỉ cần recommendation).
_RAG_INTENTS = frozenset({"information", "special_feature", "hotel_similar"})

# ── Lazy singleton ────────────────────────────────────────────────────────────
_rag_lock = threading.Lock()
_rag_chatbot: Any = None
_rag_init_failed = False


def _ensure_rag_path() -> None:
    """Thêm app/rag/ vào sys.path để RAG module resolve internal imports."""
    rag_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "rag")
    )
    if rag_dir not in sys.path:
        sys.path.insert(0, rag_dir)
        logger.debug("[rag_adapter] sys.path injected: %s", rag_dir)


def _get_rag_chatbot() -> Any:
    """Trả về singleton RAG chatbot, hoặc None nếu không khả dụng."""
    global _rag_chatbot, _rag_init_failed
    if _rag_init_failed:
        return None
    if _rag_chatbot is not None:
        return _rag_chatbot
    with _rag_lock:
        if _rag_chatbot is not None:
            return _rag_chatbot
        try:
            _ensure_rag_path()
            from rag_system import chatbot as RagChatbot  # noqa: PLC0415
            _rag_chatbot = RagChatbot()
            logger.info("[rag_adapter] RAG chatbot initialized.")
        except Exception as exc:  # noqa: BLE001
            _rag_init_failed = True
            logger.warning(
                "[rag_adapter] RAG chatbot init failed — rag_node sẽ trả empty. "
                "error=%s: %s",
                type(exc).__name__,
                exc,
            )
    return _rag_chatbot


# ── Result extraction ─────────────────────────────────────────────────────────

def _extract_confidence(aggregated: Any) -> float:
    """Trích xuất confidence từ aggregation result."""
    if not isinstance(aggregated, dict):
        return 0.5
    raw = aggregated.get("confidence_level") or aggregated.get("confidence")
    if raw is None:
        return 0.5
    try:
        return float(min(1.0, max(0.0, float(raw))))
    except (TypeError, ValueError):
        return 0.5


def _extract_rag_docs(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Gộp kết quả từ rag, graph, hotel_sql thành list source docs."""
    docs: list[dict[str, Any]] = []
    for source_key in ("rag", "graph", "hotel_sql"):
        source = result.get(source_key) or {}
        raw = source.get("results") or []
        if not isinstance(raw, list):
            continue
        for item in raw[:5]:
            if isinstance(item, dict):
                docs.append({"source": source_key, **item})
            elif isinstance(item, str):
                docs.append({"source": source_key, "content": item})
    return docs


# ── Public entry point ────────────────────────────────────────────────────────

def run_rag(
    *,
    query: str,
    intent: str,
    slots: dict[str, Any],
    chat_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Chạy RAG pipeline và trả về partial AgentState dict.

    Chỉ gọi RAG khi intent thuộc nhóm Q&A / đặc điểm / so sánh.
    Fallback an toàn: trả về dict rỗng nếu chatbot không khởi tạo được
    hoặc lỗi runtime.

    Returns:
        dict với keys: rag_docs, rag_answer, rag_confidence
    """
    _EMPTY = {"rag_docs": [], "rag_answer": "", "rag_confidence": 0.0}

    if not query:
        return _EMPTY

    # Bỏ qua RAG cho intent thuần recommendation
    if intent and intent not in _RAG_INTENTS:
        return _EMPTY

    chatbot = _get_rag_chatbot()
    if chatbot is None:
        return _EMPTY

    # Enrich query với destination nếu chưa có
    destination = (slots or {}).get("destination", "")
    if destination and destination.lower() not in query.lower():
        enriched_query = f"{query} tại {destination}"
    else:
        enriched_query = query

    try:
        result = chatbot.process(enriched_query, return_detailed=True)

        # process() trả string khi return_detailed=False (edge case)
        if isinstance(result, str):
            return {
                "rag_docs": [],
                "rag_answer": result,
                "rag_confidence": 0.5,
            }

        answer: str = result.get("response") or ""
        agg = result.get("aggregated_info") or {}
        confidence = _extract_confidence(agg)
        docs = _extract_rag_docs(result)

        return {
            "rag_docs": docs,
            "rag_answer": answer,
            "rag_confidence": confidence,
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[rag_adapter] RAG process failed — returning empty. error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return _EMPTY
