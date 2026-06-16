"""Retrieval layer for hotel vector, graph, and SQL sources."""

from __future__ import annotations

from typing import Any, Optional

from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from tools.rag_tool import search_rag
from tools.graph_tool import search_graph

logger = get_logger(__name__)


def _run_async(async_factory):
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_factory())
    raise RuntimeError("Async loop already running; call this retrieval from sync context only.")


@tracer.trace("resolve_hotel_entity")
def resolve_hotel_entity(hotel_name: str, city: Optional[str] = None) -> dict:
    """Resolve an imperfect hotel name once before multi-source retrieval."""

    try:
        async def _run():
            from config.settings import settings
            from tools.hotel_sql_tool import HotelSqlTool

            async with HotelSqlTool(api_key=settings.OTA_API_KEY) as tool:
                return await tool.resolve_hotel(hotel_name, city=city)

        resolution = _run_async(_run)
        return resolution.model_dump()
    except Exception as e:
        logger.error(f"Error resolving hotel entity: {str(e)}")
        return {
            "status": "error",
            "input_name": hotel_name,
            "input_city": city,
            "hotel_id": None,
            "canonical_name": None,
            "confidence": 0.0,
            "candidates": [],
            "error": str(e),
        }


@tracer.trace("retrieval_from_rag")
def retrieve_from_rag(
    query: str,
    top_k: int = 3,
    filters: Optional[dict[str, Any]] = None,
) -> dict:
    """Search from RAG vector DB."""
    logger.info(f"Retrieving from RAG for query: {query}")

    try:
        results = search_rag(query, top_k, filters=filters)
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
def retrieve_from_graph(
    query: str,
    top_k: int = 5,
    hotel_id: Optional[int] = None,
) -> dict:
    """Search from Neo4j knowledge graph."""
    logger.info(f"Retrieving from Graph for query: {query}")

    try:
        results = search_graph(query, top_k, hotel_id=hotel_id)
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
def retrieve_from_hotel_sql(
    query: str,
    need: Optional[list[str]] = None,
    *,
    hotel_id: Optional[int] = None,
    hotel_name: Optional[str] = None,
    city: Optional[str] = None,
) -> dict:
    """Retrieve raw hotel policies/activities from DA10 via tools.hotel_sql_tool."""
    logger.info(f"Retrieving from Hotel SQL for query: {query}")

    try:
        from modules.hotel_sql_utils import build_hotel_lookup_input_from_query

        need_list = need or ["detail", "policies", "activities"]
        if hotel_id is not None or hotel_name:
            from tools.hotel_sql_tool import HotelLookupInput

            payload = HotelLookupInput(
                hotel_id=hotel_id,
                hotel_name=hotel_name,
                city=city,
                need=need_list,
            )
        else:
            payload = build_hotel_lookup_input_from_query(query, need_list)

        async def _run():
            from config.settings import settings
            from tools.hotel_sql_tool import HotelSqlTool

            async with HotelSqlTool(api_key=settings.OTA_API_KEY) as tool:
                return await tool.lookup(payload)

        output = _run_async(_run)

        res = output.model_dump(exclude_none=True)
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

