from __future__ import annotations

import os
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Backward-compatible path for legacy absolute imports like "query_understanding.*"
BASE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

from app.analytics.logging.logger import start_log_listener
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.test import router as test_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_thread = threading.Thread(target=start_log_listener, daemon=True)
    worker_thread.start()
    yield


app = FastAPI(
    title="OTA Smart AI Search & Recommendation",
    description=(
        "AI-powered hotel search and recommendation assistant.\n\n"
        "**Luồng chính**: `/chat`\n\n"
        "**Debug/Test**: `/test/*` endpoints để kiểm tra từng module riêng lẻ.\n\n"
        "**Health**: `/health` để kiểm tra trạng thái toàn hệ thống."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(test_router)


@app.get("/", tags=["root"], summary="Root")
def read_root():
    return {
        "message": "OTA Smart AI — Still alive",
        "docs": "/docs",
        "health": "/health",
    }