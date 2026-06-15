import os
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

try:
    _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    _driver.verify_connectivity()
    print("🚀 [Neo4j] Kết nối thành công!")
except ServiceUnavailable as e:
    print(f"❌ [Neo4j] Không thể kết nối: {e}")
    _driver = None


def get_driver():
    return _driver


def run_read_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Chạy Cypher READ-ONLY, trả về list[dict]."""
    if _driver is None:
        raise RuntimeError("Neo4j driver chưa được khởi tạo.")
    params = params or {}
    with _driver.session() as session:
        result = session.run(cypher, **params)
        return [record.data() for record in result]
