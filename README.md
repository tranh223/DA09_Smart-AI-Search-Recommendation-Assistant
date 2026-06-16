# DA09 Smart AI Search Recommendation Assistant

**Bùi Đức Tiến - Update v2**

DA09 Smart AI Search Recommendation Assistant là hệ thống RAG tập trung vào bài toán tìm kiếm, truy xuất và trả lời câu hỏi về khách sạn. Hệ thống kết hợp dữ liệu khách sạn có cấu trúc, tìm kiếm ngữ nghĩa bằng vector, quan hệ trong graph database và LLM generation để tạo câu trả lời có căn cứ.

## Tổng Quan Dự Án

Mục tiêu chính của dự án là hỗ trợ recommendation và QA cho domain khách sạn. Pipeline được thiết kế để truy xuất thông tin phù hợp nhất dựa trên ý định người dùng, điểm đến, tên khách sạn, tiện ích, chính sách và kỳ vọng chuyến đi.

RAG layer hiện tập trung vào:

- Hiểu intent và phân tích query.
- Truy xuất dữ liệu từ nhiều nguồn.
- Hybrid search trên dữ liệu khách sạn.
- Tổng hợp context.
- Sinh câu trả lời cuối cùng.
- Hỗ trợ recommendation và so sánh khách sạn.

## Nguồn Dữ Liệu

Hệ thống sử dụng nhiều nguồn dữ liệu bổ trợ lẫn nhau:

| Nguồn | Vai trò |
|---|---|
| PostgreSQL / Supabase API | Dữ liệu khách sạn có cấu trúc như detail, policy, activities, địa chỉ, rating và amenities. |
| Graph Database | Dữ liệu quan hệ như khách sạn, thành phố, phòng, vị trí và entity liên quan. |
| FAISS Vector Database | Truy xuất semantic từ các hotel chunks đã được enrich. |
| LLM Provider | Sinh câu trả lời, tổng hợp context và hỗ trợ legacy intent planning. |

> Lưu ý: user profile và short-term memory retrieval đã được loại khỏi active RAG pipeline. Các module logging nếu còn tồn tại không tham gia truy xuất evidence để trả lời khách sạn.

## Structured RAG Input

Update v2 bổ sung input schema có cấu trúc cho RAG pipeline:

```json
{
  "intent_type": "HOTEL_FEATURE_QA",
  "source": "RAG_SERVICE",
  "parameters": {
    "query": "InterContinental Đà Nẵng có phù hợp cho gia đình và có kids club không?",
    "features": {
      "hotel_name": "InterContinental Danang",
      "destination": "Da Nang",
      "amenities": ["kids_club"],
      "expectations": ["family_trip"]
    }
  }
}
```

Các intent được hỗ trợ:

- `HOTEL_FEATURE_QA`
- `HOTEL_POLICY_QA`
- `HOTEL_COMPARISON_QA`

## Điểm Mới Trong Update v2

### Structured Intent Routing

Pipeline dùng deterministic routing cho structured input, giúp giảm số lần gọi LLM planner không cần thiết.

| Intent | RAG Sections | Hotel SQL Needs | Graph |
|---|---|---|---|
| `HOTEL_FEATURE_QA` | `description`, `activities` | `detail`, `activities` | Tắt mặc định |
| `HOTEL_POLICY_QA` | `policy` | `policies` | Tắt |
| `HOTEL_COMPARISON_QA` | `description`, `policy`, `activities` | `detail`, `policies`, `activities` | Bật |

### Hotel Entity Resolution

Bổ sung cơ chế chuẩn hóa tên khách sạn để xử lý tên nhập không khớp tuyệt đối:

- Fuzzy matching theo tên khách sạn.
- Alias matching giữa tên tiếng Việt và tiếng Anh.
- Scoring có xét destination.
- Fallback bằng local metadata từ FAISS.
- Truyền canonical `hotel_id` xuyên suốt RAG, Hotel SQL và Graph retrieval.

### Multi-Source Retrieval Tối Ưu

Pipeline hiện phối hợp:

- FAISS semantic retrieval với metadata filters.
- Hotel SQL API retrieval theo đúng data needs.
- Graph retrieval có thể scope theo canonical hotel ID.

### Tối Ưu Token Và Latency

Các cập nhật gần đây giúp giảm context thừa và chi phí API:

- Structured input bỏ qua LLM planner.
- RAG retrieval lọc theo section.
- Hotel SQL chỉ fetch các phần dữ liệu được yêu cầu.
- Feature QA không đưa policy payload vào context.
- City input được normalize sang dạng tiếng Việt có dấu khi gọi DA10 API.

### Observability Và Benchmark

Dự án có:

- LangSmith tracing cho planner, retrieval, tools, aggregation và generation.
- Structured pipeline benchmark lưu kết quả tại:

```text
backend/app/rag/smoke_test/results
```

## Các Thành Phần Chính

| Module | Trách nhiệm |
|---|---|
| `backend/app/rag/rag_system.py` | RAG orchestrator chính. |
| `backend/app/rag/rag_input.py` | Structured input schema và deterministic routing. |
| `backend/app/rag/modules/retrieval.py` | Retrieval layer thống nhất. |
| `backend/app/rag/modules/total_info.py` | Tổng hợp context. |
| `backend/app/rag/modules/generation.py` | Sinh câu trả lời cuối cùng. |
| `backend/app/rag/tools/rag_tool.py` | FAISS vector search. |
| `backend/app/rag/tools/hotel_sql_tool.py` | Tích hợp DA10 Hotel API. |
| `backend/app/rag/tools/hotel_entity_resolver.py` | Chuẩn hóa tên khách sạn và resolve canonical ID. |
| `backend/app/rag/tools/graph_tool.py` | Neo4j graph search. |

## Chạy Benchmark Nhanh

Chạy benchmark cho structured pipeline:

```bash
cd backend/app/rag
python smoke_test/benchmark_structured_pipeline.py
```

Chạy một số lượng case nhỏ:

```bash
python smoke_test/benchmark_structured_pipeline.py --limit 3
```

Chạy một scenario cụ thể:

```bash
python smoke_test/benchmark_structured_pipeline.py --case FEATURE_FAMILY_KIDS
```

## Tài Liệu

Tài liệu kiến trúc đầy đủ nằm tại:

```text
architecture.md
```

Tài liệu này mô tả system overview, request flow, vai trò các data source, retrieval architecture, RAG pipeline, infrastructure assumptions, monitoring, security và Mermaid diagrams.
