#!/usr/bin/env python3
"""
RAG Pipeline - Environment Configuration Validator
Checks that all required .env variables are set correctly.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)


# Define required and optional variables
REQUIRED_VARS = {
    "OPENAI_API_KEY": "OpenAI API key",
    "GRAPH_DB_URL": "Neo4j database URL",
    "GRAPH_DB_USER": "Neo4j username",
    "GRAPH_DB_PASSWORD": "Neo4j password",
    "GRAPH_DB_DATABASE": "Neo4j database name",
}

OPTIONAL_VARS = {
    "LANGSMITH_API_KEY": "LangSmith API key (for tracing)",
    "MONGO_URI": "MongoDB connection string",
    "VECTOR_DB_URL": "Qdrant vector DB URL",
    "HOTEL_ASK_BASE_URL": "Hotel Ask API endpoint",
}

DEFAULT_VARS = {
    "LLM_MODEL": "gpt-4o-mini",
    "RAG_LLM_TEMPERATURE": "0.7",
    "RAG_LLM_MAX_TOKENS": "2000",
    "LLM_TIMEOUT_SECONDS": "30",
    "LOG_LEVEL": "INFO",
    "QDRANT_COLLECTION_NAME": "hotels",
    "HOTEL_ENTITY_VECTOR_MODEL": "BAAI/bge-m3",
    "API_HOST": "0.0.0.0",
    "API_PORT": "8000",
}


def validate_env():
    """Validate environment configuration."""
    
    print("\n" + "=" * 90)
    print("RAG PIPELINE - ENVIRONMENT CONFIGURATION VALIDATOR")
    print("=" * 90)
    
    print(f"\n.env file: {env_path}")
    print(f"File exists: {env_path.exists()}")
    
    if not env_path.exists():
        print("\n[ERROR] .env file not found!")
        print("Create it with: cp .env.example .env")
        return False
    
    # Check required variables
    print("\n" + "-" * 90)
    print("REQUIRED VARIABLES")
    print("-" * 90)
    
    missing_required = []
    for var, description in REQUIRED_VARS.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "PASSWORD" in var or "KEY" in var or "TOKEN" in var:
                display_value = value[:10] + "***" if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"[OK] {var}: {display_value}")
        else:
            print(f"[ERROR] {var}: NOT SET - {description}")
            missing_required.append(var)
    
    # Check optional variables
    print("\n" + "-" * 90)
    print("OPTIONAL VARIABLES")
    print("-" * 90)
    
    for var, description in OPTIONAL_VARS.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "PASSWORD" in var or "KEY" in var or "TOKEN" in var or "URI" in var:
                display_value = value[:10] + "***" if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"[OK] {var}: {display_value}")
        else:
            print(f"[SKIP] {var}: Not set - {description}")
    
    # Check defaults
    print("\n" + "-" * 90)
    print("DEFAULT VARIABLES (using built-in if not set)")
    print("-" * 90)
    
    for var, default_val in DEFAULT_VARS.items():
        value = os.getenv(var, default_val)
        print(f"[OK] {var}: {value}")
    
    # Connection tests
    print("\n" + "-" * 90)
    print("CONNECTION TESTS")
    print("-" * 90)
    
    # Test Neo4j connection
    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import ServiceUnavailable
        
        db_url = os.getenv("GRAPH_DB_URL", "")
        db_user = os.getenv("GRAPH_DB_USER", "")
        db_pass = os.getenv("GRAPH_DB_PASSWORD", "")
        db_name = os.getenv("GRAPH_DB_DATABASE", "neo4j")
        
        if db_url and db_user and db_pass:
            try:
                # Convert http:// to bolt://
                bolt_url = db_url.replace("http://", "bolt://")
                driver = GraphDatabase.driver(bolt_url, auth=(db_user, db_pass), 
                                             encrypted=False)
                with driver.session(database=db_name) as session:
                    result = session.run("RETURN 1")
                    result.consume()
                driver.close()
                print("[OK] Neo4j connection successful")
            except ServiceUnavailable:
                print(f"[WARN] Neo4j at {db_url} is unreachable (server may be offline)")
            except Exception as exc:
                print(f"[WARN] Neo4j connection error: {exc}")
        else:
            print("[SKIP] Neo4j: Credentials not fully set")
    except ImportError:
        print("[SKIP] Neo4j: neo4j-driver not installed")
    except Exception as exc:
        print(f"[ERROR] Neo4j test failed: {exc}")
    
    # Test Qdrant connection
    try:
        from qdrant_client import QdrantClient
        
        qdrant_url = os.getenv("VECTOR_DB_URL", "localhost:6333")
        
        if "://" not in qdrant_url:
            qdrant_url = f"http://{qdrant_url}"
        
        try:
            client = QdrantClient(url=qdrant_url, timeout=3)
            collections = client.get_collections()
            print(f"[OK] Qdrant connection successful ({len(collections.collections)} collections)")
        except Exception as exc:
            print(f"[WARN] Qdrant at {qdrant_url} is unreachable: {exc}")
    except ImportError:
        print("[SKIP] Qdrant: qdrant-client not installed")
    except Exception as exc:
        print(f"[ERROR] Qdrant test failed: {exc}")
    
    # Summary
    print("\n" + "=" * 90)
    if missing_required:
        print(f"VALIDATION FAILED - {len(missing_required)} required variable(s) missing:")
        for var in missing_required:
            print(f"  - {var}")
        print("\nPlease set these variables in .env and try again.")
        return False
    else:
        print("VALIDATION SUCCESSFUL - All required variables are set!")
        print("\nYour RAG pipeline is ready to use.")
        return True


def create_env_template():
    """Create .env from .env.example if it doesn't exist."""
    
    env_path = Path(__file__).resolve().parent / ".env"
    example_path = Path(__file__).resolve().parent / ".env.example"
    
    if env_path.exists():
        return True
    
    if not example_path.exists():
        print("[ERROR] Neither .env nor .env.example found")
        return False
    
    print(f"\n[INFO] Creating .env from .env.example...")
    with open(example_path) as src:
        with open(env_path, 'w') as dst:
            dst.write(src.read())
    
    print(f"[OK] Created .env from template")
    return True


def main():
    # Create .env from template if needed
    if not create_env_template():
        return 1
    
    # Validate configuration
    if not validate_env():
        print("\n[NEXT STEPS]")
        print("1. Edit .env and fill in required values")
        print("2. Run this script again to verify")
        return 1
    
    print("\n[OK] Ready to use RAG pipeline!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
