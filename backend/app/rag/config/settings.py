import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_KEY_BACKUP: str = os.getenv("OPENAI_API_KEY_BACKUP", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2000

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # DA10 / Supabase OTA API (hotel_sql_tool)
    OTA_API_KEY: str = os.getenv("DA10_OTA_API_KEY", os.getenv("OTA_API_KEY", ""))

    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.9"))
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "2000"))
    
    # LangSmith
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "rag_system")
    LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    LANGSMITH_ENDPOINT: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    LANGSMITH_ENABLED: bool = True
    
    # Database
    VECTOR_DB_URL: str = os.getenv("VECTOR_DB_URL", "localhost:6333")
    GRAPH_DB_URL: str = os.getenv("GRAPH_DB_URL", "http://34.158.39.31:7474")
    GRAPH_DB_USER: str = os.getenv("GRAPH_DB_USER", os.getenv("NEO4J_USER", ""))
    GRAPH_DB_PASSWORD: str = os.getenv("GRAPH_DB_PASSWORD", os.getenv("NEO4J_PASSWORD", ""))
    GRAPH_DB_DATABASE: str = os.getenv("GRAPH_DB_DATABASE", os.getenv("NEO4J_DATABASE", "neo4j"))
    DA10_OTA_API_KEY: str = os.getenv("DA10_OTA_API_KEY", "")

    # System
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
