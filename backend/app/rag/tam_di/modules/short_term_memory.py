"""
Short-term Memory Module
Tìm kiếm thông tin từ short-term memory qua tool
"""
from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from tools.short_term_memory_tool import search_short_term_memory

logger = get_logger(__name__)

@tracer.trace("short_term_memory_retrieval")
def retrieve_from_short_term_memory(query: str, context: str = None) -> dict:
    """
    Tìm kiếm thông tin từ short-term memory.
    
    Args:
        query: Query để tìm kiếm
        context: Additional context
    
    Returns:
        Dict chứa thông tin từ short-term memory
    """
    logger.info(f"Retrieving from short-term memory for query: {query}")
    
    try:
        # Gọi tool để tìm kiếm
        results = search_short_term_memory(query, context)
        logger.info(f"Retrieved {len(results)} items from short-term memory")
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error retrieving from short-term memory: {str(e)}")
        return {
            "success": False,
            "results": [],
            "count": 0,
            "error": str(e)
        }
