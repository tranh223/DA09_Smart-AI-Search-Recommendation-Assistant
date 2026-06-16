"""Neo4j driver with lazy init and retry for cloud / idle connection drops."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

load_dotenv()
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
MAX_RETRIES = int(os.getenv("NEO4J_MAX_RETRIES", "3"))

_driver = None


def _create_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_lifetime=1800,
        keep_alive=True,
        connection_timeout=30,
    )


def _reset_driver() -> None:
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:
            pass
    _driver = None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (ServiceUnavailable, SessionExpired, TransientError, OSError, ConnectionError)):
        return True
    message = str(exc).lower()
    return "defunct" in message or "connection" in message or "forcibly closed" in message


def get_driver():
    """Lazy-init driver so long startup (e.g. embedding model load) won't stale the pool."""
    global _driver
    if _driver is None:
        try:
            _driver = _create_driver()
            _driver.verify_connectivity()
            print("🚀 [Neo4j] Kết nối thành công!")
        except ServiceUnavailable as exc:
            print(f"❌ [Neo4j] Không thể kết nối: {exc}")
            _driver = None
    return _driver


def run_read_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Chạy Cypher READ-ONLY, trả về list[dict]. Tự retry khi connection bị đứt."""
    params = params or {}
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        driver = get_driver()
        if driver is None:
            raise RuntimeError("Neo4j driver chưa được khởi tạo.")

        try:
            with driver.session() as session:
                result = session.run(cypher, **params)
                return [record.data() for record in result]
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt >= MAX_RETRIES:
                raise
            logger.warning(
                "[Neo4j] Query failed (attempt %d/%d): %s — reconnecting...",
                attempt,
                MAX_RETRIES,
                exc,
            )
            _reset_driver()

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Neo4j query failed without exception.")
