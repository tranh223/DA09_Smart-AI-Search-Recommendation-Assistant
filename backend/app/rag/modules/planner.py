"""
Planner Module
Xác định các vị trí liên quan để query người dùng
"""
from utils.llm_client import llm_client

from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a smart Planner. When given a user query, do the following:
1. Analyze the query to understand the user's main needs.
2. Identify important entities, objects, factors, and components in the query.
3. If the query requires multiple processing steps, break the task into reasonable logical steps.
4. If the query missing informations not important like destination, amentities or expectation, you can simulations those informations
5. Clearly determine which information sources are needed to answer the question or complete the task:
   - RAG Hotel Ask (hotel-scoped vector search)
   - Knowledge Graph
   - User Profile
   - Short-term Memory
6. Rewrite the user's question into a concise Hotel Ask query for the RAG tool.
   - Keep the canonical hotel name or hotel_id clues when present.
   - Put the actual information need first, e.g. policy, breakfast, room, amenities.
Return the result as structured JSON with the following schema:
{
    "query_type": "string",
    "main_object": "string",
    "sub_objects": ["string"],
    "hotel_name": "string or null",
    "destination": "string or null",

    "entities_to_analyze": ["string"],

    "needs_rag": boolean,
    "needs_graph": boolean,
    "needs_user_profile": boolean,
    "needs_short_term_memory": boolean,

    "tool_inputs": {
        "rag": {"query": string, "top_k": number, "hotel_ids": number[], "sections": string[]},
        "graph": {"query": string, "top_k": number}
    },

    "required_steps": ["string"],
    "context": "string"
}

Notes:
- "main_object" is the main entity or the primary focus in the query.
- "sub_objects" are components, attributes, or secondary factors that must be considered.
- "hotel_name" is the hotel name mentioned in the query, or null if not mentioned.
- "destination" is the city/destination mentioned in the query, or null if not mentioned.
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
            "hotel_name": None,
            "destination": None,
            "needs_rag": True,
            "needs_graph": True,
            "needs_user_profile": True,
            "needs_short_term_memory": True,
            "tool_inputs": {"rag": {"query": query, "top_k": 3}, "graph": {"query": query, "top_k": 3}},
            "required_steps": [
                "Phân tích query",
                "Thu thập thông tin từ tất cả nguồn",
                "Tổng hợp và tạo phản hồi"
            ],
            "context": "Unable to parse plan, using default"
        }
