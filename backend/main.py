"""OTA Smart AI — FastAPI application entry point."""

from __future__ import annotations

import importlib
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# ── Logging configuration ─────────────────────────────────────────────────────
# Must run before any other import that creates a logger.
# Uvicorn configures root logger handlers on startup; we only set levels here
# so our app namespaces emit at the right verbosity without double-handling.

def _configure_logging() -> None:
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_dir = os.getenv("QU_TRACE_LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
    os.makedirs(log_dir, exist_ok=True)

    # Dedicated formatter for the ota.flow trace logger (not propagated to root)
    _flow_fmt = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    flow_log = logging.getLogger("ota.flow")
    flow_log.setLevel(log_level)
    if not flow_log.handlers:
        import io as _io
        _stream = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") \
            if hasattr(sys.stdout, "buffer") else sys.stdout
        _h = logging.StreamHandler(_stream)
        _h.setFormatter(_flow_fmt)
        flow_log.addHandler(_h)
    flow_log.propagate = False  # avoid double output with uvicorn root handler

    # Dedicated file sink for QueryUnderstanding deep traces.
    # Pipeline code only emits logger.info(); this handler decides where it is stored.
    qu_trace_path = os.getenv(
        "QU_TRACE_LOG_FILE",
        os.path.join(log_dir, "query_understanding_trace.log"),
    )
    os.makedirs(os.path.dirname(qu_trace_path) or ".", exist_ok=True)
    qu_trace_log = logging.getLogger("query_understanding")
    qu_trace_log.setLevel(log_level)
    qu_file_handler = next(
        (
            handler
            for handler in qu_trace_log.handlers
            if isinstance(handler, RotatingFileHandler)
            and getattr(handler, "baseFilename", None) == os.path.abspath(qu_trace_path)
        ),
        None,
    )
    if qu_file_handler is None:
        qu_file_handler = RotatingFileHandler(
            qu_trace_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        qu_file_handler.setFormatter(_flow_fmt)
        qu_trace_log.addHandler(qu_file_handler)

    # Same pipeline can be imported as app.query_understanding.* in test/debug paths.
    app_qu_trace_log = logging.getLogger("app.query_understanding")
    app_qu_trace_log.setLevel(log_level)
    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == os.path.abspath(qu_trace_path)
        for handler in app_qu_trace_log.handlers
    ):
        app_qu_trace_log.addHandler(qu_file_handler)

    # ── ota.trace  — JSON trace file (một dòng JSON đầy đủ mỗi request) ─────
    trace_log_path = os.getenv(
        "OTA_TRACE_LOG_FILE",
        os.path.join(log_dir, "ota_trace.jsonl"),
    )
    _json_fmt = logging.Formatter(fmt="%(message)s")   # chỉ message, không prefix
    trace_log = logging.getLogger("ota.trace")
    trace_log.setLevel(logging.INFO)
    _has_trace_handler = any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, "baseFilename", None) == os.path.abspath(trace_log_path)
        for h in trace_log.handlers
    )
    if not _has_trace_handler:
        _trace_fh = RotatingFileHandler(
            trace_log_path,
            maxBytes=20 * 1024 * 1024,   # 20 MB mỗi file
            backupCount=5,
            encoding="utf-8",
        )
        _trace_fh.setFormatter(_json_fmt)
        trace_log.addHandler(_trace_fh)
    trace_log.propagate = False   # không bị uvicorn stdout lặp

    # ── ota.trace.rec — recommendation detail (text, không JSON) ────────────
    rec_trace_path = os.getenv(
        "OTA_REC_TRACE_LOG_FILE",
        os.path.join(log_dir, "ota_rec_trace.log"),
    )
    rec_trace_log = logging.getLogger("ota.trace.rec")
    rec_trace_log.setLevel(logging.INFO)
    _has_rec_handler = any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, "baseFilename", None) == os.path.abspath(rec_trace_path)
        for h in rec_trace_log.handlers
    )
    if not _has_rec_handler:
        _rec_fh = RotatingFileHandler(
            rec_trace_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        _rec_fh.setFormatter(_flow_fmt)
        rec_trace_log.addHandler(_rec_fh)
    rec_trace_log.propagate = False

    # App-wide namespaces inherit root handler (uvicorn stdout)
    for _ns in ("app", "ota", "api", "query_understanding"):
        logging.getLogger(_ns).setLevel(log_level)


_configure_logging()

# ── LangChain compatibility patch (must run before any langgraph import) ──────
langchain_load = importlib.import_module("langchain_core.load.load")


def _patch_langchain_reviver_default() -> None:
    original_reviver = langchain_load.Reviver

    class ReviverWithAllowedObjects(original_reviver):
        def __init__(self, *args, **kwargs):
            if not args and "allowed_objects" not in kwargs:
                kwargs["allowed_objects"] = "core"
            super().__init__(*args, **kwargs)

    langchain_load.Reviver = ReviverWithAllowedObjects


_patch_langchain_reviver_default()

# ── sys.path: allow legacy absolute imports like "query_understanding.*" ──────
BASE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

# ── Application imports ───────────────────────────────────────────────────────
from app.analytics.logging.logger import start_log_listener  # noqa: E402
from app.api.middleware import RequestIDMiddleware, get_request_id  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.chat import router as chat_router  # noqa: E402
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.test import router as test_router  # noqa: E402
from app.api.routes.traces import router as traces_router  # noqa: E402

logger = logging.getLogger(__name__)

# ── Environment config ────────────────────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# CORS — comma-separated origins; "*" allowed only in development
_raw_origins = os.getenv("CORS_ORIGINS", "" if IS_PRODUCTION else "*")
CORS_ORIGINS: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins != "*"
    else ["*"]
)

# Test endpoints — disabled by default in production
ENABLE_TEST_ENDPOINTS = (
    os.getenv("ENABLE_TEST_ENDPOINTS", "false" if IS_PRODUCTION else "true").lower()
    == "true"
)


# ── Startup validation ────────────────────────────────────────────────────────

def _check_required_env() -> list[str]:
    """Return list of missing critical env vars."""
    required = ["OPENAI_API_KEY", "MONGO_URI", "NEO4J_URI", "NEO4J_PASSWORD"]
    return [v for v in required if not os.getenv(v)]


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = _check_required_env()
    if missing:
        logger.warning(
            "[startup] Missing env vars (some features may degrade): %s",
            ", ".join(missing),
        )
    else:
        logger.info("[startup] All required env vars present.")

    worker = threading.Thread(target=start_log_listener, daemon=True)
    worker.start()
    logger.info("[startup] Kafka log listener started.")

    # Ensure MongoDB indexes for trace_runs (non-blocking)
    try:
        from app.db.trace_store import _ensure_indexes  # noqa: PLC0415
        threading.Thread(target=_ensure_indexes, daemon=True).start()
    except Exception as _exc:  # noqa: BLE001
        logger.warning("[startup] trace_store index init skipped: %s", _exc)
    logger.info(
        "[startup] OTA Smart AI ready — env=%s  log_level=%s  test_endpoints=%s",
        ENVIRONMENT,
        os.getenv("LOG_LEVEL", "INFO"),
        ENABLE_TEST_ENDPOINTS,
    )
    yield
    logger.info("[shutdown] Application shutting down.")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="OTA Smart AI Search & Recommendation",
    description=(
        "AI-powered hotel search and recommendation assistant.\n\n"
        "**Main endpoint**: `POST /chat`\n\n"
        "**Health**: `GET /health/ready` (readiness), `GET /health/live` (liveness)\n\n"
        "**Test/Debug**: `POST /test/*` — disabled in production."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Swagger/ReDoc disabled in production
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# ── Middleware (order matters — outermost first) ──────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # allow_credentials must be False when allow_origins contains "*"
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)

app.add_middleware(RequestIDMiddleware)


# ── Global exception handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = get_request_id()
    logger.error(
        "[%s] Unhandled exception on %s %s: %s",
        req_id,
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "request_id": req_id,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        },
        headers={"X-Request-ID": req_id},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(traces_router)

if ENABLE_TEST_ENDPOINTS:
    app.include_router(test_router)
    logger.info("[startup] Test endpoints enabled at /test/*")
else:
    logger.info("[startup] Test endpoints disabled (ENVIRONMENT=%s)", ENVIRONMENT)


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "OTA Smart AI Search & Recommendation",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "health": "/health/ready",
    }
