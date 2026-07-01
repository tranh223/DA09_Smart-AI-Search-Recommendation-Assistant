# Tài liệu Module RAG — Smart AI Search & Recommendation Assistant

## 1. Tổng quan

Module RAG (Retrieval-Augmented Generation) của DA09 là hệ thống trả lời câu hỏi về khách sạn bằng cách kết hợp **truy xuất dữ liệu đa nguồn** và **sinh câu trả lời bằng LLM**.

Hệ thống được thiết kế theo kiến trúc **nhiều tầng (multi-layer)** với ba lớp LLM chính:

| Lớp | Module | Vai trò |
|-----|--------|---------|
| **Planner** | `modules/planner.py` | Phân tích query, xác định nguồn dữ liệu và kế hoạch xử lý |
| **Information Aggregation** | `modules/total_info.py` | Tổng hợp, lọc và rút gọn context từ các nguồn retrieval |
| **Generation** | `modules/generation.py` | Sinh câu trả lời cuối cùng gửi đến người dùng |

**Entry point:** `backend/app/rag/rag_system.py` — class `chatbot`, method `process()`.

**Tích hợp vào agent chính:** `backend/app/agent/rag_adapter.py` → `rag_node` trong LangGraph (`backend/app/agent/nodes.py`).

---

## 2. Kiến trúc hệ thống

### 2.1. Sơ đồ luồng xử lý

```text
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  INPUT LAYER                                            │
│  ├─ Structured input parser (rag_input.py)              │
│  ├─ Intent detection (3 loại)                           │
│  └─ Query enrichment với features                       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PLANNING LAYER                                         │
│  ├─ Planner (LLM) — phân tích query, chọn tool          │
│  ├─ Skill Agent — routing theo skill.md                 │
│  └─ Hotel Entity Resolver — chuẩn hóa tên → Hotel ID    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  RETRIEVAL LAYER                                        │
│  ├─ RAG Tool — Hotel Ask API (vector search)            │
│  └─ Graph Tool — Neo4j (quan hệ thực thể)               │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  AGGREGATION LAYER                                      │
│  └─ Information Aggregation (LLM) — lọc, gộp context    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  GENERATION LAYER                                       │
│  └─ Generation (LLM) — sinh câu trả lời cuối cùng       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Response → User
```

### 2.2. Thiết kế ban đầu vs hiện tại

| Giai đoạn | Công cụ (tools) |
|-----------|-----------------|
| **Ban đầu** | Vector DB, Graph DB, User Profile, Short-term Memory |
| **Hiện tại** | Vector DB (RAG), Graph DB, **Hotel Entity Resolver** |

Sau đánh giá tính thực tiễn, hệ thống **loại bỏ** User Profile và Short-term Memory khỏi pipeline RAG (profile được xử lý ở module Query Understanding riêng). Đồng thời **bổ sung Hotel Entity Resolver** để giải quyết hạn chế Planner không nhận diện chính xác tên khách sạn trong database.

---

## 3. Các lớp xử lý chính

### 3.1. Planner

**File:** `backend/app/rag/modules/planner.py`

Planner là thành phần đầu tiên trong pipeline. Nhiệm vụ:

- Phân tích truy vấn người dùng
- Xác định entity chính (`hotel_name`, `destination`, `main_object`)
- Quyết định nguồn dữ liệu cần dùng (`needs_rag`, `needs_graph`)
- Rewrite query thành câu truy vấn tối ưu cho RAG Tool
- Trả về plan dạng JSON có cấu trúc

Planner được hướng dẫn qua file **`skill.md`** — mô tả chi tiết chức năng từng tool, điều kiện sử dụng và hướng dẫn xử lý theo từng loại tác vụ. Cách tiếp cận này giúp cải thiện tool calling và giảm lựa chọn sai công cụ.

**Output mẫu:**

```json
{
  "query_type": "policy",
  "main_object": "check-in time",
  "hotel_name": "Pullman Hanoi",
  "destination": "Hà Nội",
  "needs_rag": true,
  "needs_graph": false,
  "tool_inputs": {
    "rag": {
      "query": "check-in time Pullman Hanoi",
      "top_k": 3,
      "hotel_ids": [12345],
      "sections": ["faq", "description"]
    }
  },
  "required_steps": ["Xác định khách sạn", "Truy xuất chính sách", "Tổng hợp và trả lời"]
}
```

**Lưu ý:** Khi nhận **structured input** từ agent chính (`rag_input.py`), hệ thống bỏ qua LLM Planner và dùng `build_structured_plan()` — routing deterministic theo `intent_type`.

### 3.2. Information Aggregation

**File:** `backend/app/rag/modules/total_info.py`

Lớp thứ hai, nhận toàn bộ kết quả từ RAG Tool và Graph Tool, sau đó:

1. Lọc thông tin không liên quan hoặc dư thừa
2. Loại trùng lặp giữa các nguồn
3. Gắn dữ liệu vào từng bước Planner đề xuất
4. Tạo context ngắn gọn nhưng đầy đủ cho Generation

**Mục tiêu:** Giảm context đầu vào cho Generation, hạn chế câu trả lời lan man và cải thiện tốc độ suy luận.

**Output cấu trúc:**

- Key Information
- Related Context
- Step Mapping
- Conflicts
- Confidence Level

**Tối ưu hóa tiềm năng:** Aggregation chỉ tổng hợp và rút gọn thông tin, không nhất thiết cần GPT-4o-mini. Có thể cân nhắc model xử lý context lớn với chi phí thấp hơn (Llama, DeepSeek) để giảm latency và chi phí vận hành.

### 3.3. Generation

**File:** `backend/app/rag/modules/generation.py`

Lớp cuối cùng, nhận:

- Query gốc (đã chuẩn hóa bởi Planner)
- Thông tin đã aggregation
- Conversation history (tùy chọn)

Sinh câu trả lời cuối cùng: rõ ràng, có trích dẫn nguồn, nêu hạn chế nếu có.

---

## 4. Công cụ truy xuất (Retrieval Tools)

### 4.1. RAG Tool — Vector Database

**File:** `backend/app/rag/tools/rag_tool.py`

| Thuộc tính | Giá trị |
|------------|---------|
| Nguồn dữ liệu | **Hotel Ask API** (nhóm DA10) |
| Vector store | Qdrant Cloud — collection `hotels` |
| Embedding model | BAAI/bge-m3 (768 chiều) |
| Distance metric | Cosine similarity |

Thay vì tự xây dựng hệ thống retrieval riêng, DA09 **tích hợp API Hotel Ask** do nhóm DA10 phát triển — tái sử dụng pipeline retrieval đã được tối ưu, tiết kiệm thời gian phát triển.

**Dùng khi query cần:**

- Mô tả khách sạn / phòng
- Chính sách (check-in/out, hủy phòng, thú cưng)
- Tiện ích, FAQ, hoạt động

**Sections hỗ trợ:** `description`, `overview`, `semantic_profile`, `faq`, `room_type`, `activities`

**Input / Output:**

```json
// Input
{ "query": "check-in time Pullman Hanoi", "hotel_ids": [12345], "top_k": 5 }

// Output (mỗi chunk)
{
  "score": 0.85,
  "chunk_id": "chunk_123",
  "section": "faq",
  "content": "Check-in từ 14:00...",
  "metadata": { "hotel_id": 12345, "hotel_name": "Pullman Hanoi" }
}
```

### 4.2. Graph Tool — Knowledge Graph

**File:** `backend/app/rag/tools/graph_tool.py`

| Thuộc tính | Giá trị |
|------------|---------|
| Database | Neo4j |
| Nodes | ~18.065 entities |
| Node types | Hotel, Room, Activity, City, Tag, Place, User, UserFeature |
| Relationships | LOCATED_IN, HAS_ROOM, OFFERS_ACTIVITY, NEAR, HAS_TAG, ... |

**Dùng khi query cần:**

- Quan hệ giữa nhiều thực thể (multi-hop reasoning)
- So sánh khách sạn qua mối liên kết
- Tìm chuỗi: Hotel → Area → Attraction → Preference

**Hạn chế hiện tại:** Context trả về còn lộn xộn, nhiều thông tin dư thừa, chưa phản ánh đầy đủ quan hệ quan trọng. Đây là thành phần còn nhiều tiềm năng cải thiện qua tối ưu Cypher query, chiến lược graph expansion, hoặc lọc context trước Aggregation.

### 4.3. Hotel Entity Resolver

**File:** `backend/app/rag/tools/hotel_entity_resolver.py`

Công cụ bổ sung để giải quyết bài toán **chuẩn hóa tên khách sạn → Hotel ID** trước khi retrieval.

**Chiến lược resolution:**

1. Chuẩn hóa text (bỏ dấu, lowercase, alias địa danh)
2. Vector search trên Qdrant (collection hotels)
3. Fuzzy reranking (rapidfuzz)

**Output mẫu:**

```json
{
  "status": "resolved",
  "hotel_id": 12345,
  "canonical_name": "Sofitel Legend Metropole Hanoi",
  "confidence": 0.98,
  "matched_alias": "Sofitel Hanoi"
}
```

**Confidence scoring:**

| Phương pháp | Confidence |
|-------------|------------|
| Exact match | 0.98 |
| Vector similarity | 0.75 – 0.95 |
| Fuzzy match | 0.55 – 0.90 |
| Ambiguous | 0.50 – 0.75 |

**Hướng tối ưu:** Có thể thay vector DB chuyên biệt bằng keyword search / fuzzy search thuần túy để giảm chi phí lưu trữ và đơn giản hóa kiến trúc.

---

## 5. Hướng dẫn chọn nguồn dữ liệu

```text
Query Type Analysis
├─ "Khách sạn nào có quan hệ / liên kết với ...?"
│  └─ → GRAPH DB
│
├─ "Chính sách / mô tả / tiện ích của khách sạn X?"
│  └─ → RAG (Vector / Hotel Ask)
│
└─ "So sánh nhiều khách sạn"
   └─ → RAG + GRAPH (kết hợp)
```

Khi query cần nhiều nguồn, Planner gọi đồng thời nhiều tool; Aggregation gộp kết quả trước khi Generation.

---

## 6. Intent và routing

### 6.1. Intent types (RAG module)

| Intent | Mô tả | RAG | Graph |
|--------|-------|-----|-------|
| `HOTEL_FEATURE_QA` | Hỏi tiện ích, đặc điểm | ✓ | ✗ |
| `HOTEL_POLICY_QA` | Hỏi chính sách | ✓ | ✗ |
| `HOTEL_COMPARISON_QA` | So sánh khách sạn | ✓ | ✓ |

Định nghĩa tại `backend/app/rag/rag_input.py` — `INTENT_ROUTES`.

### 6.2. Tích hợp với LangGraph agent

RAG chỉ kích hoạt khi intent thuộc nhóm Q&A / thông tin chi tiết:

| Intent (agent) | Kích hoạt RAG |
|----------------|---------------|
| `information` | ✓ |
| `special_feature` | ✓ |
| `hotel_similar` | ✓ |
| `hotel_search` | ✗ (chỉ recommendation) |
| `personalization` | ✗ |

Adapter: `backend/app/agent/rag_adapter.py` — inject `app/rag/` vào `sys.path`, dùng singleton chatbot để tránh re-init Qdrant/Neo4j mỗi request.

---

## 7. Cấu trúc thư mục

```text
backend/app/rag/
├── rag_system.py          # Entry point — class chatbot
├── rag_input.py           # Structured input contract
├── run.py                 # API wrapper + CLI
├── skill.md               # Tool responsibilities & benchmark
├── modules/
│   ├── planner.py         # Planner (LLM)
│   ├── total_info.py      # Information Aggregation (LLM)
│   ├── generation.py      # Generation (LLM)
│   ├── retrieval.py       # Gọi RAG + Graph tools
│   ├── skill_agent.py     # Intent routing
│   └── planner_intent_toolschema.py
├── tools/
│   ├── rag_tool.py        # Hotel Ask API
│   ├── graph_tool.py      # Neo4j
│   └── hotel_entity_resolver.py
├── scripts/
│   ├── build_qdrant_hotels_from_csv.py
│   └── hf_embedder.py
├── smoke_test/            # Benchmark & integration tests
└── data/
    └── hotels_rows.csv
```

---

## 8. Hiệu năng và benchmark

### 8.1. Latency pipeline đầy đủ (tracing)

Theo kết quả tracing hiện tại, thời gian xử lý **toàn pipeline RAG** dao động **20 – 27 giây**:

| Thành phần | Thời gian | Ghi chú |
|------------|-----------|---------|
| Information Aggregation | ~10 – 11s | Xử lý context lớn, gọi LLM |
| Generation | ~11 – 14s | Sinh câu trả lời từ aggregated context |
| Planner + Retrieval | ~3 – 5s | Phụ thuộc Hotel Ask / Neo4j latency |

### 8.2. Benchmark retrieval (smoke test)

Benchmark ngày 2026-06-24 — 8 test cases, **100% pass**:

| Loại query | Số case | Latency TB | Success rate |
|------------|---------|------------|--------------|
| Feature (tiện ích) | 3 | 877 ms | 100% |
| Policy (chính sách) | 3 | 522 ms | 100% |
| Comparison (so sánh) | 2 | 527 ms | 100% |
| **Tổng** | **8** | **656 ms** | **100%** |

Quality score trung bình: **0.72** (ngưỡng pass: > 0.5).

> Benchmark retrieval đo riêng lớp tool; latency pipeline đầy đủ (3 lớp LLM) cao hơn đáng kể.

### 8.3. Hạn chế hiện tại

- Câu trả lời đôi khi còn lan man dù Aggregation đã lọc context
- Rewrite query chưa tối ưu — chưa kết hợp trực tiếp Short-term Memory trong RAG
- Graph retrieval context còn nhiễu
- Chưa có đánh giá định lượng đầy đủ về độ chính xác end-to-end

---

## 9. Hướng phát triển

| Hạng mục | Định hướng |
|----------|------------|
| **Rewrite query** | Chuyển sang Intent Detection (Query Understanding) thay vì xử lý trong RAG — giảm số thao tác, cải thiện chất lượng truy vấn đầu vào |
| **Model per layer** | Dùng model rẻ hơn cho Aggregation, model mạnh hơn cho Generation — cân bằng chất lượng / tốc độ / chi phí |
| **Graph Tool** | Tối ưu Cypher query, graph expansion, lọc context trước Aggregation |
| **Hotel Entity Resolver** | Thử keyword / fuzzy search thay vector DB chuyên biệt |
| **Latency** | Cache entity resolution, giảm context truyền vào Aggregation và Generation |

---

## 10. Chạy thử nhanh

### 10.1. Standalone (CLI)

```powershell
cd backend
.venv\Scripts\activate
cd app/rag
python run.py
```

### 10.2. Qua API backend

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"test\",\"session_id\":\"s1\",\"query\":\"Giờ check-in của Pullman Hanoi là mấy giờ?\",\"user_profile\":{},\"slots\":{}}"
```

### 10.3. Build Qdrant (lần đầu)

```powershell
python backend/app/rag/scripts/build_qdrant_hotels_from_csv.py
```

Cần Docker container `da09-qdrant` đang chạy.

### 10.4. Smoke test

```powershell
cd backend/app/rag/smoke_test
python benchmark_rag_system_full.py
```

---

## 11. Tài liệu liên quan

| File | Nội dung |
|------|----------|
| `backend/app/rag/skill.md` | Tool contract, benchmark chi tiết, deployment guide |
| `INTENT.md` | Query Understanding v2 — intent, profile, router |
| `docs/module_log/log.md` | Logging, CSAT, RAGAS monitoring |
| `README.md` | Hướng dẫn cài đặt và chạy toàn dự án |
