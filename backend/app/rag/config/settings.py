"""RAG module settings — all fields map 1-to-1 with .env variable names."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_BASE_URL: str = ""
    BASE_URL: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    RAG_LLM_TEMPERATURE: float = 0.7
    RAG_LLM_MAX_TOKENS: int = 2000
    RAG_LLM_TIMEOUT_SECONDS: int = 30

    # ── DA10 / Supabase OTA API ───────────────────────────────────────────────
    DA10_OTA_API_KEY: str = ""
    OTA_API_KEY: str = ""

    @property
    def ota_api_key(self) -> str:
        return self.DA10_OTA_API_KEY or self.OTA_API_KEY

    # ── LangSmith tracing ─────────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "DA09"
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── Neo4j HTTP API (port 7474) — used by RAG graph_tool ──────────────────
    GRAPH_DB_URL: str = "http://localhost:7474"

    # ── Neo4j credentials (NEO4J_* is the canonical name in .env) ────────────
    NEO4J_USER: str = ""
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = ""
    MONGO_TLS_ALLOW_INVALID: str = "false"

    # ── System ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
