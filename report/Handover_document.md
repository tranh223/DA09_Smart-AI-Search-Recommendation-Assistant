# Tài Liệu Bàn Giao Dự Án

## DA09 — Smart AI Search & Recommendation Assistant

| Thông tin | Chi tiết |
|-----------|----------|
| **Tên dự án** | Smart AI Search & Recommendation Assistant (VinBot / VinJourney) |
| **Mã dự án** | DA09 |
| **Repository** | https://github.com/tranh223/DA09_Smart-AI-Search-Recommendation-Assistant |
| **Demo** | https://da09-fe-338005853285.asia-southeast1.run.app/ |
| **Ngôn ngữ chính** | Python (backend), TypeScript (frontend) |
| **Phiên bản tài liệu** | 1.0 — Tháng 7/2026 |

---

## Mục Lục

1. [Tóm Tắt Dự Án](#1-tóm-tắt-dự-án)
2. [Phạm Vi & Chức Năng Đã Hoàn Thành](#2-phạm-vi--chức-năng-đã-hoàn-thành)
3. [Kiến Trúc Hệ Thống](#3-kiến-trúc-hệ-thống)
4. [Công Nghệ Sử Dụng](#4-công-nghệ-sử-dụng)
5. [Cấu Trúc Mã Nguồn](#5-cấu-trúc-mã-nguồn)
6. [Tài Liệu Kỹ Thuật (docs/)](#6-tài-liệu-kỹ-thuật-docs)
7. [Hướng Dẫn Cài Đặt & Chạy Local](#7-hướng-dẫn-cài-đặt--chạy-local)
8. [Cấu Hình Môi Trường](#8-cấu-hình-môi-trường)
9. [Triển Khai & Demo](#9-triển-khai--demo)
10. [API & Tích Hợp](#10-api--tích-hợp)
11. [Cơ Sở Dữ Liệu](#11-cơ-sở-dữ-liệu)
12. [Xác Thực & Tài Khoản](#12-xác-thực--tài-khoản)
13. [Kiểm Thử](#13-kiểm-thử)
14. [Logging, Giám Sát & Đánh Giá Chất Lượng](#14-logging-giám-sát--đánh-giá-chất-lượng)
15. [Hạn Chế & Vấn Đề Đã Biết](#15-hạn-chế--vấn-đề-đã-biết)
16. [Hướng Phát Triển Tiếp Theo](#16-hướng-phát-triển-tiếp-theo)
17. [Checklist Bàn Giao](#17-checklist-bàn-giao)

---

## 1. Tóm Tắt Dự Án

**VinBot** (hiển thị trên demo với tên **VinJourney Smart Assistant**) là trợ lý AI tích hợp trên nền tảng OTA (Online Travel Agency) giả lập. Người dùng chat bằng **tiếng Việt tự nhiên** để:

- Tìm kiếm và nhận gợi ý khách sạn phù hợp
- Hỏi thông tin chi tiết (chính sách, tiện ích, so sánh khách sạn) qua RAG
- Được hệ thống hỏi lại khi thiếu thông tin quan trọng (điểm đến, ngày, ngân sách)
- Nhận kết quả cá nhân hóa dựa trên profile ngắn hạn (phiên) và dài hạn (user)

**Luồng xử lý chính:**

```text
User Query
    → Session Load (MongoDB)
    → Query Understanding (Intent v2)
    → Slot Check / Clarify
    → Rewrite (Search Query Template)
    → RAG ∥ Recommendation (song song)
    → Rerank
    → Response Builder → Explain → Format → Analytics
```

---

## 2. Phạm Vi & Chức Năng Đã Hoàn Thành

### 2.1. Chức năng người dùng (Frontend)

| # | Chức năng | Trạng thái |
|---|-----------|------------|
| 1 | Giao diện OTA giả lập (tìm khách sạn, xem chi tiết) | ✅ Hoàn thành |
| 2 | Chatbot VinBot (widget chat) | ✅ Hoàn thành |
| 3 | Streaming câu trả lời từ backend | ✅ Hoàn thành |
| 4 | Hiển thị danh sách khách sạn gợi ý | ✅ Hoàn thành |
| 5 | Đăng ký / đăng nhập (JWT) | ✅ Hoàn thành |

### 2.2. Chức năng backend (AI Pipeline)

| # | Module | Trạng thái |
|---|--------|------------|
| 1 | Query Understanding v2 (guardrail, intent, hidden intent, profile) | ✅ Hoàn thành |
| 2 | Slot check & clarification | ✅ Hoàn thành |
| 3 | Recommendation (Template Search API + Neo4j Personalization) | ✅ Hoàn thành |
| 4 | Rerank (10 feature scores, explain) | ✅ Hoàn thành |
| 5 | RAG (Planner → Retrieval → Aggregation → Generation) | ✅ Hoàn thành |
| 6 | Session & profile persistence (MongoDB) | ✅ Hoàn thành |
| 7 | LangGraph orchestration | ✅ Hoàn thành |
| 8 | Auth API (JWT) | ✅ Hoàn thành |
| 9 | Analytics / Kafka logging | ✅ Hoàn thành (Kafka tùy chọn) |
| 10 | LangSmith tracing | ✅ Hỗ trợ (tùy chọn) |

### 2.3. Chưa hoàn thiện / ngoài phạm vi bàn giao

| Hạng mục | Ghi chú |
|----------|---------|
| Infra as Code (Terraform/K8s) | Thư mục `infra/` chưa có manifest đầy đủ |
| Đánh giá định lượng RAGAS tự động | Thiết kế có, job định kỳ cần vận hành thêm |
| Tối ưu latency RAG full pipeline | ~20–27s; cần tối ưu thêm |
| Graph Tool retrieval | Context còn nhiễu, cần cải thiện |

---

## 3. Kiến Trúc Hệ Thống

### 3.1. Sơ đồ tổng quan

```text
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Vite)                                        │
│  VinJourney UI  +  VinBot Chat Widget                           │
│  Deploy: Google Cloud Run (asia-southeast1)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + LangGraph)                                  │
│  POST /chat  |  /api/auth/*  |  /health/*  |  /test/* (dev)     │
└──────┬──────────────┬──────────────┬──────────────┬───────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
  MongoDB Atlas   Neo4j Graph    Qdrant Vector   PostgreSQL
  (session,       (personalize,  (RAG, entity    (Supabase —
   profile,        tag expand)    resolver)       OTA data)
   summary)
       │
       ▼
  Kafka (analytics, tùy chọn)
       │
       ▼
  External APIs:
  - OpenAI GPT-4o-mini (LLM)
  - Hotel Search API (semantic search)
  - OTA API (supabase-ota-travel.onrender.com)
  - Hotel Ask API (RAG — nhóm DA10)
```

### 3.2. LangGraph — các node chính

| Node | Vai trò |
|------|---------|
| `session_node` | Load history, summary, profile từ MongoDB |
| `intent_node` | Chạy Query Understanding Pipeline |
| `slot_check_node` | Kiểm tra đủ slot để recommend/RAG |
| `clarify_node` | Hỏi lại user khi thiếu thông tin |
| `rewrite_node` | Sinh `search_query_template` từ profile |
| `rag_node` | Pipeline RAG (Q&A khách sạn) |
| `recommend_node` | Candidate generation + merge |
| `rerank_node` | Xếp hạng lại & sinh lý do gợi ý |
| `response_builder_node` | Tổng hợp câu trả lời cuối |
| `explain_node` | Giải thích gợi ý |
| `analytics_node` | Persist state, gửi Kafka |

**File:** `backend/app/agent/graph.py`

---

## 4. Công Nghệ Sử Dụng

### Frontend

| Công nghệ | Vai trò |
|-----------|---------|
| React 18+ | UI framework |
| Vite 5+ | Build tool |
| TypeScript | Ngôn ngữ |
| Tailwind CSS | Styling |

### Backend

| Công nghệ | Vai trò |
|-----------|---------|
| Python 3.12+ | Runtime |
| FastAPI | REST API |
| LangGraph | Agent orchestration |
| LangChain | LLM integration |
| OpenAI GPT-4o-mini | LLM chính |
| Pydantic v2 | Data validation |

### Data & Infrastructure

| Dịch vụ | Vai trò |
|---------|---------|
| MongoDB Atlas | Session, profile, summary, eval |
| Neo4j | Knowledge graph, personalization |
| Qdrant | Vector store (RAG, entity resolver) |
| PostgreSQL (Supabase) | Dữ liệu OTA |
| Kafka | Event streaming (analytics) |
| Google Cloud Run | Deploy frontend (demo) |
| LangSmith | LLM tracing (tùy chọn) |

---

## 5. Cấu Trúc Mã Nguồn

```text
DA09_Smart-AI-Search-Recommendation-Assistant/
├── backend/                    # FastAPI backend
│   ├── main.py                 # Entry point uvicorn
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── agent/              # LangGraph nodes, graph, state
│       ├── api/routes/         # chat, auth, test, health
│       ├── auth/               # JWT authentication
│       ├── query_understanding/ # Intent v2 pipeline
│       ├── recommendation/     # Candidate gen, merge, rerank
│       ├── rag/                # RAG pipeline (standalone module)
│       └── db/                 # MongoDB, Qdrant clients
├── frontend/                   # React + Vite
│   ├── src/
│   ├── package.json
│   └── .env.example
├── docs/                       # Tài liệu kỹ thuật theo module
├── report/                     # Tài liệu bàn giao (thư mục này)
├── data/                       # Dữ liệu mẫu / CSV
├── notebooks/                  # Jupyter notebooks thử nghiệm
├── scripts/                    # Script tiện ích
├── INTENT.md                   # Tài liệu Intent v2 (root)
└── README.md                   # Hướng dẫn cài đặt & chạy
```

**Branch chính:** `main`  
**Không commit:** `.env`, `node_modules/`, `.venv/`, secret keys

---

## 6. Tài Liệu Kỹ Thuật (docs/)

Bảng tra cứu tài liệu chi tiết theo module:

| Module | Đường dẫn | Nội dung |
|--------|-----------|----------|
| **Query Understanding** | `docs/module_Recommend/intent_pipeline/` | Guardrail, intent, hidden intent, semantic mapping, profile retention, router |
| | `INTENT.md` (root) | Intent v2 runtime — session state, search template |
| **Recommendation** | `docs/module_Recommend/recommend_pipeline/recommend.md` | Orchestrator, Search API, Personalization, REC_MERGE |
| **Rerank** | `docs/module_Recommend/rerank _pipeline/rerank.md` | 5 phase rerank, scoring, explain |
| **RAG** | `docs/module_Rag/doc_rag.md` | Planner, Aggregation, Generation, tools |
| **Logging & CSAT** | `docs/module_log/log.md` | Realtime chat, Kafka, CSAT, RAGAS |
| **Auth** | `docs/authenticator/auth_api.md` | JWT, register/login, phân quyền |
| **MongoDB** | `docs/module_data/mongoDB/mongodb_schema.md` | Schema collections |
| **PostgreSQL** | `docs/module_data/supabase/relational_schema.md` | Schema OTA relational |
| **Neo4j / Graph** | `docs/module_data/graph_database/` | Edge weighting, queries, Kafka sync |

**Thứ tự đọc đề xuất cho người mới:**

1. `README.md` → cài đặt nhanh
2. `report/TAI_LIEU_BAN_GIAO.md` (file này) → tổng quan bàn giao
3. `docs/module_Recommend/intent_pipeline/00-overview.md` → QU pipeline
4. `docs/module_Recommend/recommend_pipeline/recommend.md` → Recommendation
5. `docs/module_Recommend/rerank _pipeline/rerank.md` → Rerank
6. `docs/module_Rag/doc_rag.md` → RAG

---

## 7. Hướng Dẫn Cài Đặt & Chạy Local

### Yêu cầu hệ thống

- Python 3.12+
- Node.js 20+ và npm
- MongoDB, Neo4j, Qdrant, OpenAI API key (chạy đầy đủ pipeline)
- Docker (cho Qdrant container `da09-qdrant`)

### Backend

```powershell
# Tại root repo
python -m venv .venv
.venv\Scripts\activate
cd backend
pip install -r requirements.txt
copy .env.example .env
# Chỉnh sửa .env với API keys thật

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra: `curl http://localhost:8000/health/live`

### Frontend

```powershell
cd frontend
copy .env.example .env
# Đặt VITE_BACKEND_BASE_URL=http://localhost:8000

npm install
npm run dev
```

Truy cập: `http://localhost:5173`

### Qdrant (lần đầu, cho RAG)

```powershell
# Khởi động container da09-qdrant (Docker)
python backend/app/rag/scripts/build_qdrant_hotels_from_csv.py
```

Chi tiết đầy đủ: [README.md](../README.md)

---

## 8. Cấu Hình Môi Trường

### Backend — biến quan trọng (`backend/.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| `OPENAI_API_KEY` | ✅ | API key OpenAI |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `DATABASE_NAME` | ✅ | Tên database (mặc định: `VinSmartFuture`) |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | ✅ | Neo4j cho personalization & graph |
| `HOTEL_SEARCH_API_URL` | Khuyến nghị | External semantic search API |
| `HOTEL_API_BASE_URL`, `HOTEL_API_KEY` | Khuyến nghị | OTA API |
| `KAFKA_URL` | Tùy chọn | Analytics; hệ thống vẫn chạy nếu thiếu |
| `LANGSMITH_*` | Tùy chọn | LLM tracing |
| `ENVIRONMENT` | — | `development` \| `production` |
| `MOCK_MODE` | — | `true` = stub data, bỏ qua DB thật |
| `CHAT_TIMEOUT_SECONDS` | — | Timeout mỗi request chat (mặc định 120s) |

> **Cảnh báo bảo mật:** Không commit file `.env`. Gửi secret qua kênh riêng khi bàn giao nội bộ.

### Frontend — biến quan trọng (`frontend/.env`)

| Biến | Mô tả |
|------|-------|
| `VITE_BACKEND_BASE_URL` | URL FastAPI backend |
| `VITE_OTA_BASE_URL` | OTA API (mặc định: supabase-ota-travel.onrender.com) |
| `VITE_OTA_API_KEY` | API key OTA (nếu có) |

Template: `backend/.env.example`, `frontend/.env.example`

---

## 9. Triển Khai & Demo

### Demo production

| Thành phần | URL |
|------------|-----|
| **Frontend (VinJourney)** | https://da09-fe-338005853285.asia-southeast1.run.app/ |
| **Repository** | https://github.com/tranh223/DA09_Smart-AI-Search-Recommendation-Assistant |

Frontend demo deploy trên **Google Cloud Run** (region `asia-southeast1`). Backend và các dịch vụ dữ liệu (MongoDB, Neo4j, Qdrant, OpenAI) được cấu hình qua biến môi trường trên môi trường deploy tương ứng.

### Build frontend production

```powershell
cd frontend
npm run build
# Output: frontend/dist/
```

### Chạy backend production

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

**Biến cần đổi khi production:**

```env
ENVIRONMENT=production
CORS_ORIGINS=https://da09-fe-338005853285.asia-southeast1.run.app
ENABLE_TEST_ENDPOINTS=false
```

### Cách sử dụng demo

1. Mở https://da09-fe-338005853285.asia-southeast1.run.app/
2. Duyệt trang OTA hoặc click icon **VinBot**
3. Nhập câu hỏi mẫu:

```text
Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu
```

4. Chờ phản hồi — lần đầu có thể chậm do cold start LLM/embedding

---

## 10. API & Tích Hợp

### 10.1. Endpoint chính — `POST /chat`

**Request:**

```json
{
  "user_id": "user-123",
  "session_id": "session-abc",
  "query": "Tìm khách sạn gia đình ở Đà Nẵng",
  "user_profile": {},
  "slots": {},
  "rerank_options": { "top_k": 5 }
}
```

**Response (rút gọn):**

```json
{
  "success": true,
  "request_id": "...",
  "data": {
    "answer": "...",
    "intent": "hotel_search",
    "recommendations": [...],
    "needs_clarification": false,
    "explanation": "...",
    "latency": {}
  },
  "latency_ms": 3500
}
```

### 10.2. Auth API — tiền tố `/api/auth`

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/auth/register` | Đăng ký tài khoản |
| POST | `/api/auth/login` | Đăng nhập, nhận JWT |
| GET | `/api/auth/me` | Thông tin user hiện tại |

Chi tiết: `docs/authenticator/auth_api.md`

### 10.3. Health check

```text
GET /health/live    — Liveness
GET /health/ready   — Readiness (kiểm tra DB)
```

### 10.4. Test endpoints (chỉ development)

| Endpoint | Mô tả |
|----------|-------|
| `POST /test/recommend` | Test candidate generation |
| `POST /test/rerank` | Test full recommend + rerank |
| `POST /test/intent` | Test Query Understanding |

Yêu cầu: `ENABLE_TEST_ENDPOINTS=true`, `ENVIRONMENT=development`

### 10.5. Swagger UI (development)

```text
http://localhost:8000/docs
http://localhost:8000/redoc
```

### 10.6. External APIs phụ thuộc

| API | URL mặc định | Vai trò |
|-----|--------------|---------|
| Hotel Search API | `search-api-....asia-southeast1.run.app/search` | Semantic hotel search |
| OTA API | `supabase-ota-travel.onrender.com` | Dữ liệu khách sạn OTA |
| OpenAI | `api.openai.com` | LLM |
| Hotel Ask (DA10) | (qua RAG tool) | RAG retrieval |

---

## 11. Cơ Sở Dữ Liệu

### 11.1. MongoDB (VinSmartFuture)

| Collection | Vai trò |
|------------|---------|
| `Users` | `long_term_profile` người dùng |
| `Sessions` | `history`, `session_context` theo phiên |
| `Summary` | Conversation summary, resume context |
| `TagRemoved` | Profile tags đã loại (retention) |
| `Booking` | Lịch sử đặt phòng |
| `Eval` / RAGAS | Đánh giá chất lượng |

Schema: `docs/module_data/mongoDB/mongodb_schema.md`

### 11.2. Neo4j (Knowledge Graph)

- Nodes: Hotel, Room, Tag, User, UserFeature, City, Place, Activity
- Dùng cho: personalization, tag expansion, graph retrieval (RAG)
- Tài liệu: `docs/module_data/graph_database/`

### 11.3. Qdrant

- Collection `hotels` — embedding BAAI/bge-m3 (768 dim)
- Dùng cho: RAG (Hotel Ask), Hotel Entity Resolver

### 11.4. PostgreSQL (Supabase)

- Dữ liệu relational OTA (khách sạn, phòng, booking)
- Schema: `docs/module_data/supabase/relational_schema.md`
- Rerank enrichment khi candidate không có `raw_hit`

---

## 12. Xác Thực & Tài Khoản

### Cơ chế

- JWT (HS256), access token mặc định **1 ngày**
- Phân quyền: `user` | `admin`
- Header: `Authorization: Bearer <token>`

### Chat không bắt buộc đăng nhập

Luồng VinBot chat có thể dùng `user_id` / `session_id` tự sinh mà không cần JWT. Đăng nhập cần thiết cho:

- Trang quản trị / dashboard admin
- Personalization đầy đủ (user không phải `guest_` / `anonymous_`)

### Tài khoản demo

| Vai trò | Tài khoản | Mật khẩu | Ghi chú |
|---------|-----------|----------|---------|
| **Admin** | `demo` | `abc123` | Trang quản trị / dashboard |
| **User** | `user001` | `123456` | Người dùng thông thường |

Đăng nhập qua demo: https://da09-fe-338005853285.asia-southeast1.run.app/

Hoặc qua API:

```powershell
# User
curl -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"user001\",\"password\":\"123456\"}"

# Admin
curl -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"demo\",\"password\":\"abc123\"}"
```

---

## 13. Kiểm Thử

### 13.1. Test thủ công end-to-end

1. Chạy backend `localhost:8000` + frontend `localhost:5173`
2. Mở VinBot, gửi câu hỏi tìm khách sạn
3. Kiểm tra log backend: `POST /chat 200`
4. Kiểm tra UI hiển thị recommendations

### 13.2. Test API bằng curl

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"test\",\"session_id\":\"s1\",\"query\":\"Tìm khách sạn ở Đà Nẵng ngân sách 5 triệu\",\"user_profile\":{},\"slots\":{},\"rerank_options\":{\"top_k\":5}}"
```

### 13.3. Unit tests

```powershell
cd backend
pytest tests/unit/
```

Các test rerank: `backend/tests/unit/recommendation/rerank/`

### 13.4. RAG smoke tests

```powershell
cd backend/app/rag/smoke_test
python benchmark_rag_system_full.py
```

---

## 14. Logging, Giám Sát & Đánh Giá Chất Lượng

| Thành phần | Mô tả | Tài liệu |
|------------|-------|----------|
| Flow trace | `ota_trace.jsonl` — trace từng node LangGraph | `backend/logs/` |
| Recommend trace | `ota.trace.rec` logger | `docs/module_Recommend/recommend_pipeline/recommend.md` |
| RAG trace | `backend/logs/qu_*.json` | `docs/module_Rag/doc_rag.md` |
| Rerank debug | `rerank_last_debug.json` | `docs/module_Recommend/rerank _pipeline/rerank.md` |
| Kafka analytics | Events sau mỗi turn chat | `docs/module_log/log.md` |
| CSAT | Đánh giá hài lòng khi kết thúc phiên | `docs/module_log/log.md` |
| RAGAS | Job định kỳ chấm chất lượng câu trả lời | `docs/module_log/log.md` |
| LangSmith | Tracing LLM (khi bật) | `LANGSMITH_*` env vars |

---

## 15. Hạn Chế & Vấn Đề Đã Biết

| # | Vấn đề | Mức độ | Ghi chú |
|---|--------|--------|---------|
| 1 | Latency `/chat` cao (đặc biệt RAG) | Trung bình | Lần đầu cold start; pipeline nhiều bước LLM |
| 2 | RAG full pipeline ~20–27s | Trung bình | Aggregation + Generation chiếm phần lớn |
| 3 | Graph Tool context nhiễu | Thấp | Cần tối ưu Cypher / lọc context |
| 4 | Kafka không bắt buộc | Thông tin | Analytics có thể thiếu nếu Kafka down |
| 5 | Guest user không có personalization | Thiết kế | Chỉ dùng Template Search API |
| 6 | Phụ thuộc external Search API | Trung bình | Timeout 20s; cần fallback |
| 7 | `infra/` chưa có Terraform/K8s đầy đủ | Thông tin | Deploy hiện thủ công / Cloud Run |

---

## 16. Hướng Phát Triển Tiếp Theo

1. **Giảm latency** — cache embedding, model rẻ hơn cho Aggregation, parallel LLM calls
2. **Tối ưu Graph retrieval** — cải thiện Cypher, lọc context trước RAG Aggregation
3. **Rewrite query** — chuyển sang Intent Detection thay vì xử lý trong RAG
4. **Infra as Code** — hoàn thiện Docker Compose / Terraform / K8s trong `infra/`
5. **A/B test rerank weights** — tune `SOURCE_WEIGHTS`, feature weights
6. **RAGAS automation** — job định kỳ + dashboard admin
7. **Fallback khi Search API timeout** — chỉ dùng personalization hoặc cached results

---

## 17. Checklist Bàn Giao

Dùng checklist sau khi nhận bàn giao dự án:

### Mã nguồn & Repository

- [ ] Clone được repo: https://github.com/tranh223/DA09_Smart-AI-Search-Recommendation-Assistant
- [ ] Branch `main` build và chạy được local
- [ ] Đã nhận file `.env` (backend + frontend) qua kênh bảo mật

### Tài liệu

- [ ] Đọc `report/TAI_LIEU_BAN_GIAO.md` (file này)
- [ ] Đọc `README.md` — hướng dẫn cài đặt
- [ ] Tra cứu `docs/` theo module cần maintain

### Môi trường & Dịch vụ

- [ ] Có quyền truy cập MongoDB Atlas
- [ ] Có quyền truy cập Neo4j
- [ ] Có quyền truy cập Qdrant (hoặc Docker local)
- [ ] Có OpenAI API key
- [ ] Có quyền truy cập Cloud Run demo (nếu cần vận hành)
- [ ] Có OTA API key / Hotel Search API (nếu cần)

### Kiểm thử

- [ ] `GET /health/live` trả 200
- [ ] `POST /chat` trả recommendations hợp lệ
- [ ] Demo https://da09-fe-338005853285.asia-southeast1.run.app/ hoạt động
- [ ] Đăng ký / đăng nhập Auth API hoạt động (nếu dùng)

### Bảo mật

- [ ] Không có secret trong Git history
- [ ] Đã rotate key nếu từng commit nhầm `.env`
- [ ] `CORS_ORIGINS` cấu hình đúng domain production

---

## Phụ Lục — Danh Sách File Bàn Giao

| Loại | Đường dẫn |
|------|-----------|
| Tài liệu bàn giao | `report/TAI_LIEU_BAN_GIAO.md` |
| Hướng dẫn chạy | `README.md` |
| Intent v2 | `INTENT.md` |
| Query Understanding wiki | `docs/module_Recommend/intent_pipeline/` |
| Recommendation | `docs/module_Recommend/recommend_pipeline/recommend.md` |
| Rerank | `docs/module_Recommend/rerank _pipeline/rerank.md` |
| RAG | `docs/module_Rag/doc_rag.md` |
| Logging / CSAT | `docs/module_log/log.md` |
| Auth | `docs/authenticator/auth_api.md` |
| MongoDB schema | `docs/module_data/mongoDB/mongodb_schema.md` |
| PostgreSQL schema | `docs/module_data/supabase/relational_schema.md` |
| Graph DB | `docs/module_data/graph_database/` |
| Env template backend | `backend/.env.example` |
| Env template frontend | `frontend/.env.example` |

---

*Tài liệu được tổng hợp từ mã nguồn, README và thư mục `docs/` của dự án DA09. Cập nhật lần cuối: Tháng 7/2026.*
