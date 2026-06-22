"""FastAPI dependencies for authentication — Bearer token extraction & role check."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.security import decode_access_token
from app.auth.service import get_current_user_data

logger = logging.getLogger(__name__)

# HTTPBearer — Swagger UI chỉ hiện 1 ô nhập token, paste vào là xong.
http_bearer = HTTPBearer()


async def get_current_user_dep(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict[str, Any]:
    """Decode JWT and load account + user profile.

    Returns
    -------
    dict
        ``{"account": {...}, "user_profile": {...}}``

    Raises
    ------
    HTTPException 401
        If the token is missing, expired, or invalid.
    HTTPException 404
        If the user referenced by the token no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        return get_current_user_data(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản không tồn tại.",
        )


async def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user_dep),
) -> dict[str, Any]:
    """Dependency that ensures the current user has ``role == 'admin'``.

    Raises
    ------
    HTTPException 403
        If the user is not an admin.
    """
    account = current_user.get("account", {})
    if account.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập tài nguyên này.",
        )
    return current_user
