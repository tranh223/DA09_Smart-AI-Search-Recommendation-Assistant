# RAG System - Hệ thống RAG với Short-term Memory Layer

## Tổng quan

Hệ thống RAG (Retrieval-Augmented Generation) được xây dựng theo sơ đồ kiến trúc với các tính năng:

- **Planner**: Lập kế hoạch cho query
- **Short-term Memory**: Lớp mới để tìm kiếm thông tin từ bộ nhớ tạm thời
- **Multi-source Retrieval**: Tìm kiếm từ RAG, Knowledge Graph, User Profile
- **Information Aggregation**: Tổng hợp thông tin từ các nguồn
- **Generation**: Tạo phản hồi cuối cùng
- **LLM Integration**: Kết nối với OpenAI API (hỗ trợ nhiều API keys)
- **LangSmith Tracing**: Theo dõi toàn bộ pipeline

## Cấu trúc dự án

```
.
├── rag_system.py              # File chính (entry point)
├── api.py                     # API wrapper và CLI interactive
├── config/
│   ├── settings.py           # Cấu hình hệ thống
│   └── __init__.py
├── modules/
│   ├── planner.py            # Planner module
│   ├── short_term_memory.py  # Short-term memory retrieval
│   ├── retrieval.py          # RAG, Graph, User Profile retrieval
│   ├── total_info.py         # Information aggregation
│   ├── generation.py         # Response generation
│   └── __init__.py
├── tools/
│   ├── rag_tool.py           # RAG search tool (placeholder)
│   ├── graph_tool.py         # Graph search tool (placeholder)
│   ├── user_profile_tool.py  # User profile tool (placeholder)
│   ├── short_term_memory_tool.py  # Short-term memory tool (placeholder)
│   └── __init__.py
├── utils/
│   ├── logger.py             # Logging utility
│   ├── llm_client.py         # LLM client (OpenAI)
│   ├── langsmith_tracer.py   # LangSmith tracing
│   └── __init__.py
├── requirements.txt          # Dependencies
└── .env.example              # Environment variables template
```

## Thiết lập

### 1. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 2. Cấu hình environment

Tạo file `.env` từ `.env.example`:

```bash
cp .env.example .env
```

Điền các thông tin:

```env
# OpenAI API Keys (hỗ trợ nhiều API keys để failover)
OPENAI_API_KEY=sk-...
OPENAI_API_KEY_BACKUP=sk-...

# LangSmith Tracing
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=rag_system

# Logging
LOG_LEVEL=INFO
```

## Sử dụng

### 1. Sử dụng file chính (rag_system.py)

```python
from rag_system import RAGSystem

# Khởi tạo
rag_system = RAGSystem(user_id="user_123")

# Gọi đơn giản (chỉ nhận đầu vào, trả ra kết quả)
response = rag_system.chat("Hãy giúp tôi tìm hiểu về...")
print(response)
```

### 2. Sử dụng API wrapper (api.py)

```python
from api import RAGAPI

api = RAGAPI(user_id="user_123")

# Đặt câu hỏi
answer = api.ask("Hãy giúp tôi tìm hiểu về...")
print(answer)
```

### 3. CLI Interactive

```bash
python api.py
```

Sau đó nhập các query và nhận phản hồi.

### 4. Sử dụng với chi tiết (debugging)

```python
from rag_system import RAGSystem

rag_system = RAGSystem(user_id="user_123")

# Lấy chi tiết từng bước
detailed_result = rag_system.process(
    "Hãy giúp tôi tìm hiểu về...",
    return_detailed=True
)

print(f"Plan: {detailed_result['plan']}")
print(f"Short-term Memory: {detailed_result['short_term_memory']}")
print(f"RAG Results: {detailed_result['rag']}")
print(f"Graph Results: {detailed_result['graph']}")
print(f"User Profile: {detailed_result['user_profile']}")
print(f"Aggregated Info: {detailed_result['aggregated_info']}")
print(f"Final Response: {detailed_result['response']}")
```

## Kiến trúc Pipeline

### Flow chính:

1. **Query Input** → User query
2. **Planner** → Lên kế hoạch, xác định những source nào cần tìm kiếm
3. **Short-term Memory Layer** → Tìm kiếm thông tin từ bộ nhớ tạm (cuộc trò chuyện trước)
4. **Parallel Retrievals**:
   - Retrieval from RAG Database
   - Retrieval from Knowledge Graph
   - Retrieval from User Profile
5. **Aggregation** → Tổng hợp thông tin từ các source, loại bỏ trùng lặp
6. **Generation** → LLM tạo phản hồi dựa trên thông tin tổng hợp
7. **Output** → Trả về phản hồi cho user

### Lợi thế kiến trúc này:

- **Modular**: Dễ dàng thay thế từng module
- **Transparent**: Có thể debug từng bước
- **Efficient**: Parallel retrievals cùng lúc
- **Smart Planning**: Planner quyết định source cần tìm kiếm
- **Memory Integration**: Short-term memory giúp context awareness
- **Traceability**: LangSmith tracing cho toàn bộ pipeline

## Một số lưu ý quan trọng

### Tools (placeholder)

Các file tools hiện đang là placeholder:
- `tools/rag_tool.py` - Cần implement logic tìm kiếm từ vector database
- `tools/graph_tool.py` - Cần implement logic truy vấn Knowledge Graph
- `tools/user_profile_tool.py` - Cần implement logic tìm kiếm user profile
- `tools/short_term_memory_tool.py` - Cần implement logic lưu trữ conversation

### LLM Integration

Hệ thống hỗ trợ:
- Gọi LLM từ nhiều API keys (failover tự động)
- Prompt customization cho từng module
- Structured output từ LLM

### Monitoring & Tracing

- Tất cả module được decorated với `@tracer.trace()` cho LangSmith
- Logging chi tiết cho mỗi bước
- Dễ dàng debugging với `return_detailed=True`

## LangSmith Tracing

Tất cả các module được tự động trace bởi LangSmith:

```python
# Xem trace trên LangSmith dashboard
# URL: https://smith.langchain.com/projects/rag_system
```

Mỗi run sẽ được ghi lại với:
- Input query
- Module được gọi
- Output của mỗi module
- Latency
- Errors (nếu có)

## Mở rộng

### Thêm module mới

1. Tạo file mới trong `modules/`
2. Implement logic với decorator `@tracer.trace()`
3. Gọi từ `rag_system.py`

### Thay đổi prompt

Các prompt đã được định nghĩa trong mỗi module. Để thay đổi:
- Sửa `*_SYSTEM_PROMPT` trong module tương ứng

### Tích hợp database mới

Implement logic trong `tools/` files tương ứng

## Troubleshooting

### "No module named 'openai'"

```bash
pip install openai==1.3.0
```

### "OPENAI_API_KEY not found"

Kiểm tra file `.env` đã được tạo và có đúng API key

### LangSmith không hoạt động

Kiểm tra `LANGSMITH_API_KEY` trong `.env` và confirm `LANGSMITH_ENABLED=True`

## Examples

Xem file `examples/` để có các ví dụ chi tiết.

## License

MIT
