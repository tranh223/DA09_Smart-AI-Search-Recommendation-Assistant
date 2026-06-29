"""RAG module settings — all fields map 1-to-1 with backend/.env variable names."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    BASE_URL: str = "https://api.openai.com/v1"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = ""
    DATABASE_NAME: str = "VinSmartFuture"
    MONGODB_USER_PROFILE_COLLECTION: str = "Users"
    MONGODB_BOOKINGS_COLLECTION: str = "Booking"
    MONGO_TLS_ALLOW_INVALID: str = "false"

    # ── Neo4j Bolt API (port 7687) ───────────────────────────────────────────
    NEO4J_URI: str = ""
    NEO4J_USER: str = ""
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MAX_RETRIES: int = 3

    # ── Neo4j HTTP API (port 7474) — used by RAG graph_tool ──────────────────
    GRAPH_DB_URL: str = "http://localhost:7474"
    GRAPH_DB_USER: str = ""
    GRAPH_DB_PASSWORD: str = ""
    GRAPH_DB_DATABASE: str = "neo4j"
    GRAPH_DB_MAX_RETRIES: int = 3

    # ── Kafka ─────────────────────────────────────────────────────────────────
    KAFKA_URL: str = ""

    # ── Hotel API ─────────────────────────────────────────────────────────────
    HOTEL_API_BASE_URL: str = "https://supabase-ota-travel.onrender.com"
    HOTEL_API_KEY: str = ""
    HOTEL_ASK_BASE_URL: str = ""
    DA10_SEARCH_API_BASE_URL: str = ""

    # ── OTA API ───────────────────────────────────────────────────────────────
    DA10_OTA_API_KEY: str = ""
    OTA_API_KEY: str = ""

    @property
    def ota_api_key(self) -> str:
        return self.DA10_OTA_API_KEY or self.OTA_API_KEY

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    POSTGRES_DSN: str = ""

    # ── LangSmith tracing ─────────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "DA09"
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── System & Environment ─────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    MOCK_MODE: bool = False
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "*"
    ENABLE_TEST_ENDPOINTS: bool = True

    # ── API Gateway ───────────────────────────────────────────────────────────
    CHAT_TIMEOUT_SECONDS: int = 120

    # ── LLM Runtime Controls ──────────────────────────────────────────────────
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2
    LLM_RETRY_DELAY_SECONDS: float = 1.0

    # ── Response Builder ──────────────────────────────────────────────────────
    RESPONSE_BUILDER_TIMEOUT_SECONDS: int = 25
    RESPONSE_BUILDER_MAX_RETRIES: int = 1

    # ── Memory Summarizer ─────────────────────────────────────────────────────
    SUMMARY_LLM_TEMPERATURE: float = 0.3
    SUMMARY_LLM_TIMEOUT_SECONDS: int = 30

    # ── RAG Generation ───────────────────────────────────────────────────────
    RAG_LLM_TEMPERATURE: float = 0.9
    RAG_LLM_MAX_TOKENS: int = 12000
    RAG_LLM_TIMEOUT_SECONDS: int = 30

    # ── Streaming ─────────────────────────────────────────────────────────────
    STREAM_WORD_DELAY_SECONDS: float = 0.018

    # ── Hidden Intent Extractor ──────────────────────────────────────────────
    HIDDEN_INTENT_ENABLED: bool = True
    HIDDEN_INTENT_MODEL: str = "gpt-5.4-mini"
    HIDDEN_INTENT_TEMPERATURE: float = 0.1
    HIDDEN_INTENT_MIN_CONFIDENCE: float = 0.65
    HIDDEN_INTENT_PROFILE_TOP_N: int = 5
    HIDDEN_INTENT_TIMEOUT_SECONDS: int = 15

    # ── Qdrant Vector Store ───────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_TAGS: str = "hotel_tags"
    QDRANT_COLLECTION_HOTELS: str = "hotels"
    QDRANT_TIMEOUT_SECONDS: int = 30
    QDRANT_BATCH_SIZE: int = 100

    # ── Embedding Model Configuration ─────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
