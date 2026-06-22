"""Pydantic schemas for authentication request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Body cho API đăng ký tài khoản."""

    username: str = Field(min_length=3, max_length=50, description="Tên đăng nhập (unique)")
    password: str = Field(min_length=6, max_length=128, description="Mật khẩu")
    name: str = Field(min_length=1, max_length=200, description="Tên hiển thị")


class LoginRequest(BaseModel):
    """Body cho API đăng nhập."""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


# ── Response Models ───────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class AuthData(BaseModel):
    """Response đầy đủ trả về khi login/register — nằm trong APIResponse.data."""

    access_token: str
    token_type: str = "bearer"
    role: str
    user: dict[str, Any] = Field(
        description="User profile từ collection Users"
    )
