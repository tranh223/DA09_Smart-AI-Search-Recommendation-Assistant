# GCP Setup — DA09 Smart AI Search & Recommendation Assistant

Tóm tắt hạ tầng GCP của dự án.

## Tổng quan

| Thành phần        | Giá trị                                                                 |
| ----------------- | ----------------------------------------------------------------------- |
| Region            | `asia-southeast1`                                                       |
| Project number    | `338005853285`                                                          |
| Nền tảng deploy   | Cloud Run (managed)                                                     |
| Registry          | Artifact Registry — repo Docker tên `da09`                              |
| CI/CD             | Cloud Build (trigger khi push `main`, chạy `cloudbuild.yaml`)           |
| Secrets           | Secret Manager                                                          |

Hai service chạy trên Cloud Run:

- **Backend** — FastAPI (Python 3.12) chạy bằng `uvicorn`, bind `0.0.0.0:$PORT` (Cloud Run cấp `PORT`, mặc định 8080).
  URL: `https://da09-smart-ai-search-recommendation-assistant-338005853285.asia-southeast1.run.app`
- **Frontend** — Vite build tĩnh, serve bằng nginx (multi-stage Docker), expose port 8080.

## Backend (`backend/Dockerfile`)

- Base `python:3.12-slim`, cài `requirements.txt` trước để tận dụng layer cache.
- `CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`.

Service Cloud Run (`da09-backend`) deploy với:

- `--allow-unauthenticated`, `--port=8080`
- `--memory=2Gi --cpu=2 --timeout=600`
- Env không nhạy cảm: `DATABASE_NAME=VinSmartFuture`, `QDRANT_COLLECTION=hotels`, `LOG_LEVEL=INFO`
- Secrets (từ Secret Manager, gắn qua `--set-secrets`): `OPENAI_API_KEY`, `MONGO_URI`, `NEO4J_PASSWORD`, `POSTGRES_DSN`

## Frontend (`frontend/Dockerfile`)

- Multi-stage: `node:20-alpine` build Vite → `nginx:1.27-alpine` serve `dist/`.
- Biến `VITE_*` nhúng cứng lúc build, truyền qua `--build-arg`:
  - `VITE_BACKEND_BASE_URL` → URL backend Cloud Run ở trên
  - `VITE_OTA_BASE_URL`, `VITE_OTA_API_KEY`

## CI/CD — Cloud Build (`cloudbuild.yaml`)

Trigger chạy khi push lên `main`. Các bước:

1. `docker build` image backend (context = `./backend`), tag theo `$SHORT_SHA` và `latest`.
2. `docker push --all-tags` lên Artifact Registry: `${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/${_SERVICE}`.
3. `gcloud run deploy ${_SERVICE}` với image `$SHORT_SHA`.

Substitutions: `_REGION=asia-southeast1`, `_REPO=da09`, `_SERVICE=da09-backend`.

## Checklist thiết lập (làm 1 lần)

1. Bật API: `run`, `cloudbuild`, `artifactregistry`, `secretmanager`.
2. Tạo Artifact Registry repo Docker tên `da09` (region `asia-southeast1`).
3. Cấp role cho service account của Cloud Build: **Cloud Run Admin**, **Service Account User**, **Artifact Registry Writer**.
4. Tạo secret trong Secret Manager: `OPENAI_API_KEY`, `MONGO_URI`, `NEO4J_PASSWORD`, `POSTGRES_DSN`.
5. Tạo Cloud Build trigger trỏ vào `cloudbuild.yaml`, nhánh `main`.
