# DA09 — Smart AI Search & Recommendation Assistant

Hệ thống trợ lý tìm kiếm và gợi ý khách sạn thông minh dựa trên AI, được xây dựng cho nền tảng VinSmart Future (VSF). Người dùng nhắn tin bằng ngôn ngữ tự nhiên (tiếng Việt) để tìm kiếm khách sạn phù hợp — hệ thống hiểu ý định, hỏi lại nếu thiếu thông tin, và gợi ý danh sách khách sạn từ OTA API.

---

## Mục Lục

1. [Mô Tả Dự Án](#1-mô-tả-dự-án)
2. [Công Nghệ Sử Dụng](#2-công-nghệ-sử-dụng)
3. [Cài Đặt Dependencies](#3-cài-đặt-dependencies)
4. [Cấu Hình Môi Trường (.env)](#4-cấu-hình-môi-trường-env)
5. [Chạy Backend](#5-chạy-backend)
6. [Chạy Frontend](#6-chạy-frontend)
7. [Build & Deploy](#7-build--deploy)
8. [API Documentation](#8-api-documentation)
9. [Test End-to-End](#9-test-end-to-end)
10. [Tài Khoản Demo](#10-tài-khoản-demo)
11. [Lỗi Thường Gặp](#11-lỗi-thường-gặp)
12. [Ghi Chú](#12-ghi-chú)

---

## 1. Mô Tả Dự Án

**VinBot** là chatbot AI tích hợp trong trang web OTA (Online Travel Agency) giả lập. Người dùng có thể:

- Nhắn tin bằng tiếng Việt tự nhiên, ví dụ: *"Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu"*
- Bot tự động hiểu ý định (intent), hỏi lại khi thiếu thông tin (ngày, điểm đến, ngân sách)
- Gợi ý danh sách khách sạn phù hợp từ kho dữ liệu thật qua OTA Search API
- Ghi nhớ profile người dùng (sở thích dài hạn, ngắn hạn) để cá nhân hóa kết quả
- Giải thích lý do gợi ý bằng ngôn ngữ tự nhiên

Luồng chính: `User query → Query Understanding → Slot Check → Recommendation → Rerank → Response`


---

## 2. Công Nghệ Sử Dụng

### Frontend
| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| React | 18+ | UI framework |
| Vite | 5+ | Build tool / Dev server |
| TypeScript | 5+ | Ngôn ngữ |
| Tailwind CSS | 3+ | Styling |

### Backend
| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| Python | 3.12+ | Ngôn ngữ |
| FastAPI | 0.111+ | API framework |
| LangGraph | 0.2+ | AI agent graph orchestration |
| LangChain | 0.2+ | LLM integration |
| OpenAI GPT-4o-mini | — | LLM chính cho intent/response |

### Database & Storage
| Dịch vụ | Vai trò |
|---------|---------|
| MongoDB Atlas | Session, profile người dùng, lịch sử chat, summary |
| Neo4j | Knowledge graph cho tag expansion (semantic) |
| Qdrant | Vector database cho RAG (tìm kiếm ngữ nghĩa) |
| PostgreSQL (Supabase) | Dữ liệu OTA (khách sạn, booking) |

### External API & Services
| Dịch vụ | Vai trò |
|---------|---------|
| OTA Search API | API tìm kiếm & gợi ý khách sạn (Supabase hosted) |
| Hotel Search API | Semantic search khách sạn qua vector embedding |
| LangSmith | Tracing & monitoring LLM (tùy chọn) |
| Kafka | Analytics events (tùy chọn, không bắt buộc để chạy) |

---

## 3. Cài Đặt Dependencies

### Backend (Python)

```powershell
# Tại thư mục gốc của repo
python -m venv .venv
.venv\Scripts\activate

cd backend
pip install -r requirements.txt
```

Nếu `.venv` đã tồn tại, chỉ cần activate:

```powershell
.venv\Scripts\activate
```

### Frontend (Node.js)

Yêu cầu Node.js 20+ và npm.

```powershell
cd frontend
npm install
```

---

## 4. Cấu Hình Môi Trường (.env)

### Backend — `backend/.env`

Tạo file từ template:

```powershell
copy backend\.env.example backend\.env
```

Các biến quan trọng cần cấu hình:

```env
# -------------------------
# LLM
# -------------------------
OPENAI_API_KEY=sk-...           # API key OpenAI (bắt buộc)
LLM_MODEL=gpt-4o-mini           # Model mặc định cho toàn pipeline

# -------------------------
# MongoDB
# -------------------------
MONGO_URI=mongodb+srv://...     # Connection string MongoDB Atlas (bắt buộc)
DATABASE_NAME=VinSmartFuture    # Tên database

# -------------------------
# Neo4j (Knowledge Graph)
# -------------------------
NEO4J_URI=bolt://...            # URI kết nối Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# -------------------------
# OTA / Hotel Search API
# -------------------------
HOTEL_API_BASE_URL=https://supabase-ota-travel.onrender.com
HOTEL_API_KEY=...               # API key OTA
HOTEL_SEARCH_API_URL=https://search-api-....run.app/search

# -------------------------
# Kafka (tùy chọn)
# -------------------------
KAFKA_URL=localhost:9092         # Nếu không có Kafka, hệ thống vẫn chạy được

# -------------------------
# Runtime
# -------------------------
ENVIRONMENT=development          # development | staging | production
CHAT_TIMEOUT_SECONDS=120
MOCK_MODE=false                  # true = dùng stub data, bỏ qua kết nối DB thật

# -------------------------
# LangSmith Tracing (tùy chọn)
# -------------------------
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=DA09
LANGSMITH_TRACING=true
```

> **Lưu ý:** Khi `MOCK_MODE=true`, backend bỏ qua kết nối MongoDB, Neo4j, Qdrant — phù hợp để test nhanh mà không cần infra đầy đủ.

### Frontend — `frontend/.env`

Tạo file từ template:

```powershell
copy frontend\.env.example frontend\.env
```

Nội dung cần cấu hình:

```env
# OTA Travel API (khách sạn)
VITE_OTA_BASE_URL=https://supabase-ota-travel.onrender.com
VITE_OTA_API_KEY=                          # API key nếu có

# FastAPI backend (AI assistant)
VITE_BACKEND_BASE_URL=http://localhost:8000
```

---

## 5. Chạy Backend

```powershell
# Activate venv (nếu chưa)
.venv\Scripts\activate

# Vào thư mục backend
cd backend

# Khởi động server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend chạy tại: `http://localhost:8000`

Kiểm tra nhanh:

```powershell
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

> **Qdrant (RAG):** Nếu chạy RAG, cần Docker và container `da09-qdrant` đang running. Lần đầu chạy build vector store:
> ```powershell
> python app/rag/scripts/build_qdrant_hotels_from_csv.py
> ```

---

## 6. Chạy Frontend

Mở terminal mới (backend phải đang chạy):

```powershell
cd frontend
npm run dev
```

Frontend chạy tại: `http://localhost:5173`

Mở trình duyệt, click vào icon **VinBot** góc phải màn hình để bắt đầu chat.

---

## 7. Build & Deploy

### Build Frontend (production)

```powershell
cd frontend
npm run build
```

Output tại `frontend/dist/` — có thể deploy lên Vercel, Netlify, hoặc serve tĩnh.

### Chạy Backend (production)

```powershell
# Không dùng --reload khi production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

Hoặc dùng Docker (nếu có `Dockerfile` trong `infra/`):

```powershell
docker compose -f infra/docker-compose.yml up -d
```

### Biến môi trường production cần đổi

```env
ENVIRONMENT=production           # Ẩn /docs, /redoc, tắt test endpoints
CORS_ORIGINS=https://your-domain.com
ENABLE_TEST_ENDPOINTS=false
MOCK_MODE=false
```

---

## 8. API Documentation

### `POST /chat`

Endpoint chính để chat với VinBot.

**Request:**

```json
{
  "user_id": "user-123",
  "session_id": "session-abc",
  "query": "Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu",
  "user_profile": {},
  "slots": {},
  "rerank_options": {
    "top_k": 5
  }
}
```

**Response:**

```json
{
  "success": true,
  "request_id": "req-...",
  "data": {
    "answer": "Dưới đây là các khách sạn phù hợp cho gia đình...",
    "intent": "hotel_search",
    "recommendations": [],
    "sources": [],
    "next_suggestions": ["Bạn muốn lọc theo tiện ích không?"],
    "needs_clarification": false,
    "clarification_question": "",
    "explanation": "",
    "latency": {}
  },
  "error": null,
  "latency_ms": 1500
}
```

### Swagger UI (development only)

```
http://localhost:8000/docs
http://localhost:8000/redoc
```

### Health Check

```powershell
curl http://localhost:8000/health/live    # Liveness probe
curl http://localhost:8000/health/ready  # Readiness probe (check DB connections)
```

---

## 9. Test End-to-End

1. Chạy backend tại `http://localhost:8000`
2. Chạy frontend tại `http://localhost:5173`
3. Mở trình duyệt, click **VinBot**
4. Nhập câu ví dụ:

```
Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu
```

Kết quả mong đợi:
- Terminal backend có log `POST /chat 200`
- VinBot trả danh sách khách sạn với giá, mô tả, lý do gợi ý

Test bằng curl:

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"test-user\",\"session_id\":\"test-session\",\"query\":\"Tìm khách sạn gia đình ở Đà Nẵng ngân sách 10 triệu\",\"user_profile\":{},\"slots\":{},\"rerank_options\":{\"top_k\":5}}"
```

---

## 10. Tài Khoản Demo

### Đăng nhập hệ thống

| Vai trò | Tài khoản | Mật khẩu |
|---------|-----------|----------|
| **Admin** | `demo` | `abc123` |
| **User** | `user001` | `123456` |

- **Admin:** truy cập trang quản trị / dashboard
- **User:** người dùng thông thường, personalization đầy đủ

Đăng nhập qua UI hoặc API:

```powershell
curl -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"user001\",\"password\":\"123456\"}"
```

### Chat VinBot (không bắt buộc đăng nhập)

Mỗi phiên chat có thể dùng `user_id` / `session_id` tự sinh mà không cần JWT. Để test với profile đã có lịch sử, dùng lại cùng `user_id` qua các lần gọi API.

---

## 11. Lỗi Thường Gặp

### `ModuleNotFoundError: No module named 'kafka'`

```powershell
pip install -r backend/requirements.txt
```

Kafka là tùy chọn; nếu chưa có Kafka server, hệ thống vẫn chat bình thường.

### Frontend không kết nối được backend

Kiểm tra `frontend/.env`:

```env
VITE_BACKEND_BASE_URL=http://localhost:8000
```

Sau khi sửa `.env`, restart frontend:

```powershell
npm run dev
```

### Request `/chat` mất rất nhiều thời gian

Pipeline AI gồm nhiều bước: guardrail → intent extraction → slot check → RAG → recommendation → rerank → response. Lần đầu chạy thường chậm hơn do tải model và cache cold-start.

Điều chỉnh timeout nếu cần:

```env
CHAT_TIMEOUT_SECONDS=180
LLM_TIMEOUT_SECONDS=45
```

### Lỗi kết nối MongoDB / Neo4j / Qdrant

Kiểm tra các URI trong `backend/.env`. Dùng `MOCK_MODE=true` để bỏ qua kết nối thật khi dev/test.

---
### Báo Cáo & Tài Liệu Bàn Giao — DA09

Thư mục này chứa tài liệu bàn giao chính thức của dự án **Smart AI Search & Recommendation Assistant**.

| Tài liệu | Mô tả |
|----------|--------|
| [**TAI_LIEU_BAN_GIAO.md**](./TAI_LIEU_BAN_GIAO.md) | Tài liệu bàn giao tổng hợp — đọc file này trước |

### Liên kết nhanh

- **Repository:** https://github.com/tranh223/DA09_Smart-AI-Search-Recommendation-Assistant
- **Demo (Frontend):** https://da09-fe-338005853285.asia-southeast1.run.app/
- **Tài liệu kỹ thuật chi tiết:** [docs/](../docs/)

## 12. Ghi Chú

- **Không commit file `.env`** — file này chứa API key và credentials thật.
- `frontend/package.json`: quản lý dependencies UI (npm).
- `backend/requirements.txt`: quản lý dependencies Python (pip).
- Log debug LLM pipeline tại `backend/logs/` (JSON files theo từng request).
- Trace chi tiết từng node trong LangGraph qua LangSmith (nếu bật `LANGSMITH_TRACING=true`).
- Tài liệu kiến trúc Intent v2 xem tại [INTENT.md](./INTENT.md).
