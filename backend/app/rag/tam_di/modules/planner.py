"""
Planner Module
Xác định các vị trí liên quan để query người dùng
"""
from utils.llm_client import llm_client
from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """Bạn là một Planner thông minh. Khi nhận một query từ người dùng, hãy:
1. Phân tích query để hiểu nhu cầu chính của user.
2. Nhận diện các đối tượng, thực thể, yếu tố và thành phần quan trọng trong query.
3. Nếu query đòi hỏi nhiều bước xử lý, hãy phân rã task thành các bước logic hợp lý.
4. Xác định rõ những nguồn thông tin cần thiết để tìm câu trả lời hoặc hoàn thành task:
   - RAG Database (vector search)
   - Knowledge Graph
   - User Profile
   - Short-term Memory
5. Trả về kết quả dưới dạng JSON có cấu trúc:
{
    "query_type": "string",
    "main_object": "string",
    "sub_objects": ["string"],
    "needs_rag": boolean,
    "needs_graph": boolean,
    "needs_user_profile": boolean,
    "needs_short_term_memory": boolean,
    "required_steps": ["string"],
    "context": "string"
}

Ghi chú:
- "main_object" là thực thể chính hoặc đối tượng trọng tâm trong query.
- "sub_objects" là các thành phần, thuộc tính, hay các yếu tố phụ cần chú ý.
- "required_steps" là danh sách các bước xử lý cần thực hiện để đáp ứng query.
- Nếu không có sub_objects hoặc required_steps rõ ràng, trả về mảng rỗng.
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
            system_prompt=PLANNER_SYSTEM_PROMPT
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
            "needs_user_profile": True,
            "needs_short_term_memory": True,
            "required_steps": [
                "Phân tích query",
                "Thu thập thông tin từ tất cả nguồn",
                "Tổng hợp và tạo phản hồi"
            ],
            "context": "Unable to parse plan, using default"
        }
