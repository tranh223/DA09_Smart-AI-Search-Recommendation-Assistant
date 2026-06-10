"""
Retrieval Modules
Chỉ gọi tool, không cần code logic
"""
from utils.langsmith_tracer import tracer
from utils.logger import get_logger
from tools.rag_tool import search_rag
from tools.graph_tool import search_graph
from tools.user_profile_tool import search_user_profile

logger = get_logger(__name__)

@tracer.trace("retrieval_from_rag")
def retrieve_from_rag(query: str, top_k: int = 5) -> dict:
    """
    Tìm kiếm từ RAG Database.
    
    Args:
        query: Query để tìm kiếm
        top_k: Số kết quả trả về
    
    Returns:
        Dict chứa kết quả
    """
    logger.info(f"Retrieving from RAG for query: {query}")
    
    try:
        results = search_rag(query, top_k)
        logger.info(f"Retrieved {len(results)} items from RAG")
        return {
            "success": True,
            "source": "rag",
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error retrieving from RAG: {str(e)}")
        return {
            "success": False,
            "source": "rag",
            "results": [],
            "count": 0,
            "error": str(e)
        }

@tracer.trace("retrieval_from_graph")
def retrieve_from_graph(query: str, top_k: int = 5) -> dict:
    """
    Tìm kiếm từ Knowledge Graph.
    
    Args:
        query: Query để tìm kiếm
        top_k: Số kết quả trả về
    
    Returns:
        Dict chứa kết quả
    """
    logger.info(f"Retrieving from Graph for query: {query}")
    
    try:
        results = search_graph(query, top_k)
        logger.info(f"Retrieved {len(results)} items from Graph")
        return {
            "success": True,
            "source": "graph",
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error retrieving from Graph: {str(e)}")
        return {
            "success": False,
            "source": "graph",
            "results": [],
            "count": 0,
            "error": str(e)
        }

@tracer.trace("retrieval_from_user_profile")
def retrieve_from_user_profile(user_id: str, query: str) -> dict:
    """
    Tìm kiếm từ User Profile.
    
    Args:
        user_id: ID của user
        query: Query để tìm kiếm
    
    Returns:
        Dict chứa kết quả
    """
    logger.info(f"Retrieving from User Profile for user: {user_id}")
    
    try:
        results = search_user_profile(user_id, query)
        logger.info(f"Retrieved user profile information")
        return {
            "success": True,
            "source": "user_profile",
            "user_id": user_id,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error retrieving from User Profile: {str(e)}")
        return {
            "success": False,
            "source": "user_profile",
            "user_id": user_id,
            "results": {},
            "error": str(e)
        }
