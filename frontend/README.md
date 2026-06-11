# Travel Assistant — ChatUI (React + Vite + Tailwind)

ChatUI cho Travel Assistant: gửi tin nhắn, nhận **product cards** (khách sạn / điểm tham
quan) kèm lý do "vì sao phù hợp", và câu hỏi làm rõ khi thiếu thông tin.

## Chạy (full-stack mock)

```bash
# 1) Backend (terminal khác) — từ thư mục gốc dự án
uvicorn app.main:app --reload      # http://localhost:8000

# 2) Frontend
npm install
npm run dev                        # http://localhost:5173
```

Vite proxy `/api` → `http://localhost:8000` (xem `vite.config.ts`), nên ChatUI gọi
`/api/chat` (SSE). Đặt `VITE_API_BASE` nếu backend ở nơi khác.

## Cấu trúc

- `src/types.ts` — mirror `app/api/schemas.py` (BE là nguồn chân lý).
- `src/api/chat.ts` — POST `/chat`, parse SSE (`token` → `result` → `done`).
- `src/hooks/useChat.ts` — state hội thoại + streaming.
- `src/components/ProductCard.tsx` — render 1 `RecommendationCard`.
