"""
Total Info Aggregation Module
Tổng hợp thông tin từ các nguồn khác nhau
"""
from utils.llm_client import llm_client
from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

AGGREGATION_SYSTEM_PROMPT = """Bạn là một chuyên gia tổng hợp thông tin. Khi nhận được:
- Query gốc
- Context/phân tích từ Planner
- Các kết quả từ RAG, Graph, User Profile, Short-term Memory
hãy:
1. Đọc kỹ mục tiêu chính và các bước xử lý Planner đề xuất.
2. Lọc lại chỉ những thông tin quan trọng, phù hợp để giải quyết query.
3. Nối logic giữa các thông tin từ nhiều nguồn.
4. Đối chiếu các thông tin với các bước cần làm; nếu Planner đã phân rã task, hãy gắn kết dữ liệu vào từng bước phù hợp.
5. Loại bỏ dữ liệu trùng lặp và thông tin không liên quan.
6. Trả về kết quả tổng hợp rõ ràng, gồm:
   - Key Information
   - Related Context
   - Suggested Steps / Step Mapping
   - Conflicts
   - Confidence Level
"""

@tracer.trace("aggregate_information")
def aggregate_information(
    query: str,
    plan_result: dict = None,
    rag_results: dict = None,
    graph_results: dict = None,
    user_profile_results: dict = None,
    short_term_memory_results: dict = None
) -> dict:
    """
    Tổng hợp thông tin từ các nguồn khác nhau.
    
    Args:
        query: Query gốc
        rag_results: Kết quả từ RAG
        graph_results: Kết quả từ Graph
        user_profile_results: Kết quả từ User Profile
        short_term_memory_results: Kết quả từ Short-term Memory
    
    Returns:
        Dict chứa thông tin tổng hợp
    """
    logger.info("Aggregating information from all sources")
    
    # Chuẩn bị thông tin từ các nguồn
    sources_info = []
    
    if rag_results and rag_results.get("success"):
        sources_info.append(f"RAG: {rag_results.get('results', [])}")
    
    if graph_results and graph_results.get("success"):
        sources_info.append(f"Graph: {graph_results.get('results', [])}")
    
    if user_profile_results and user_profile_results.get("success"):
        sources_info.append(f"User Profile: {user_profile_results.get('results', {})}")
    
    if plan_result:
        sources_info.append(f"Planner Context: {plan_result.get('context', '')}")
        sources_info.append(f"Planner Required Steps: {plan_result.get('required_steps', [])}")
        sources_info.append(f"Planner Main Object: {plan_result.get('main_object', '')}")
        sources_info.append(f"Planner Sub Objects: {plan_result.get('sub_objects', [])}")
    
    if short_term_memory_results and short_term_memory_results.get("success"):
        sources_info.append(f"Short-term Memory: {short_term_memory_results.get('results', [])}")
    
    if not sources_info:
        logger.warning("No information from any source")
        return {
            "success": False,
            "aggregated_info": {},
            "error": "No information available from sources"
        }
    
    # Gọi LLM để tổng hợp
    aggregated_content = "\n".join(sources_info)
    
    messages = [
        {
            "role": "user",
            "content": f"""Query: {query}

Planner analysis:
{plan_result}

Thông tin từ các nguồn:
{aggregated_content}

Hãy thực hiện các bước sau:
1. Xác định thông tin quan trọng nhất liên quan đến query.
2. Đối chiếu các dữ liệu này với các bước Planner đề xuất.
3. Gắn kết dữ liệu vào từng bước khi có thể.
4. Nối logic giữa các nguồn và loại bỏ trùng lặp.
5. Trả về cấu trúc rõ ràng:
   - Key Information
   - Related Context
   - Step Mapping (liên kết với required_steps nếu có)
   - Conflicts
   - Confidence Level
"""
        }
    ]
    
    try:
        result = llm_client.call(
            messages,
            system_prompt=AGGREGATION_SYSTEM_PROMPT
        )
        logger.info("Information aggregation successful")
        return {
            "success": True,
            "aggregated_info": result,
            "sources_count": len(sources_info)
        }
    except Exception as e:
        logger.error(f"Error aggregating information: {str(e)}")
        return {
            "success": False,
            "aggregated_info": None,
            "error": str(e)
        }
