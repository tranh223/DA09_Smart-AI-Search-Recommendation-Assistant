"""API middleware: Request ID injection + structured access logging."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.access")

# Context var — readable anywhere in same request context
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-ID into every request/response.

    Priority: reuses header from upstream (load balancer / client),
    otherwise generates a new UUIDv4.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or uuid.uuid4().hex
        )
        token = request_id_var.set(req_id)
        try:
            t0 = time.perf_counter()
            response: Response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - t0) * 1000)

            response.headers["X-Request-ID"] = req_id
            response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

            logger.info(
                "%s %s %s %dms rid=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                req_id,
            )
            return response
        finally:
            request_id_var.reset(token)
