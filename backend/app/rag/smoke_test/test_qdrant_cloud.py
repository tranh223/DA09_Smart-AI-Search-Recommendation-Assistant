#!/usr/bin/env python3
"""
Test Qdrant Cloud connection with API key
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)


def test_qdrant_cloud():
    """Test Qdrant Cloud connection."""
    
    print("\n" + "=" * 90)
    print("QDRANT CLOUD CONNECTION TEST")
    print("=" * 90)
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.exceptions import ResponseHandlingException
        
        vector_db_url = os.getenv("VECTOR_DB_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        
        print(f"\nConnecting to Qdrant Cloud:")
        print(f"  URL: {vector_db_url}")
        print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: NOT SET")
        
        if not vector_db_url or not api_key:
            print("\n[ERROR] VECTOR_DB_URL or QDRANT_API_KEY not set")
            return False
        
        # Connect with API key
        client = QdrantClient(
            url=vector_db_url,
            api_key=api_key,
            timeout=10
        )
        
        print("\n[OK] Connected to Qdrant Cloud!")
        
        # Get collections
        collections = client.get_collections()
        print(f"\n[OK] Collections available: {len(collections.collections)}")
        for col in collections.collections:
            print(f"     - {col.name}: {col.points_count} points, vectors_count: {col.vectors_count}")
        
        # Check for hotels collection
        hotel_collection = next(
            (c.name for c in collections.collections if "hotel" in c.name.lower()),
            None
        )
        
        if hotel_collection:
            print(f"\n[OK] Hotel collection found: {hotel_collection}")
            collection_info = client.get_collection(hotel_collection)
            print(f"     Points: {collection_info.points_count}")
            print(f"     Vector size: {collection_info.config.params.vectors.size}")
            print(f"     Distance: {collection_info.config.params.vectors.distance}")
        else:
            print("\n[WARN] No hotel collection found - may need to create and populate")
        
        print("\n" + "=" * 90)
        print("[SUCCESS] Qdrant Cloud is ready to use!")
        print("=" * 90)
        return True
        
    except Exception as exc:
        print(f"\n[ERROR] Connection failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 90)
    print("QDRANT CLOUD SETUP VERIFICATION")
    print("=" * 90)
    
    # Test connection
    if test_qdrant_cloud():
        print("""
        Next steps:
        
        1. Verify .env is configured:
           python validate_env.py
        
        2. Run full test suite:
           python component_test.py
        
        3. Start using the pipeline:
           python run.py
        """)
        return 0
    else:
        print("""
        Troubleshooting:
        
        1. Check VECTOR_DB_URL is correct
        2. Verify QDRANT_API_KEY is valid
        3. Ensure Qdrant Cloud cluster is running
        4. Check firewall/network access to Qdrant Cloud
        
        Configuration file: .env
        """)
        return 1


if __name__ == "__main__":
    sys.exit(main())
