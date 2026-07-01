# Tài Liệu Bàn Giao — Module Recommendation Pipeline

Tài liệu này mô tả **độc lập** luồng xử lý gợi ý khách sạn (Recommendation) trong dự án **Smart-AI-Search-Recommendation-Assistant**: từ đầu vào `RecommendInput` đến danh sách `MergedCandidate` trước khi chuyển sang module Rerank.

> **Phạm vi tài liệu:** Candidate Generation → Orchestrator → Merge.  
> Chi tiết xếp hạng lại (Rerank) xem tại [`rerank.md`](../rerank%20_pipeline/rerank.md).

---

## Mục Lục

1. [Tổng Quan](#1-tổng-quan)
2. [Vị Trí Trong Hệ Thống](#2-vị-trí-trong-hệ-thống)
3. [Đầu Vào — RecommendInput](#3-đầu-vào--recommendinput)
4. [Luồng Xử Lý Tổng Thể](#4-luồng-xử-lý-tổng-thể)
5. [Rewrite & Search Query Template](#5-rewrite--search-query-template)
6. [Orchestrator — Chọn Nguồn Candidate](#6-orchestrator--chọn-nguồn-candidate)
7. [Nguồn 1 — Template Search API](#7-nguồn-1--template-search-api)
8. [Nguồn 2 — Personalization (Neo4j)](#8-nguồn-2--personalization-neo4j)
9. [REC_MERGE — Gộp & Tính Điểm Sơ Bộ](#9-rec_merge--gộp--tính-điểm-sơ-bộ)
10. [Engine API](#10-engine-api)
11. [Cấu Trúc Thư Mục](#11-cấu-trúc-thư-mục)
12. [Cấu Hình Môi Trường](#12-cấu-hình-môi-trường)
13. [Tracing & Debug](#13-tracing--debug)
14. [Kiểm Thử](#14-kiểm-thử)
15. [Hạn Chế & Hướng Phát Triển](#15-hạn-chế--hướng-phát-triển)
16. [Tài Liệu Liên Quan](#16-tài-liệu-liên-quan)

---

## 1. Tổng Quan

Module Recommendation chịu trách nhiệm **sinh danh sách khách sạn ứng viên** phù hợp với nhu cầu người dùng, dựa trên:

- **Ngữ cảnh phiên** (`session_context`): điểm đến, ngày, ngân sách, số khách, v.v.
- **Profile dài hạn** (`profile`): sở thích, loại hình lưu trú, tiện ích, phong cách du lịch
- **Query gốc** và **search query template** đã được chuẩn hóa

Pipeline gồm ba giai đoạn chính:

```text
RecommendInput
      │
      ▼
┌─────────────────┐
│  ORCHESTRATOR   │  Quyết định nguồn nào cần chạy
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
TEMPLATE    PERSONALIZATION
SEARCH API  (Neo4j graph)
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│   REC_MERGE     │  Dedup theo hotel_id, tính pre_rank_score
└────────┬────────┘
         ▼
  MergedCandidate[]
         │
         ▼
    → Rerank (module riêng)
```

**Entry point:** `backend/app/recommendation/engine.py` — hàm `run_candidate_pipeline()`.

---

## 2. Vị Trí Trong Hệ Thống

### 2.1. LangGraph pipeline

Recommendation được kích hoạt trong graph OTA assistant:

```text
session → intent → slot_check
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
        clarify                  rewrite
        (thiếu slot)                  │
                                      ├──► rag (song song)
                                      └──► recommend
                                              │
                                              ▼
                                          rerank
                                              │
                                              ▼
                                    response_builder → ...
```

**File graph:** `backend/app/agent/graph.py`

- Sau `rewrite_node`, `rag_node` và `recommend_node` chạy **song song** (fan-out).
- `rerank_node` chờ **cả hai** hoàn thành (fan-in) rồi xếp hạng lại merged candidates.

### 2.2. Điều kiện kích hoạt

`recommend_node` chỉ chạy khi Query Understanding (QU) đã build `recommend_input` — tức router có `recommendation_plan` (task `HOTEL_SEARCH` hoặc `PERSONALIZATION`).

| Điều kiện | Kết quả |
|-----------|---------|
| Có `recommend_input` trong state | Chạy candidate pipeline |
| Không có plan / thiếu `destination` | Skip, trả `merged_candidates: []` |
| User guest/anonymous | Vẫn chạy Template Search API; tắt Personalization |

**Node:** `backend/app/agent/nodes.py` — `recommend_node()`, `_should_run_recommend()`.

### 2.3. Nguồn RecommendInput

`RecommendInput` được build sẵn tại `intent_node` qua QU adapter:

```text
QueryUnderstandingPipeline
    → RouterResult.recommendation_plan
    → qu_adapter.pipeline_result_to_state()
    → RecommendInput (profile + session_context + original_query)
```

Sau đó `rewrite_node` gắn thêm `search_query_template` vào `RecommendInput` trước khi `recommend_node` chạy.

**File:** `backend/app/agent/qu_adapter.py`, `backend/app/agent/nodes.py` — `rewrite_node()`.

---

## 3. Đầu Vào — RecommendInput

**Schema:** `backend/app/recommendation/models.py`

```python
class RecommendInput(BaseModel):
    user_id: str
    profile: Profile                    # long-term profile
    session_context: SessionContext     # destination, dates, budget, guests...
    original_query: str = ""
    search_query_template: str | None = None   # sinh bởi rewrite_node
    limit_per_source: int = 10          # top_k mỗi nguồn
```

### 3.1. SessionContext — trường quan trọng

| Trường | Vai trò |
|--------|---------|
| `destination` | **Bắt buộc** để bật mọi nguồn candidate |
| `check_in`, `check_out` | Đưa vào search query template |
| `session_price_range` | Ngân sách phiên (min/max VND) |
| `number_of_guests`, `has_children`, `has_pet` | Ngữ cảnh chuyến đi |
| `nearby_place` | Landmark / khu vực quan tâm |

### 3.2. Profile — trường quan trọng

| Trường | Vai trò |
|--------|---------|
| `traveler_type` | Phong cách du lịch (tag + interaction score) |
| `long_term_trip_types` | Loại chuyến đi (gia đình, công tác...) |
| `long_term_budget_levels` | Mức ngân sách ưu tiên |
| `long_term_hotel_types`, `long_term_room_views`, `long_term_amenities` | Sở thích lưu trú |
| `long_term_preference_habits` | Thói quen / đặc điểm ưu tiên |
| `long_term_negative_preferences` | Truyền sang Rerank (tránh loại KS/tiện ích) |

Các trường dạng `{tag_name: {count, last_interaction}}` được dùng để rank tag theo tần suất tương tác.

---

## 4. Luồng Xử Lý Tổng Thể

### 4.1. Các bước trong `run_candidate_pipeline()`

| Bước | Module | Mô tả |
|------|--------|-------|
| ① | `trace.py` | Log `RecommendInput` (nếu bật trace) |
| ② | `orchestrator.py` | Quyết định nguồn, chạy song song |
| ③ | `search_api.py` | Gọi External Search API (nếu bật) |
| ④ | `personalization.py` | Truy vấn Neo4j (nếu bật) |
| ⑤ | — | Gộp `list[CandidateHotel]` từ mọi nguồn |
| ⑥ | `merger.py` | Dedup, tính `pre_rank_score`, sort |

### 4.2. Output

```python
list[MergedCandidate]
```

Mỗi `MergedCandidate` chứa:

| Trường | Ý nghĩa |
|--------|---------|
| `hotel_id` | ID khách sạn (key dedup) |
| `sources` | Nguồn xuất hiện: `template_search_api`, `personalization` |
| `source_scores` | Điểm đã normalize theo từng nguồn (0–1) |
| `pre_rank_score` | Điểm sơ bộ trước Rerank |
| `matched_paths`, `reasons` | Explainability — path Neo4j, lý do match |
| `metadata` | `raw_hit`, `strategy`, `review_score`, v.v. |

---

## 5. Rewrite & Search Query Template

Trước khi gọi Template Search API, `rewrite_node` sinh **câu truy vấn mẫu tiếng Việt** từ profile + session context.

**File:** `backend/app/agent/nodes.py` — `build_search_query_template()`, `_build_search_query_text()`

**Logic:** `extract_slots(inp)` → ghép các câu mẫu có dữ liệu:

```text
Tôi sắp đi {destination} từ ngày {check_in} đến ngày {check_out}.
Tôi muốn khách sạn phù hợp cho {trip_type}.
Phong cách du lịch của tôi là {traveler_type}.
Tôi muốn phòng có giá khoảng {budget_min} đến {budget_max} mỗi đêm.
Tôi ưu tiên loại hình lưu trú như {hotel_types}.
Tôi muốn phòng có hướng nhìn như {room_views}.
Tôi muốn khách sạn có tiện ích như {amenities}.
Tôi muốn khách sạn có đặc điểm như {preference_habits}.
```

Phần thiếu dữ liệu được **bỏ qua** — template chỉ chứa thông tin đã có.

**Ví dụ output:**

```text
Tôi sắp đi Đà Nẵng từ ngày 2026-06-19 đến ngày 2026-06-23.
Tôi muốn khách sạn phù hợp cho gia đình.
Tôi muốn phòng có giá khoảng 2 triệu đến 2.5 triệu mỗi đêm.
```

Template được gán vào `RecommendInput.search_query_template` và dùng làm `query` khi gọi External Search API.

---

## 6. Orchestrator — Chọn Nguồn Candidate

**File:** `backend/app/recommendation/candidate_generation/orchestrator.py`

### 6.1. Quy tắc bật nguồn

| Nguồn | Điều kiện bật |
|-------|---------------|
| `template_search_api` | Có `session_context.destination` |
| `personalization` | Có `destination` **và** `user_id` không phải guest/anonymous |

Prefix guest bị loại: `guest_`, `anonymous_`, `anon_`.

### 6.2. Chế độ thực thi

| Chế độ | Hành vi |
|--------|---------|
| **Production** (mặc định) | `ThreadPoolExecutor` — chạy song song các nguồn đã bật |
| **Trace** (`RecommendTrace.enabled`) | Chạy tuần tự, log chi tiết từng nguồn |

Nếu không có nguồn nào bật → trả `[]`.

---

## 7. Nguồn 1 — Template Search API

**File:** `backend/app/recommendation/candidate_generation/hotel_search/search_api.py`

### 7.1. Mô tả

Gọi **External Hotel Search API** (semantic search) với query template đã build. Đây là nguồn chính cho task `HOTEL_SEARCH` — tìm khách sạn theo mô tả ngữ nghĩa tổng hợp từ profile.

### 7.2. Điều kiện skip

- Thiếu `destination` (city)
- Thiếu `search_query_template` (rewrite_node chưa sinh template)

### 7.3. Request / Response

**Endpoint mặc định:**

```text
HOTEL_SEARCH_API_URL=https://search-api-760679907616.asia-southeast1.run.app/search
```

**Payload:**

```json
{
  "query": "<search_query_template>",
  "filters": {},
  "top_k": 10
}
```

**Response:** Danh sách hotel hits → map sang `CandidateHotel`:

```python
CandidateHotel(
    hotel_id=12345,
    hotel_name="Vinpearl Resort & Spa",
    source="template_search_api",
    score=0.87,
    matched_paths=["Tag(Hồ bơi)", "Tag(Gia đình)"],
    reason="search_api match (0.870) | Đà Nẵng",
    metadata={
        "strategy": "external_search_api",
        "city": "Đà Nẵng",
        "tags": [...],
        "raw_hit": {...}    # dùng bởi Rerank để skip DB enrichment
    }
)
```

`raw_hit` giúp Rerank parse metadata mà không cần gọi thêm Postgres/Supabase.

### 7.4. Slots extraction

**File:** `backend/app/recommendation/candidate_generation/hotel_search/slots.py`

Hàm `extract_slots(inp)` chuyển `RecommendInput` → dict compact dùng cho template builder và debug trace.

---

## 8. Nguồn 2 — Personalization (Neo4j)

**File:** `backend/app/recommendation/candidate_generation/personalization/personalization.py`

### 8.1. Mô tả

Truy vấn **Knowledge Graph Neo4j** để gợi ý khách sạn cá nhân hóa theo lịch sử và sở thích user. Nguồn này map với task `PERSONALIZATION` trong QU router.

### 8.2. Chiến lược hai tầng (tự chọn)

```text
Kiểm tra booking_count của user
        │
        ├─ booking_count >= 1  →  COLLABORATIVE FILTERING
        │
        └─ booking_count < 1   →  DEMOGRAPHIC FALLBACK
```

#### Tầng 1 — Collaborative Filtering

**Luồng:**

```text
User → shared BOOKED hotels → similar users
     → hotel similar users đã đặt (lọc city, loại hotel user đã biết)
     → boost interest fit (INTERESTED_IN × HAS_TAG)
```

**Công thức điểm:**

```text
userSimilarity = 0.65 × bookingOverlap + 0.35 × featureJaccard
finalScore     = 0.70 × collaborativeScore + 0.20 × interestFit + 0.10 × reviewScore
```

#### Tầng 2 — Demographic Fallback

Dùng khi user chưa có booking hoặc ít dữ liệu:

```text
User → shared UserFeature → similar segment users
     → hotel họ đã đặt trong city
     → boost interest fit
```

**Công thức điểm:**

```text
finalScore = 0.60 × demographicScore + 0.30 × interestFit + 0.10 × reviewScore
```

### 8.3. Graph schema liên quan

| Node / Edge | Vai trò |
|-------------|---------|
| `User`, `Hotel`, `Tag`, `UserFeature` | Thực thể chính |
| `BOOKED` | Lịch sử đặt phòng |
| `INTERESTED_IN` | Sở thích user (có time-decay) |
| `HAS_TAG` | Tag khách sạn |
| `HAS_FEATURES` | Phân khúc user |

### 8.4. Output mẫu

```python
CandidateHotel(
    hotel_id=67890,
    hotel_name="Melia Danang",
    source="personalization",
    score=0.72,
    matched_paths=["Tag(view biển)", "Tag(spa)"],
    reason="Khớp collaborative + interest",
    metadata={
        "strategy": "collaborative",       # hoặc "demographic_fallback"
        "collaborative_score": 0.45,
        "interest_fit": 0.31,
        "similar_user_count": 3,
        "review_score": 8.5,
    }
)
```

---

## 9. REC_MERGE — Gộp & Tính Điểm Sơ Bộ

**File:** `backend/app/recommendation/merge/merger.py`

### 9.1. Nguyên tắc

1. **Dedup theo `hotel_id`** — gộp sources, paths, reasons
2. **Min-max normalize** score theo từng nguồn (0→1) để so sánh công bằng
3. **Weighted sum** theo trọng số nguồn
4. **Bonus đa nguồn** — hotel xuất hiện ở nhiều nguồn được cộng điểm
5. Sort giảm dần theo `pre_rank_score`

### 9.2. Trọng số mặc định

| Nguồn | Trọng số |
|-------|----------|
| `personalization` | 0.50 |
| `template_search_api` | 0.50 |

| Bonus | Giá trị |
|-------|---------|
| Xuất hiện ở 2 nguồn | +0.10 |
| Trùng cả personalization **và** template_search_api | +0.20 (overlap boost) |

### 9.3. Công thức pre_rank_score

```text
weighted_sum = Σ (source_scores[src] × SOURCE_WEIGHTS[src])
bonus        = MULTI_SOURCE_BONUS[n_sources]     # 2 nguồn → +0.10
overlap      = +0.20 nếu có cả personalization và template_search_api

pre_rank_score = min(weighted_sum + bonus + overlap, 1.0)
```

### 9.4. Ví dụ

| hotel_id | Nguồn | pre_rank_score |
|----------|-------|----------------|
| 101 | template_search_api (0.9) | 0.45 |
| 202 | personalization (0.8) | 0.40 |
| 303 | cả hai (norm: 0.9 + 0.7) | 0.50 + 0.10 + 0.20 = **0.80** |

Hotel 303 được ưu tiên vì xuất hiện ở cả hai nguồn.

---

## 10. Engine API

**File:** `backend/app/recommendation/engine.py`

### 10.1. `run_candidate_pipeline(inp, trace=False, return_stats=False)`

Chạy toàn bộ Orchestrator → Merge.

```python
merged = run_candidate_pipeline(recommend_input, trace=True, return_stats=True)
# → (list[MergedCandidate], {"template_search_api": 8, "personalization": 5})
```

### 10.2. `run_rerank_from_merged(inp, merged, options=None)`

Chuyển `MergedCandidate` → format reranker → gọi `rerank()`.  
*(Thuộc boundary với module Rerank — xem tài liệu riêng.)*

### 10.3. `run_recommend_and_rerank(inp, options=None, trace=False)`

End-to-end: candidate pipeline + rerank trong một lần gọi.

---

## 11. Cấu Trúc Thư Mục

```text
backend/app/recommendation/
├── engine.py                    # Entry point
├── models.py                    # RecommendInput, CandidateHotel, MergedCandidate
├── trace.py                     # RecommendTrace logging
├── candidate_generation/
│   ├── orchestrator.py          # Chọn & chạy nguồn
│   ├── hotel_search/
│   │   ├── search_api.py        # Template Search API adapter
│   │   └── slots.py             # Extract slots từ RecommendInput
│   └── personalization/
│       └── personalization.py   # Neo4j collaborative / demographic
└── merge/
    └── merger.py                # REC_MERGE

backend/app/agent/
├── nodes.py                     # recommend_node, rewrite_node, rerank_node
├── qu_adapter.py                # Build RecommendInput từ QU
└── graph.py                     # LangGraph wiring
```

---

## 12. Cấu Hình Môi Trường

| Biến | Mặc định | Vai trò |
|------|----------|---------|
| `HOTEL_SEARCH_API_URL` | `https://search-api-....run.app/search` | Endpoint Template Search API |
| `HOTEL_SEARCH_API_TIMEOUT_SECONDS` | `20` | Timeout HTTP |
| `NEO4J_URI` | — | Kết nối Neo4j cho Personalization |
| `NEO4J_USER`, `NEO4J_PASSWORD` | — | Credentials Neo4j |

Personalization **không chạy** nếu Neo4j không khả dụng — pipeline vẫn trả kết quả từ Template Search API.

---

## 13. Tracing & Debug

**Logger:** `ota.trace.rec` (chi tiết), `ota.flow` (summary)

Khi request `/chat` có FlowTrace active, `recommend_node` bật `trace=True`:

```text
=== ① INTENT INPUT → RecommendInput ===
=== ② ORCHESTRATOR — chọn nguồn ===
=== ③ TEMPLATE SEARCH API ===
=== ④ PERSONALIZATION (Neo4j unified Cypher) ===
=== ⑥ REC_MERGE ===
```

**File:** `backend/app/recommendation/trace.py`

Mỗi bước log: destination, user_id, strategy, top candidates, số lượng trước/sau dedup.

---

## 14. Kiểm Thử

### 14.1. Test endpoints (development)

| Endpoint | Mô tả |
|----------|-------|
| `POST /test/recommend` | Chỉ Candidate Generation → Merge |
| `POST /test/rerank` | Full pipeline + Rerank |

**File:** `backend/app/api/routes/test.py`  
Yêu cầu `ENABLE_TEST_ENDPOINTS=true` và `ENVIRONMENT=development`.

### 14.2. Unit tests

```text
backend/tests/unit/recommendation/rerank/
├── test_schema.py
├── test_rule_scorer.py
├── test_profile_normalizer.py
└── test_trend_scorer.py
```

### 14.3. Ví dụ curl (qua /chat)

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"user-123\",\"session_id\":\"s1\",\"query\":\"Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu\",\"user_profile\":{},\"slots\":{},\"rerank_options\":{\"top_k\":5}}"
```

Kết quả gợi ý nằm trong `data.recommendations` sau khi QU + recommend + rerank hoàn tất.

---

## 15. Hạn Chế & Hướng Phát Triển

### Hạn chế hiện tại

| Hạng mục | Mô tả |
|----------|-------|
| Phụ thuộc `destination` | Không có city → không sinh candidate |
| Phụ thuộc `search_query_template` | Template Search API skip nếu rewrite thất bại |
| Guest user | Không có Personalization — chỉ semantic search |
| Neo4j cold start | Lần đầu truy vấn graph có thể chậm |
| Không có Qdrant nội bộ | Embedding search chuyển sang External Search API |

### Hướng phát triển

- Bổ sung nguồn candidate mới (ví dụ: rule-based filter, trending hotels)
- Tune `SOURCE_WEIGHTS` và overlap boost theo A/B test
- Cache kết quả Search API theo template hash
- Fallback khi Search API timeout — dùng chỉ Personalization hoặc ngược lại
- Đồng bộ `limit_per_source` động theo độ rộng query / số lượng filter

---

## 16. Tài Liệu Liên Quan

| Tài liệu | Nội dung |
|----------|----------|
| [`rerank.md`](../rerank%20_pipeline/rerank.md) | Module Rerank — scoring 10 features, rank & filter |
| [`intent_pipeline/07-router-contract.md`](../intent_pipeline/07-router-contract.md) | Router QU → `recommendation_plan` |
| [`intent_pipeline/00-overview.md`](../intent_pipeline/00-overview.md) | Tổng quan Query Understanding |
| [`doc_rag.md`](../../module_Rag/doc_rag.md) | Module RAG (chạy song song với Recommend) |
| `INTENT.md` | Intent v2 — profile, session context, search template |
| `README.md` | Hướng dẫn cài đặt và chạy dự án |
