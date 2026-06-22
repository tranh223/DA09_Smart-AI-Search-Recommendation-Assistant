"""Auth API routes — register, login, me."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.middleware import get_request_id
from app.api.models import APIResponse
from app.auth.dependencies import get_current_user_dep
from app.auth.schemas import AuthData, LoginRequest, RegisterRequest
from app.auth.service import login_user, register_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Register ──────────────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=APIResponse,
    summary="Đăng ký tài khoản mới",
    description=(
        "Tạo account (username/password) và user profile mặc định.\n\n"
        "Trả về JWT access token + thông tin user."
    ),
)
async def register(req: RegisterRequest) -> APIResponse:
    req_id = get_request_id()
    try:
        auth_data: AuthData = register_user(
            username=req.username,
            password=req.password,
            name=req.name,
        )
    except ValueError as exc:
        logger.warning("[%s] Register failed: %s", req_id, exc)
        return APIResponse.fail(
            code="REGISTER_FAILED",
            message=str(exc),
            request_id=req_id,
        )
    except Exception as exc:
        logger.error("[%s] Register error: %s", req_id, exc, exc_info=True)
        return APIResponse.fail(
            code="INTERNAL_ERROR",
            message="Đăng ký thất bại. Vui lòng thử lại.",
            request_id=req_id,
        )

    logger.info("[%s] User registered: %s", req_id, req.username)
    return APIResponse.ok(data=auth_data.model_dump(), request_id=req_id)


# ── Login ─────────────────────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=APIResponse,
    summary="Đăng nhập",
    description=(
        "Xác thực bằng username/password.\n\n"
        "Trả về JWT access token + user profile + role."
    ),
)
async def login(req: LoginRequest) -> APIResponse:
    req_id = get_request_id()
    try:
        auth_data: AuthData = login_user(
            username=req.username,
            password=req.password,
        )
    except ValueError as exc:
        logger.warning("[%s] Login failed: %s", req_id, exc)
        return APIResponse.fail(
            code="LOGIN_FAILED",
            message=str(exc),
            request_id=req_id,
        )
    except Exception as exc:
        logger.error("[%s] Login error: %s", req_id, exc, exc_info=True)
        return APIResponse.fail(
            code="INTERNAL_ERROR",
            message="Đăng nhập thất bại. Vui lòng thử lại.",
            request_id=req_id,
        )

    logger.info("[%s] User logged in: %s", req_id, req.username)
    return APIResponse.ok(data=auth_data.model_dump(), request_id=req_id)


# ── Me ────────────────────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=APIResponse,
    summary="Lấy thông tin user hiện tại",
    description=(
        "Yêu cầu header ``Authorization: Bearer <token>``.\n\n"
        "Trả về account info (không bao gồm password) + user profile."
    ),
)
async def me(
    current_user: dict[str, Any] = Depends(get_current_user_dep),
) -> APIResponse:
    req_id = get_request_id()
    return APIResponse.ok(data=current_user, request_id=req_id)
