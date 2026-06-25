"""modules.retrieval

Retrieval layer: calls underlying tools.

User-profile retrieval has been DISABLED per request.

Notes
- Per request: only take top 3 from every retrieval tool.
- RAG retrieval is backed by Hotel Ask, not local FAISS.
"""

from __future__ import annotations

from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from tools.rag_tool import search_rag
from tools.graph_tool import search_graph


logger = get_logger(__name__)


@tracer.trace("retrieval_from_rag")
def retrieve_from_rag(
    query: str,
    top_k: int = 3,
    *,
    hotel_ids: list[int] | None = None,
    sections: list[str] | None = None,
) -> dict:
    """Search hotel evidence from Hotel Ask."""
    logger.info(f"Retrieving from RAG for query: {query}")

    try:
        candidates = search_rag(
            query,
            top_k * 4,
            hotel_ids=hotel_ids,
            sections=sections,
        )
        # rerank first, then take top 3
        from modules.retrieval_rerank_pipeline import llm_rerank
        results = llm_rerank(query, candidates, top_n=3)

        results = (results or [])[: max(int(top_k), 0)]
        logger.info(f"Retrieved {len(results)} items from RAG")
        return {
            "success": True,
            "source": "rag",
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Error retrieving from RAG: {str(e)}")
        return {
            "success": False,
            "source": "rag",
            "results": [],
            "count": 0,
            "error": str(e),
        }


@tracer.trace("retrieval_from_graph")
def retrieve_from_graph(query: str, top_k: int = 3) -> dict:
    """Search from Neo4j knowledge graph."""
    logger.info(f"Retrieving from Graph for query: {query}")

    try:
        results = search_graph(query, top_k)
        results = (results or [])[: max(int(top_k), 0)]
        logger.info(f"Retrieved {len(results)} items from Graph")
        return {
            "success": True,
            "source": "graph",
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Error retrieving from Graph: {str(e)}")
        return {
            "success": False,
            "source": "graph",
            "results": [],
            "count": 0,
            "error": str(e),
        }


# User profile retrieval removed entirely (Mongo disabled).
@tracer.trace("retrieval_from_user_profile")
def retrieve_from_user_profile(user_id: str, query: str) -> dict:
    """User profile retrieval disabled."""
    return {
        "success": False,
        "source": "user_profile",
        "user_id": user_id,
        "results": {},
        "error": "User profile retrieval disabled",
    }

