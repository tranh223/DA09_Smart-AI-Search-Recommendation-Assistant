# DA09 Smart AI Search & Recommendation Assistant

Ứng dụng gồm:

- `backend/`: FastAPI backend cho AI chat, query understanding, RAG, recommendation, rerank.
- `frontend/`: React + Vite UI, gọi backend `/chat` và OTA hotel API.

## Yêu Cầu

- Python 3.12+
- Node.js 20+ và npm
- MongoDB/Neo4j/Qdrant/OpenAI API key nếu muốn chạy đầy đủ pipeline AI

## 1. Chạy Backend

Mở terminal tại root repo:

```powershell
cd D:\AI_VIN\DA09_VSF\DA09_Smart-AI-Search-Recommendation-Assistant\backend
```

Tạo/copy file môi trường:

```powershell
copy .env.example .env
```

Cập nhật các biến quan trọng trong `backend/.env`:

```env
OPENAI_API_KEY=...
MONGO_URI=...
DATABASE_NAME=VinSmartFuture
NEO4J_URI=...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
KAFKA_URL=localhost:9092
CHAT_TIMEOUT_SECONDS=180
```

Cài thư viện Python:

```powershell
python -m venv ..\.venv
..\.venv\Scripts\activate
pip install -r requirements.txt
```

Nếu venv đã tồn tại, chỉ cần activate:

```powershell
..\.venv\Scripts\activate
```
Chạy Qdrant cho RAG (cho lần đầu):
```powershell
python backend/app/rag/scripts/build_qdrant_hotels_from_csv.py
```
Mở docker và khởi động container da09-qdrant

Chạy API:
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend sẽ chạy tại:

```text
http://localhost:8000
```

Test nhanh:

```powershell
curl http://localhost:8000/health/live
```

Test chat:

```powershell
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"frontend-user\",\"session_id\":\"test-session\",\"query\":\"Tìm khách sạn gia đình ở Đà Nẵng ngân sách 10 triệu\",\"user_profile\":{},\"slots\":{},\"rerank_options\":{\"top_k\":5}}"
```

## 2. Chạy Frontend

Mở terminal khác:

```powershell
cd D:\AI_VIN\DA09_VSF\DA09_Smart-AI-Search-Recommendation-Assistant\frontend
```

Tạo file môi trường:

```powershell
copy .env.example .env
```

Kiểm tra `frontend/.env`:

```env
VITE_OTA_BASE_URL=https://supabase-ota-travel.onrender.com
VITE_OTA_API_KEY=
VITE_BACKEND_BASE_URL=http://localhost:8000
```

Cài thư viện UI:

```powershell
npm install
```

Chạy UI:

```powershell
npm run dev
```

Frontend thường chạy tại:

```text
http://localhost:5173
```

Build kiểm tra production:

```powershell
npm run build
```

## 3. Test End-to-End

1. Chạy backend ở `http://localhost:8000`.
2. Chạy frontend ở `http://localhost:5173`.
3. Mở UI trên browser.
4. Bấm VinBot.
5. Nhập ví dụ:

```text
Tìm khách sạn gia đình ở Đà Nẵng từ 19/6 đến 23/6, ngân sách 10 triệu
```

Nếu kết nối đúng:

- Terminal backend sẽ có log `POST /chat`.
- UI sẽ hiển thị câu trả lời từ backend trong VinBot.

## 4. Endpoint Chính

### `POST /chat`

Request:

```json
{
  "user_id": "frontend-user",
  "session_id": "test-session",
  "query": "Tìm khách sạn ở Đà Nẵng",
  "user_profile": {},
  "slots": {},
  "rerank_options": {
    "top_k": 5
  }
}
```

Response:

```json
{
  "success": true,
  "request_id": "...",
  "data": {
    "answer": "...",
    "intent": "...",
    "recommendations": [],
    "sources": [],
    "next_suggestions": [],
    "needs_clarification": false,
    "clarification_question": "",
    "explanation": "",
    "latency": {}
  },
  "error": null,
  "latency_ms": 123
}
```

### Health Check

```powershell
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## 5. Lỗi Thường Gặp

### `ModuleNotFoundError: No module named 'kafka'`

Cài lại dependency backend:

```powershell
pip install -r backend/requirements.txt
```

Kafka analytics là phụ trợ; nếu chưa chạy Kafka, hệ thống vẫn có thể chat nếu các service chính hoạt động.

### Frontend không gọi được backend

Kiểm tra:

- Backend đang chạy tại `http://localhost:8000`
- `frontend/.env` có:

```env
VITE_BACKEND_BASE_URL=http://localhost:8000
```

Sau khi sửa `.env`, restart frontend:

```powershell
npm run dev
```

### Request `/chat` rất lâu

Pipeline AI có thể tải model embedding, gọi LLM, RAG, rerank. Lần đầu chạy thường chậm hơn do tải model/cache.

## 6. Ghi Chú

- Không commit file `.env` vì có thể chứa secret.
- `frontend/package.json` dùng cho npm/UI.
- `backend/requirements.txt` dùng cho pip/backend Python.