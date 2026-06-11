"""Tầng kết nối Neo4j: driver dùng chung + helper chạy Cypher read-only.

- run_cypher: trả records dạng list[dict].
- run_cypher_nodes: trả các node (nhãn + property) — giữ được label để phân loại.
Cả hai dùng managed transaction (execute_read) nên tự retry khi rớt kết nối.
"""

from __future__ import annotations

from neo4j import GraphDatabase
from neo4j.graph import Node

from app import config

_driver = None


def get_driver():
    """Khởi tạo (lazy) và tái sử dụng Neo4j driver."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            max_connection_lifetime=config.NEO4J_MAX_CONNECTION_LIFETIME,
            liveness_check_timeout=config.NEO4J_LIVENESS_CHECK_TIMEOUT,
            connection_acquisition_timeout=config.NEO4J_CONNECTION_ACQUISITION_TIMEOUT,
        )
    return _driver


def run_cypher(cypher: str, params: dict | None = None) -> list[dict]:
    """Chạy Cypher read-only, trả list[dict]."""
    driver = get_driver()
    with driver.session(default_access_mode="READ") as session:
        return session.execute_read(
            lambda tx: [record.data() for record in tx.run(cypher, params or {})]
        )


def run_cypher_nodes(cypher: str, params: dict | None = None) -> list[tuple[str, dict]]:
    """Chạy Cypher read-only, trả các node (nhãn + property); giữ thứ tự, loại trùng.

    Quét mọi giá trị trong từng record, lấy giá trị đầu tiên là Node. Nhờ giữ được
    nhãn (label) nên tầng trên biết đó là Hotel/Place/Room... để trả đúng thông tin.
    """
    def _tx(tx) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        seen: set = set()
        for record in tx.run(cypher, params or {}):
            node = next((v for v in record.values() if isinstance(v, Node)), None)
            if node is None or node.element_id in seen:
                continue
            seen.add(node.element_id)
            label = next(iter(node.labels), "Unknown")
            out.append((label, dict(node)))
        return out

    driver = get_driver()
    with driver.session(default_access_mode="READ") as session:
        return session.execute_read(_tx)


def close() -> None:
    """Đóng driver (gọi khi kết thúc ứng dụng)."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
