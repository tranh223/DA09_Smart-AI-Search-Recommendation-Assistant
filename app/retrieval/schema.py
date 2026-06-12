"""Introspect schema graph + danh mục City/Tag để đưa vào prompt cho LLM.

Tự lấy schema từ Neo4j (ưu tiên APOC, fallback built-in) và kèm danh mục giá trị
thật của City/Tag, giúp LLM map đúng tên thành phố/tiện nghi người dùng diễn đạt.
"""

from __future__ import annotations

from app import config
from app.core.neo4j_client import run_cypher

_SCHEMA_CACHE: str | None = None


def get_schema(refresh: bool = False) -> str:
    """Lấy mô tả schema của graph để đưa vào prompt cho LLM (có cache)."""
    global _SCHEMA_CACHE

    if config.GRAPH_SCHEMA:
        return config.GRAPH_SCHEMA
    if _SCHEMA_CACHE is not None and not refresh:
        return _SCHEMA_CACHE

    schema_text = _schema_via_apoc()
    if schema_text is None:
        schema_text = _schema_via_builtin()

    # Kèm danh mục City thật để LLM map đúng tên thành phố (xử lý sai chính tả/dấu).
    city_catalog = _city_catalog()
    if city_catalog:
        schema_text = f"{schema_text}\n\n{city_catalog}"

    # Kèm danh mục giá trị Tag thật để LLM map đúng cách diễn đạt -> tên tag.
    tag_catalog = _tag_catalog()
    if tag_catalog:
        schema_text = f"{schema_text}\n\n{tag_catalog}"

    _SCHEMA_CACHE = schema_text
    return schema_text


def _city_catalog() -> str | None:
    """Liệt kê toàn bộ tên City thật trong DB (giúp map sai chính tả/dấu)."""
    try:
        rows = run_cypher(
            "MATCH (c:City) WHERE c.name IS NOT NULL RETURN DISTINCT c.name AS name"
        )
    except Exception:
        return None

    if not rows:
        return None

    names = ", ".join(sorted(r["name"] for r in rows))
    return (
        "Danh mục tên City có sẵn (PHẢI map tên thành phố người dùng gõ -> đúng tên "
        f"trong danh mục này, kể cả khi gõ sai dấu/chính tả):\n{names}"
    )


def _tag_catalog() -> str | None:
    """Liệt kê toàn bộ giá trị Tag thật trong DB, gom theo category."""
    try:
        rows = run_cypher(
            "MATCH (t:Tag) WHERE t.name IS NOT NULL "
            "RETURN t.category AS category, collect(DISTINCT t.name) AS names"
        )
    except Exception:
        return None

    if not rows:
        return None

    lines = ["Danh mục giá trị Tag có sẵn (PHẢI dùng đúng các giá trị này khi lọc theo Tag):"]
    for row in sorted(rows, key=lambda r: r.get("category") or ""):
        category = row.get("category") or "(không phân loại)"
        names = ", ".join(sorted(row.get("names", [])))
        lines.append(f"- {category}: {names}")
    return "\n".join(lines)


def _schema_via_apoc() -> str | None:
    """Thử lấy schema chi tiết qua APOC. Trả None nếu APOC không khả dụng."""
    try:
        rows = run_cypher("CALL apoc.meta.schema() YIELD value RETURN value")
    except Exception:
        return None

    if not rows:
        return None

    value = rows[0].get("value", {})
    lines: list[str] = []
    for name, info in value.items():
        if info.get("type") != "node":
            continue
        props = info.get("properties", {})
        prop_names = ", ".join(sorted(props.keys())) or "(không có property)"
        lines.append(f"(:{name}) properties: {prop_names}")

        rels = info.get("relationships", {})
        for rel_type, rel_info in rels.items():
            direction = rel_info.get("direction", "out")
            targets = ", ".join(rel_info.get("labels", [])) or "?"
            arrow = (
                f"(:{name})-[:{rel_type}]->(:{targets})"
                if direction == "out"
                else f"(:{name})<-[:{rel_type}]-(:{targets})"
            )
            lines.append(f"  {arrow}")

    return "\n".join(lines) if lines else None


def _schema_via_builtin() -> str:
    """Fallback: ghép schema từ các thủ tục built-in của Neo4j."""
    labels = [r["label"] for r in run_cypher("CALL db.labels() YIELD label RETURN label")]
    rel_types = [
        r["relationshipType"]
        for r in run_cypher(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        )
    ]
    prop_keys = [
        r["propertyKey"]
        for r in run_cypher("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey")
    ]

    return (
        "Node labels: " + ", ".join(labels) + "\n"
        "Relationship types: " + ", ".join(rel_types) + "\n"
        "Property keys: " + ", ".join(prop_keys)
    )
