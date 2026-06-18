"""
Generation Module
Tạo kết quả cuối cùng dựa trên thông tin tổng hợp
"""
from utils.llm_client import llm_client

from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

GENERATION_SYSTEM_PROMPT = """You are a smart AI assistant.
Based on the provided information, generate a response:
1. Clear and easy to understand
2. Cite the information sources when possible
3. Provide detailed explanations
4. Mention any uncertainties or limitations
5. Provide suggestions or next steps when appropriate
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
            system_prompt=GENERATION_SYSTEM_PROMPT,
        )
        logger.info("Response generation successful")
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return f"Xin lỗi, tôi gặp lỗi khi xử lý query của bạn: {str(e)}"
