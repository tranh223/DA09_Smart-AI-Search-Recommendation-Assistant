"""Cấu hình tập trung — đọc từ biến môi trường (.env).

Mọi hằng số cấu hình của ứng dụng nằm ở đây để các tầng khác import dùng chung.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# --- Neo4j ---------------------------------------------------------------- #
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Cấu hình driver chống kết nối "chết" (server đóng kết nối idle).
NEO4J_MAX_CONNECTION_LIFETIME = 300
NEO4J_LIVENESS_CHECK_TIMEOUT = 30
NEO4J_CONNECTION_ACQUISITION_TIMEOUT = 60

# --- OpenAI --------------------------------------------------------------- #
# OPENAI_API_KEY được SDK tự đọc từ môi trường.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# --- Schema --------------------------------------------------------------- #
# Đặt chuỗi mô tả schema để CỐ ĐỊNH thay vì introspect tự động (None = tự lấy).
GRAPH_SCHEMA: str | None = None

# --- Gợi ý ---------------------------------------------------------------- #
# Số khách sạn ứng viên đưa cho LLM cân nhắc khi gợi ý.
CANDIDATE_LIMIT = 25
