import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_KEY_BACKUP: str = os.getenv("OPENAI_API_KEY_BACKUP", "")
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2000
    
    # LangSmith
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "rag_system")
    LANGSMITH_ENABLED: bool = True
    
    # Database
    VECTOR_DB_URL: str = os.getenv("VECTOR_DB_URL", "localhost:6333")
    GRAPH_DB_URL: str = os.getenv("GRAPH_DB_URL", "http://localhost:7687")
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    MONGO_TLS_ALLOW_INVALID: str = os.getenv("MONGO_TLS_ALLOW_INVALID", "false")
    
    # System
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
