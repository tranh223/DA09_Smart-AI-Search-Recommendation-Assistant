#!/usr/bin/env python3
"""
RAG Pipeline Component Test - No LLM Required
Tests individual components without needing OpenAI API.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_input import parse_rag_request, build_structured_plan, build_retrieval_query
from tools.graph_tool import get_graph_config, run_cypher, search_graph
from tools.rag_tool import search_rag


def test_structured_input():
    """Test structured input parsing and planning."""
    print("\n" + "=" * 90)
    print("TEST 1: Structured Input & Planning")
    print("=" * 90)
    
    payload = {
        "intent_type": "HOTEL_FEATURE_QA",
        "source": "RAG_SERVICE",
        "parameters": {
            "query": "Does Hanoi Sofitel have a swimming pool?",
            "features": {
                "hotel_name": "Sofitel Legend Metropole Hanoi",
                "destination": "Hanoi",
                "amenities": ["pool"],
                "expectations": ["luxury_trip"],
            }
        }
    }
    
    try:
        request = parse_rag_request(payload)
        plan = build_structured_plan(request)
        retrieval_query = build_retrieval_query(request)
        
        print(f"\nRequest parsed: {request.intent_type}")
        print(f"Main object: {plan['main_object']}")
        print(f"Query type: {plan['query_type']}")
        print(f"Needs RAG: {plan['needs_rag']}")
        print(f"Needs Graph: {plan['needs_graph']}")
        print(f"RAG sections: {plan['rag_sections']}")
        print(f"\nRetrival query:\n{retrieval_query}")
        print("\n[OK] Structured input test passed")
        return True
    except Exception as exc:
        print(f"\n[FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_connection():
    """Test graph database connectivity."""
    print("\n" + "=" * 90)
    print("TEST 2: Graph Database Connection")
    print("=" * 90)
    
    try:
        config = get_graph_config()
        print(f"\nGraph config loaded:")
        print(f"  URL: {config['url']}")
        print(f"  User: {config['user']}")
        print(f"  Database: {config['database']}")
        
        # Test connection
        result = run_cypher("MATCH (n) RETURN count(n) AS count LIMIT 1")
        count = result[0]['count'] if result else 0
        print(f"  Node count: {count}")
        
        print("\n[OK] Graph connection test passed")
        return True
    except Exception as exc:
        print(f"\n[FAIL] {exc}")
        return False


def test_graph_search():
    """Test graph search."""
    print("\n" + "=" * 90)
    print("TEST 3: Graph Search")
    print("=" * 90)
    
    try:
        results = search_graph("luxury hotel", top_k=3)
        print(f"\nSearch for 'luxury hotel' returned {len(results)} results")
        
        if results:
            first = results[0]
            print(f"  Labels: {first.get('labels', [])}")
            print(f"  Relationships found: {len(first.get('relationships', []))}")
            print(f"  Properties count: {len(first.get('properties', {}))}")
        
        print("\n[OK] Graph search test passed")
        return True
    except Exception as exc:
        print(f"\n[FAIL] {exc}")
        return False


def test_rag_search():
    """Test RAG search."""
    print("\n" + "=" * 90)
    print("TEST 4: RAG Search (Hotel Ask)")
    print("=" * 90)
    
    try:
        results = search_rag("wifi breakfast amenities", top_k=5)
        print(f"\nSearch for 'wifi breakfast' returned {len(results)} chunks")
        
        if results:
            first = results[0]
            print(f"  First chunk score: {first.get('score')}")
            print(f"  Section: {first.get('section')}")
            print(f"  Has metadata: {'metadata' in first}")
        else:
            print("  [Note] No results - may need hotel IDs or API connectivity")
        
        print("\n[OK] RAG search test completed")
        return True
    except Exception as exc:
        print(f"\n[FAIL] {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 90)
    print("RAG PIPELINE - COMPONENT TEST SUITE")
    print("=" * 90)
    
    results = {
        "Structured Input": test_structured_input(),
        "Graph Connection": test_graph_connection(),
        "Graph Search": test_graph_search(),
        "RAG Search": test_rag_search(),
    }
    
    print("\n" + "=" * 90)
    print("TEST SUMMARY")
    print("=" * 90)
    
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
    
    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("\n" + "=" * 90)
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
