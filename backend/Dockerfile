# Backend FastAPI image cho Cloud Run.
# Cloud Run cấp biến PORT (mặc định 8080); uvicorn phải bind 0.0.0.0:$PORT.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài dependency trước để tận dụng layer cache
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy mã nguồn backend (context build = thư mục backend/)
COPY . .

EXPOSE 8080
# Shell form để $PORT được expand lúc runtime
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
