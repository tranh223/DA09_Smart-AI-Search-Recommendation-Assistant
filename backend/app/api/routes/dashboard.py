"""Admin dashboard endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, Depends

from app.api.models import APIResponse
from app.auth.dependencies import require_admin
from app.analytics.dashboard.analyst import analysis_by_day, analysis_by_month
from app.db.mongo.mongo_client import get_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=APIResponse, summary="Overview metrics for today")
async def overview(current_user=Depends(require_admin)) -> APIResponse:
    req_id = "-"
    try:
        eval_col = get_collection("Eval")
        today = datetime.utcnow().strftime("%Y-%m-%d")
        doc = eval_col.find_one({"date": today})
        if not doc:
            data = {"csat": 0, "latency": 0, "ttft": 0, "hit rate": 0, "input token": 0, "output token": 0}
        else:
            csat = sum(doc.get("csat") or []) / (len(doc.get("csat") or []) or 1)
            latency = sum(doc.get("latency") or []) / (len(doc.get("latency") or []) or 1)
            ttft = sum(doc.get("ttft") or []) / (len(doc.get("ttft") or []) or 1)
            booking_list = doc.get("booking") or []
            booked = sum(1 for b in booking_list if b is True) if booking_list else 0
            booking = booked / len(booking_list) if booking_list else 0
            inp_token = sum(doc.get("input_token") or []) / (len(doc.get("input_token") or []) or 1)
            out_token = sum(doc.get("output_token") or []) / (len(doc.get("output_token") or []) or 1)
            data = {"csat": round(csat, 2), "latency": round(latency, 2), "ttft": round(ttft, 2), "hit rate": round(booking * 100, 2), "input token": inp_token, "output token": out_token}
        return APIResponse.ok(data=data, request_id=req_id)
    except Exception as exc:
        logger.exception("overview failed")
        return APIResponse.fail(code="INTERNAL_ERROR", message="Overview error", request_id=req_id)


@router.get("/analysis/day", response_model=APIResponse, summary="Daily analysis for a month")
async def day_analysis(month: int = None, current_user=Depends(require_admin)) -> APIResponse:
    req_id = "-"
    try:
        if month is None:
            month = datetime.utcnow().month
        data = analysis_by_day(int(month))
        return APIResponse.ok(data=data, request_id=req_id)
    except Exception as exc:
        logger.exception("day analysis failed")
        return APIResponse.fail(code="INTERNAL_ERROR", message=f"Day analysis error {exc}", request_id=req_id)


@router.get("/analysis/month", response_model=APIResponse, summary="Monthly analysis for a year")
async def month_analysis(year: int = None, current_user=Depends(require_admin)) -> APIResponse:
    req_id = "-"
    try:
        if year is None:
            year = datetime.utcnow().year
        data = analysis_by_month(int(year))
        return APIResponse.ok(data=data, request_id=req_id)
    except Exception as exc:
        logger.exception("month analysis failed")
        return APIResponse.fail(code="INTERNAL_ERROR", message="Month analysis error", request_id=req_id)
