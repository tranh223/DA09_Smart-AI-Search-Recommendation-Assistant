"""Booking endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.analytics.logging.logger import log_booking_for_graph
from app.api.middleware import get_request_id
from app.api.models import APIResponse
from app.auth.dependencies import get_current_user_dep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/booking", tags=["booking"])


class BookingCreateRequest(BaseModel):
    hotel_id: int = Field(gt=0)
    hotel_name: str = Field(min_length=1)


@router.post("", response_model=APIResponse, summary="Book a hotel")
async def create_booking(
    req: BookingCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user_dep),
) -> APIResponse:
    req_id = get_request_id()
    try:
        account = current_user.get("account") or {}
        user_id = account.get("user_id")
        if not user_id:
            return APIResponse.fail(
                code="INVALID_USER",
                message="Không xác định được người dùng hiện tại.",
                request_id=req_id,
            )

        inserted_id = log_booking_for_graph(req.hotel_id, user_id, req.hotel_name)
        if inserted_id is None:
            return APIResponse.fail(
                code="BOOKING_SAVE_FAILED",
                message="Không lưu được booking.",
                request_id=req_id,
            )

        return APIResponse.ok(
            data={
                "booking_id": str(inserted_id),
                "hotel_id": req.hotel_id,
                "hotel_name": req.hotel_name,
            },
            request_id=req_id,
        )
    except Exception:
        logger.exception("create booking failed")
        return APIResponse.fail(
            code="INTERNAL_ERROR",
            message="Booking error",
            request_id=req_id,
        )
