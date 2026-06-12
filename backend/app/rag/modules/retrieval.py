"""modules.retrieval

Retrieval layer: calls underlying tools.

User-profile retrieval has been DISABLED per request.
"""

from __future__ import annotations

from typing import Optional

from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from tools.rag_tool import search_rag
from tools.graph_tool import search_graph

logger = get_logger(__name__)


@tracer.trace("retrieval_from_rag")
def retrieve_from_rag(query: str, top_k: int = 3) -> dict:
    """Search from RAG vector DB."""
    logger.info(f"Retrieving from RAG for query: {query}")

    try:
        results = search_rag(query, top_k)
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
def retrieve_from_graph(query: str, top_k: int = 5) -> dict:
    """Search from Neo4j knowledge graph."""
    logger.info(f"Retrieving from Graph for query: {query}")

    try:
        results = search_graph(query, top_k)
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


@tracer.trace("retrieval_from_hotel_sql")
def retrieve_from_hotel_sql(query: str, need: Optional[list[str]] = None) -> dict:
    """Retrieve raw hotel policies/activities from DA10 via tools.hotel_sql_tool."""
    logger.info(f"Retrieving from Hotel SQL for query: {query}")

    try:
        from modules.hotel_sql_utils import build_hotel_lookup_input_from_query

        need_list = need or ["detail", "policies", "activities"]
        payload = build_hotel_lookup_input_from_query(query, need_list)

        import asyncio

        async def _run():
            from config.settings import settings
            from tools.hotel_sql_tool import HotelSqlTool

            async with HotelSqlTool(api_key=settings.OTA_API_KEY) as tool:
                return await tool.lookup(payload)

        output = None
        try:
            # Prefer running loop check (works when called from async context).
            loop = asyncio.get_running_loop()
            # If we're already in a running loop, run via create_task and wait.
            # But since this function is sync, we only support non-running loops here.
            _ = loop  # keep for clarity
        except RuntimeError:
            # No running loop: safe to use asyncio.run
            output = asyncio.run(_run())

        if output is None:
            raise RuntimeError(
                "Async loop already running; call retrieve_from_hotel_sql from sync context only."
            )

        res = output.model_dump()
        return {
            "success": True,
            "source": "hotel_sql",
            "results": res,
            "count": 1,
        }
    except Exception as e:
        logger.error(f"Error retrieving from Hotel SQL: {str(e)}")
        return {
            "success": False,
            "source": "hotel_sql",
            "results": None,
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

