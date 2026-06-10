"""
Generation Module
Tạo kết quả cuối cùng dựa trên thông tin tổng hợp
"""
from utils.llm_client import llm_client
from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

GENERATION_SYSTEM_PROMPT = """Bạn là một trợ lý AI thông minh.
Dựa trên thông tin được cung cấp, hãy tạo một phản hồi:
1. Rõ ràng và dễ hiểu
2. Trích dẫn nguồn thông tin
3. Cung cấp giải thích chi tiết
4. Đề cập đến bất kỳ sự không chắc chắn hay hạn chế nào
5. Cung cấp các đề xuất hoặc bước tiếp theo nếu thích hợp
"""

@tracer.trace("generate_response")
def generate_response(
    query: str,
    aggregated_info: str,
    conversation_history: list = None
) -> str:
    """
    Tạo phản hồi cuối cùng.
    
    Args:
        query: Query gốc từ người dùng
        aggregated_info: Thông tin tổng hợp
        conversation_history: Lịch sử cuộc trò chuyện (tùy chọn)
    
    Returns:
        Response text
    """
    logger.info(f"Generating response for query: {query}")
    
    # Chuẩn bị messages
    messages = []
    
    # Thêm conversation history nếu có
    if conversation_history:
        messages.extend(conversation_history)
    
    # Thêm query hiện tại
    messages.append({
        "role": "user",
        "content": f"""Query: {query}

Thông tin để trả lời:
{aggregated_info}

Vui lòng trả lời query dựa trên thông tin được cung cấp."""
    })
    
    try:
        response = llm_client.call(
            messages,
            system_prompt=GENERATION_SYSTEM_PROMPT
        )
        logger.info("Response generation successful")
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return f"Xin lỗi, tôi gặp lỗi khi xử lý query của bạn: {str(e)}"
