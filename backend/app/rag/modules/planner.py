"""
Planner Module
Xác định các vị trí liên quan để query người dùng
"""
import os
from utils.llm_client import llm_client

from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a smart Planner. When given a user query, do the following:
1. Analyze the query to understand the user’s main needs.
2. Identify important entities, objects, factors, and components in the query.
3. If the query requires multiple processing steps, break the task into reasonable logical steps.
4. Clearly determine which information sources are needed to answer the question or complete the task:
   - RAG Database (vector search)
   - Knowledge Graph
   - Hotel SQL (if policy/rules must be fetched precisely)
5. Return the result as structured JSON with the following schema:
{
    "query_type": "string",
    "main_object": "string",
    "sub_objects": ["string"],
    "needs_rag": boolean,
    "needs_graph": boolean,
    "needs_hotel_sql": boolean,

    "required_steps": ["string"],
    "context": "string"
}

Notes:
- "main_object" is the main entity or the primary focus in the query.
- "sub_objects" are components, attributes, or secondary factors that must be considered.
- "required_steps" is the list of processing steps needed to fulfill the query.
- If you cannot determine sub_objects or required_steps, return empty arrays.
"""

@tracer.trace("planner")
def plan(query: str) -> dict:
    """
    Lập kế hoạch cho query.
    
    Args:
        query: Query từ người dùng
    
    Returns:
        Dict chứa plan
    """
    logger.info(f"Planning for query: {query}")
    
    messages = [
        {
            "role": "user",
            "content": f"Query: {query}\n\nHãy phân tích query này và trả về plan dưới dạng JSON."
        }
    ]
    
    try:
        result = llm_client.call_with_structured_output(
            messages,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            provider=os.getenv("LLM_PROVIDER", "openai"),
        )
        logger.info(f"Plan created: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in planner: {str(e)}")
        # Default plan
        return {
            "query_type": "general",
            "main_object": "general request",
            "sub_objects": [],
            "needs_rag": True,
            "needs_graph": True,
            "needs_hotel_sql": True,
            "required_steps": [

                "Phân tích query",
                "Thu thập thông tin từ tất cả nguồn",
                "Tổng hợp và tạo phản hồi"
            ],
            "context": "Unable to parse plan, using default"
        }
