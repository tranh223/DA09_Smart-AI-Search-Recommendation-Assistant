"""Shared Pydantic models cho API response layer.

Mọi endpoint đều wrap kết quả trong APIResponse để client
xử lý nhất quán dù success hay error.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Machine-readable error code, e.g. VALIDATION_ERROR")
    message: str = Field(description="Human-readable error message")


class APIResponse(BaseModel):
    """Envelope chuẩn cho mọi response."""

    success: bool
    request_id: str = Field(description="Unique request identifier for tracing")
    data: Any | None = Field(default=None)
    error: ErrorDetail | None = Field(default=None)
    latency_ms: int | None = Field(default=None)

    @classmethod
    def ok(
        cls,
        data: Any,
        *,
        request_id: str,
        latency_ms: int | None = None,
    ) -> APIResponse:
        return cls(
            success=True,
            request_id=request_id,
            data=data,
            latency_ms=latency_ms,
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        *,
        request_id: str,
    ) -> APIResponse:
        return cls(
            success=False,
            request_id=request_id,
            error=ErrorDetail(code=code, message=message),
        )
