"""Tầng LLM: OpenAI client dùng chung."""

from __future__ import annotations

from openai import OpenAI

from app.config import OPENAI_MODEL

__all__ = ["get_openai", "OPENAI_MODEL"]

_client: OpenAI | None = None


def get_openai() -> OpenAI:
    """Khởi tạo (lazy) OpenAI client (đọc OPENAI_API_KEY từ môi trường)."""
    global _client
    if _client is None:
        _client = OpenAI()
    return _client
