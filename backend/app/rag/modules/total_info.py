"""
Total Info Aggregation Module
Tổng hợp thông tin từ các nguồn khác nhau
"""

from utils.llm_client import llm_client
from utils.langsmith_tracer import tracer
from utils.logger import get_logger

logger = get_logger(__name__)

AGGREGATION_SYSTEM_PROMPT = """Bạn là chuyên gia tổng hợp thông tin. Khi nhận được:
- Query gốc
- Phân tích của Planner
- Kết quả từ RAG, Graph, và Short-term Memory
hãy:
1) Đọc mục tiêu chính và các bước xử lý do Planner đề xuất.
2) Lọc và chỉ giữ phần thông tin liên quan nhất để trả lời query.
3) Kết nối logic giữa các mảnh thông tin từ nhiều nguồn.
4) Đối chiếu dữ liệu với các bước bắt buộc trong Planner: gắn thông tin vào đúng từng bước.
5) Loại trùng và loại phần không liên quan.
6) Trả về đầu ra tổng hợp rõ ràng gồm:
   - Thông tin chính (Key Information)
   - Ngữ cảnh liên quan (Related Context)
   - Ánh xạ bước (Step Mapping)
   - Mâu thuẫn (Conflicts)
   - Mức độ tin cậy (Confidence Level)
"""


def _truncate_for_token_limit(text: str, max_chars: int = 8000) -> str:

    """Giới hạn đầu vào theo ký tự để tránh tràn token.

    Lưu ý: đây là ước lượng theo tokenizer phổ biến; mục tiêu là giữ ngữ cảnh
    quan trọng nhất ở đầu.
    """

    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[đã cắt nội dung để giới hạn token]"


@tracer.trace("aggregate_information")
def aggregate_information(
    query: str,
    plan_result: dict = None,
    rag_results: dict = None,
    graph_results: dict = None,
    user_profile_results: dict = None,
    short_term_memory_results: dict = None,
) -> dict:
    """Tổng hợp thông tin từ các nguồn khác nhau."""

    logger.info("Aggregating information from all sources")

    sources_info: list[str] = []

    # Chuẩn hóa đầu ra các nguồn về dạng text để LLM tổng hợp.
    if rag_results and rag_results.get("success"):
        sources_info.append(f"RAG: {rag_results.get('results', [])}")

    if graph_results and graph_results.get("success"):
        sources_info.append(f"Graph: {graph_results.get('results', [])}")

    if user_profile_results and user_profile_results.get("success"):
        sources_info.append(f"User Profile: {user_profile_results.get('results', {})}")

    if plan_result:
        sources_info.append(f"Planner Context: {plan_result.get('context', '')}")
        sources_info.append(
            f"Planner Required Steps: {plan_result.get('required_steps', [])}"
        )
        sources_info.append(f"Planner Main Object: {plan_result.get('main_object', '')}")
        sources_info.append(f"Planner Sub Objects: {plan_result.get('sub_objects', [])}")

    if short_term_memory_results and short_term_memory_results.get("success"):
        sources_info.append(
            f"Short-term Memory: {short_term_memory_results.get('results', [])}"
        )

    if not sources_info:
        logger.warning("No information from any source")
        return {
            "success": False,
            "aggregated_info": {},
            "error": "No information available from sources",
        }

    # Gọi LLM để tổng hợp (giới hạn ngữ cảnh để không tràn token ~6000).
    # 6000 token thường ~20-30k ký tự tiếng Việt/Anh tùy tokenizer, nên dùng ngưỡng an toàn.
    aggregated_content = "\n".join(sources_info)
    aggregated_content = _truncate_for_token_limit(aggregated_content, max_chars=6000)

    plan_result_str = ""
    try:
        plan_result_str = str(plan_result) if plan_result is not None else ""
    except Exception:
        plan_result_str = ""

    query_str = str(query) if query is not None else ""

    messages = [
        {
            "role": "user",
            "content": f"""Query: {query_str}

Planner analysis:
{plan_result_str}

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
   - Step Mapping
   - Conflicts
   - Confidence Level
""",
        }
    ]

    def _chunk_list(items: list[str], chunk_chars: int = 8000) -> list[list[str]]:
        chunks: list[list[str]] = []
        buf: list[str] = []
        cur = 0
        for s in items:
            if cur + len(s) > chunk_chars and buf:
                chunks.append(buf)
                buf = [s]
                cur = len(s)
            else:
                buf.append(s)
                cur += len(s)
        if buf:
            chunks.append(buf)
        return chunks

    chunks = _chunk_list(sources_info, chunk_chars=8000)

    # Gọi LLM nhiều lần theo từng cụm nguồn để hạn chế tràn token.
    partial_summaries: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_content = "\n".join(chunk)
        chunk_content = _truncate_for_token_limit(chunk_content, max_chars=24000)

        chunk_messages = [
            {
                "role": "user",
                "content": f"""Query: {query_str}

Planner analysis:
{plan_result_str}

Thông tin từ các nguồn (PHẦN {idx}/{len(chunks)}):
{chunk_content}

Nhiệm vụ:
- Tóm tắt phần thông tin quan trọng nhất từ cụm nguồn này liên quan đến query.
- Trích xuất theo khung:
  Key Information, Related Context, Step Mapping, Conflicts, Confidence Level
- Chỉ trả về tóm tắt cho cụm này.
""",
            }
        ]

        part = llm_client.call(chunk_messages, system_prompt=AGGREGATION_SYSTEM_PROMPT)
        partial_summaries.append(str(part))

    # Gom các tóm tắt từng cụm để ra kết quả cuối.
    final_compact = _truncate_for_token_limit("\n".join(partial_summaries), max_chars=24000)
    final_messages = [
        {
            "role": "user",
            "content": f"""Query: {query_str}

Planner analysis:
{plan_result_str}

Các tóm tắt từng phần:
{final_compact}

Hãy hợp nhất tất cả tóm tắt thành 1 đáp án tổng hợp cuối cùng.
Trả về đúng cấu trúc:
- Key Information
- Related Context
- Step Mapping
- Conflicts
- Confidence Level
""",
        }
    ]

    try:
        result = llm_client.call(final_messages, system_prompt=AGGREGATION_SYSTEM_PROMPT)
        logger.info("Information aggregation successful (multi-pass)")
        return {
            "success": True,
            "aggregated_info": result,
            "sources_count": len(sources_info),
            "pass_count": len(chunks) + 1,
        }
    except Exception as e:
        logger.error(f"Error aggregating information: {str(e)}")
        return {
            "success": False,
            "aggregated_info": None,
            "error": str(e),
        }


