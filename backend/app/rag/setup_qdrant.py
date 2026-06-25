#!/usr/bin/env python3
"""
Qdrant Vector Store Setup & Connection Test
Sets up Qdrant connection and verifies hotel entity resolver.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel, ConfigDict


class QdrantConfig(BaseModel):
    """Qdrant configuration."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    host: str = "localhost"
    port: int = 6333
    url: str | None = None
    collection_name: str = "hotels"


class QdrantStore:
    """Qdrant vector store interface."""
    
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self.client = None
    
    def connect(self):
        """Connect to Qdrant server."""
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(url=self.url, timeout=5)
            # Test connection
            self.client.get_collections()
            return True
        except Exception as exc:
            print(f"Connection failed: {exc}")
            return False
    
    def is_running(self):
        """Check if Qdrant server is running."""
        return self.connect()
    
    def get_client(self):
        """Get the Qdrant client."""
        if self.client is None:
            self.connect()
        return self.client


def test_qdrant_connection():
    """Test Qdrant connection."""
    print("\n" + "=" * 90)
    print("QDRANT CONNECTION TEST")
    print("=" * 90)
    
    config = QdrantConfig()
    store = QdrantStore(host=config.host, port=config.port)
    
    print(f"\nAttempting connection to: {store.url}")
    
    try:
        if store.is_running():
            print(f"[OK] Connected to Qdrant at {store.url}")
            
            client = store.get_client()
            collections = client.get_collections()
            print(f"[OK] Collections available: {len(collections.collections)}")
            
            for col in collections.collections:
                print(f"     - {col.name}: {col.points_count} points")
            
            return True
        else:
            print(f"[FAIL] Cannot connect to Qdrant at {store.url}")
            print("\nTo start Qdrant:")
            print("  Option 1 (Docker):")
            print("    docker run -p 6333:6333 qdrant/qdrant")
            print("  Option 2 (Pre-built binary):")
            print("    Download from https://qdrant.tech/documentation/quick-start/")
            return False
    except Exception as exc:
        print(f"[FAIL] Error: {exc}")
        return False


def create_sample_hotels_collection():
    """Create a sample hotels collection if needed."""
    print("\n" + "=" * 90)
    print("SAMPLE HOTELS COLLECTION")
    print("=" * 90)
    
    store = QdrantStore()
    if not store.connect():
        print("[SKIP] Qdrant not running")
        return False
    
    try:
        client = store.get_client()
        collections = client.get_collections()
        
        collection_exists = any(c.name == "hotels" for c in collections.collections)
        if collection_exists:
            print("[OK] 'hotels' collection already exists")
            col = client.get_collection("hotels")
            print(f"     Points: {col.points_count}")
            return True
        else:
            print("[INFO] 'hotels' collection not found")
            print("       Create via embedding service or admin tools")
            return False
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return False


def test_embedder():
    """Test if embedder is available."""
    print("\n" + "=" * 90)
    print("EMBEDDER TEST")
    print("=" * 90)
    
    try:
        from app.recommendation.embedding.bge_embedder import get_embedder
        embedder = get_embedder()
        
        test_text = "Sofitel Legend Metropole Hanoi"
        vector = embedder.encode_one(test_text, is_query=True)
        
        print(f"[OK] Embedder working")
        print(f"     Text: {test_text}")
        print(f"     Vector dimension: {len(vector)}")
        print(f"     Vector sample: {vector[:5]}...")
        return True
    except ImportError as exc:
        print(f"[INFO] Embedder module not found: {exc}")
        print("       Will use local embedder if available")
        return False
    except Exception as exc:
        print(f"[FAIL] Embedder error: {exc}")
        return False


def test_hotel_resolver():
    """Test hotel entity resolver."""
    print("\n" + "=" * 90)
    print("HOTEL ENTITY RESOLVER TEST")
    print("=" * 90)
    
    try:
        from tools.hotel_entity_resolver import hotel_entity_resolver
        
        test_cases = [
            ("Sofitel Legend Metropole Hanoi", "Hanoi"),
            ("Vinpearl Resort Nha Trang", None),
            ("InterContinental Danang", "Da Nang"),
        ]
        
        print(f"\nTesting resolver with {len(test_cases)} queries:\n")
        
        for hotel_name, city in test_cases:
            print(f"  Query: {hotel_name}" + (f" ({city})" if city else ""))
            
            try:
                resolution = hotel_entity_resolver.resolve(
                    hotel_name,
                    candidates=[],
                    city=city,
                )
                
                print(f"    Status: {resolution.status}")
                if resolution.hotel_id:
                    print(f"    Resolved ID: {resolution.hotel_id}")
                    print(f"    Canonical name: {resolution.canonical_name}")
                    print(f"    Confidence: {resolution.confidence:.2%}")
                
                if resolution.candidates:
                    print(f"    Candidates: {len(resolution.candidates)}")
                print()
            except Exception as exc:
                print(f"    ERROR: {exc}\n")
        
        return True
    except Exception as exc:
        print(f"[FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 90)
    print("QDRANT SETUP & INTEGRATION TEST")
    print("=" * 90)
    
    results = {
        "Qdrant Connection": test_qdrant_connection(),
        "Hotels Collection": create_sample_hotels_collection(),
        "Embedder": test_embedder(),
        "Hotel Resolver": test_hotel_resolver(),
    }
    
    print("\n" + "=" * 90)
    print("RESULTS SUMMARY")
    print("=" * 90)
    
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[!!]"
        print(f"{status} {test_name}")
    
    print("\n" + "=" * 90)
    
    if not results.get("Qdrant Connection"):
        print("NEXT STEPS: Start Qdrant server")
        print("=" * 90)
        print("""
Run one of these commands:

  1. Docker (recommended):
     docker run -p 6333:6333 qdrant/qdrant

  2. Or download pre-built binary from:
     https://qdrant.tech/documentation/quick-start/

After starting Qdrant, run this script again.
        """)
    else:
        print("QDRANT READY FOR USE")
        print("=" * 90)
        print("""
Qdrant is connected and ready. The hotel entity resolver will use
vector search for hotel name resolution.

To use in pipeline:
  from tools.hotel_entity_resolver import hotel_entity_resolver
  resolution = hotel_entity_resolver.resolve("Hotel Name", city="City")
        """)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
