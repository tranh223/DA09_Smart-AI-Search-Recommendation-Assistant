#!/usr/bin/env python3
"""
Qdrant In-Memory Setup - For Development/Testing
Creates an in-memory Qdrant instance without Docker.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def setup_qdrant_inmemory():
    """Setup in-memory Qdrant for development."""
    print("\n" + "=" * 90)
    print("QDRANT IN-MEMORY SETUP")
    print("=" * 90)
    
    print("\nInitializing in-memory Qdrant...")
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        # Create in-memory client (no server needed)
        client = QdrantClient(":memory:")
        print("[OK] In-memory Qdrant initialized")
        
        # Check if hotels collection exists
        try:
            collection = client.get_collection("hotels")
            print(f"[OK] 'hotels' collection exists with {collection.points_count} points")
        except:
            # Create hotels collection if it doesn't exist
            print("[INFO] Creating 'hotels' collection...")
            client.create_collection(
                collection_name="hotels",
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print("[OK] 'hotels' collection created (empty)")
        
        return client
    except Exception as exc:
        print(f"[FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return None


def test_hotel_resolver_with_inmemory():
    """Test hotel resolver with in-memory Qdrant."""
    print("\n" + "=" * 90)
    print("HOTEL ENTITY RESOLVER TEST (In-Memory)")
    print("=" * 90)
    
    try:
        # Import with fallback
        try:
            from app.recommendation.embedding.bge_embedder import get_embedder
            embedder = get_embedder()
            print("[OK] BGE embedder loaded")
        except:
            print("[INFO] Using numpy fallback for embeddings")
            import numpy as np
            # Mock embedder
            class MockEmbedder:
                def encode_one(self, text, is_query=False):
                    import hashlib
                    seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
                    np.random.seed(seed)
                    return np.random.rand(768).astype('float32').tolist()
            embedder = MockEmbedder()
        
        # Get in-memory Qdrant
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, Distance, VectorParams
        
        qdrant = QdrantClient(":memory:")
        qdrant.create_collection(
            collection_name="hotels",
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        
        # Add sample hotel data
        sample_hotels = [
            (1, "Sofitel Legend Metropole Hanoi", "Hanoi"),
            (2, "Vinpearl Resort Nha Trang", "Nha Trang"),
            (3, "InterContinental Danang Sun Peninsula Resort", "Da Nang"),
            (4, "Sheraton Hanoi Hotel", "Hanoi"),
            (5, "Pullman Hanoi", "Hanoi"),
        ]
        
        print(f"\n[OK] Loading {len(sample_hotels)} sample hotels into vector store...")
        
        points = []
        for hotel_id, hotel_name, city in sample_hotels:
            vector = embedder.encode_one(hotel_name, is_query=False)
            points.append(
                PointStruct(
                    id=hotel_id,
                    vector=vector,
                    payload={
                        "hotel_id": hotel_id,
                        "hotel_name": hotel_name,
                        "city_name": city,
                    }
                )
            )
        
        qdrant.upsert(collection_name="hotels", points=points)
        print(f"[OK] Added {len(points)} hotels to Qdrant")
        
        # Now test resolver
        print("\n[OK] Testing hotel resolution queries:\n")
        
        test_queries = [
            ("Sofitel Hanoi", "Hanoi"),
            ("Vinpearl Nha Trang", None),
            ("InterContinental Danang", "Da Nang"),
        ]
        
        for query, city in test_queries:
            query_vector = embedder.encode_one(query, is_query=True)
            
            # Search using query_points
            results = qdrant.query_points(
                collection_name="hotels",
                query=query_vector,
                limit=3
            )
            
            print(f"  Query: '{query}'" + (f" ({city})" if city else ""))
            if results and results.points:
                top = results.points[0]
                print(f"    Top match: {top.payload['hotel_name']}")
                print(f"    Score: {top.score:.3f}")
            print()
        
        return True
    except Exception as exc:
        print(f"[FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 90)
    print("QDRANT VECTOR STORE - SETUP FOR RAG PIPELINE")
    print("=" * 90)
    
    # Setup in-memory Qdrant
    qdrant = setup_qdrant_inmemory()
    
    if not qdrant:
        print("\n[ERROR] Failed to setup Qdrant")
        return 1
    
    # Test with sample data
    if not test_hotel_resolver_with_inmemory():
        print("\n[ERROR] Hotel resolver test failed")
        return 1
    
    print("\n" + "=" * 90)
    print("QDRANT READY FOR DEVELOPMENT")
    print("=" * 90)
    print("""
Current Setup: In-Memory Qdrant (development/testing)
- No server needed
- Data persists in process memory only
- Vector dimension: 768 (BGE embeddings)
- Distance metric: Cosine similarity

For production deployment:

1. Start Qdrant server with Docker:
   docker run -p 6333:6333 qdrant/qdrant

2. Or download pre-built binary:
   https://qdrant.tech/documentation/quick-start/

3. Load hotel data using embedding service:
   - Collection name: 'hotels'
   - Vectors: 768-dimensional BGE embeddings
   - Metric: Cosine distance
   - Schema: {hotel_id, hotel_name, city_name, ...}

4. The RAG pipeline will use Qdrant for:
   - Hotel entity resolution with vector search
   - Semantic similarity matching
   - Fast retrieval of top-k hotels by vector proximity
    """)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
