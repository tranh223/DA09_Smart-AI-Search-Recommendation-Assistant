#!/usr/bin/env python3
"""
Full RAG Pipeline Test - End-to-End Execution
Tests the complete pipeline with a real query.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app.rag.rag_system import chatbot, get_chatbot


def test_pipeline():
    """Run full RAG pipeline with test queries."""
    
    print("=" * 90)
    print("RAG PIPELINE - END-TO-END TEST")
    print("=" * 90)

    # Initialize chatbot
    user_id = "test_user_001"
    bot = get_chatbot(user_id)
    
    test_queries = [
        "Tell me about Hanoi hotels with good reviews",
        "What are family-friendly accommodations in Da Nang?",
        "Compare luxury hotels in Ho Chi Minh City",
    ]

    print(f"\nInitialized chatbot for user: {user_id}\n")

    for i, query in enumerate(test_queries, 1):
        print("-" * 90)
        print(f"Query {i}: {query}")
        print("-" * 90)
        
        try:
            # Process with detailed output
            result = bot.process(query, return_detailed=True)
            
            # Extract key info
            response = result.get("response", "")
            plan = result.get("plan", {})
            rag_results = result.get("rag", {})
            graph_results = result.get("graph", {})
            error = result.get("error")
            
            if error:
                print(f"ERROR: {error}")
            else:
                print(f"\nResponse:\n{response[:300]}...\n" if len(response) > 300 else f"\nResponse:\n{response}\n")
                
                print(f"Plan type: {plan.get('query_type', 'N/A')}")
                print(f"Main object: {plan.get('main_object', 'N/A')}")
                print(f"Needs RAG: {plan.get('needs_rag')}")
                print(f"Needs Graph: {plan.get('needs_graph')}")
                
                rag_count = rag_results.get('count', 0) if rag_results.get('success') else 0
                graph_count = graph_results.get('count', 0) if graph_results.get('success') else 0
                
                print(f"\nRAG results: {rag_count} items")
                print(f"Graph results: {graph_count} items")
                
                if error:
                    print(f"Warning: {error}")
        
        except Exception as exc:
            print(f"EXCEPTION: {exc}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 90)
    print("PIPELINE TEST COMPLETE")
    print("=" * 90)
    
    return 0


if __name__ == "__main__":
    sys.exit(test_pipeline())
