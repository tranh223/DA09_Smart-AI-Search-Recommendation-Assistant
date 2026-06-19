from __future__ import annotations

import json
import time
from typing import Any

from .config import Settings
from .prompt_builder import build_llm_messages
from .utils import clamp, to_str_id


def validate_llm_output(payload: Any, allowed_ids: set[str]) -> dict[str, dict[str, Any]]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    ranked = payload.get("ranked_items") if isinstance(payload, dict) else None
    if not isinstance(ranked, list):
        return {}
    valid: dict[str, dict[str, Any]] = {}
    for item in ranked:
        if not isinstance(item, dict):
            continue
        item_id = to_str_id(item.get("item_id"))
        if item_id not in allowed_ids:
            continue
        try:
            score = float(item.get("llm_score"))
        except (TypeError, ValueError):
            continue
        if not 0 <= score <= 1:
            continue
        valid[item_id] = {
            "llm_score": clamp(score),
            "rank": item.get("rank"),
            "reasons": [str(x) for x in item.get("reasons", []) if x is not None],
            "warnings": [str(x) for x in item.get("warnings", []) if x is not None],
        }
    return valid


def summarize_llm_validation(payload: Any, allowed_ids: set[str]) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            return {
                "raw_item_count": 0,
                "valid_item_ids": [],
                "rejected_items": [{"reason": "invalid_json", "detail": str(error)}],
            }
    ranked = payload.get("ranked_items") if isinstance(payload, dict) else None
    if not isinstance(ranked, list):
        return {
            "raw_item_count": 0,
            "valid_item_ids": [],
            "rejected_items": [{"reason": "missing_ranked_items"}],
        }

    rejected: list[dict[str, Any]] = []
    valid_ids: list[str] = []
    for index, item in enumerate(ranked):
        if not isinstance(item, dict):
            rejected.append({"index": index, "reason": "item_not_object"})
            continue
        item_id = to_str_id(item.get("item_id"))
        if item_id not in allowed_ids:
            rejected.append({"index": index, "item_id": item_id, "reason": "item_id_not_in_top_n"})
            continue
        try:
            score = float(item.get("llm_score"))
        except (TypeError, ValueError):
            rejected.append({"index": index, "item_id": item_id, "reason": "llm_score_not_number"})
            continue
        if not 0 <= score <= 1:
            rejected.append({"index": index, "item_id": item_id, "reason": "llm_score_out_of_range"})
            continue
        valid_ids.append(item_id)

    return {
        "raw_item_count": len(ranked),
        "valid_item_ids": valid_ids,
        "rejected_items": rejected,
    }


def _compact_response_text(value: str, limit: int = 500) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _openai_response(settings: Settings, query: str | None, profile: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    from openai import OpenAI  # noqa: PLC0415

    client = OpenAI(api_key=settings.openai_api_key)
    messages = build_llm_messages(query, profile, candidates)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.rerank_temperature,
        response_format={"type": "json_object"},
        timeout=settings.llm_timeout_seconds,
    )
    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise RuntimeError("openai_empty_message_content")
    return json.loads(content)


def build_llm_debug_request(query: str | None, profile: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    messages = build_llm_messages(query, profile, candidates)
    return {
        "messages": messages,
        "candidate_ids": [item["item_id"] for item in candidates],
    }


def rerank_with_llm(
    settings: Settings,
    query: str | None,
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    use_llm: bool,
    dry_run: bool = False,
) -> tuple[dict[str, dict[str, Any]], str, bool, dict[str, Any]]:
    detail: dict[str, Any] = {
        "requested": bool(use_llm),
        "candidate_ids": [item["item_id"] for item in candidates],
        "model": settings.llm_model,
        "request": None,
        "reason": None,
        "raw_response": None,
        "attempts": [],
        "validated": {
            "raw_item_count": 0,
            "valid_item_ids": [],
            "rejected_items": [],
        },
    }
    if not use_llm:
        detail["reason"] = "options.use_llm_rerank=false"
        return {}, "fallback", False, detail
    if not candidates:
        detail["reason"] = "no_candidates_after_hard_filter"
        return {}, "fallback", True, detail
    allowed_ids = {item["item_id"] for item in candidates}
    try:
        detail["request"] = build_llm_debug_request(query, profile, candidates)
        if dry_run:
            detail["reason"] = "options.llm_dry_run=true"
            return {}, "dry_run", True, detail
        if not settings.openai_api_key:
            detail["reason"] = "missing_openai_api_key"
            return {}, "fallback", True, detail
        payload = None
        last_error = None
        max_attempts = max(settings.llm_max_retries + 1, 1)
        for attempt in range(1, max_attempts + 1):
            try:
                payload = _openai_response(settings, query, profile, candidates)
                detail["attempts"].append({"attempt": attempt, "ok": True})
                break
            except Exception as error:
                last_error = error
                detail["attempts"].append({"attempt": attempt, "ok": False, "error": f"{type(error).__name__}: {error}"})
                if attempt < max_attempts:
                    time.sleep(min(0.5 * attempt, 2.0))
        if payload is None:
            detail["reason"] = f"{type(last_error).__name__}: {last_error}" if last_error else "openai_no_response"
            return {}, "fallback", True, detail
        validated = validate_llm_output(payload, allowed_ids)
        detail["raw_response"] = payload
        detail["validated"] = summarize_llm_validation(payload, allowed_ids)
        detail["reason"] = None if validated else "openai_response_has_no_valid_items"
        return validated, "openai", not bool(validated), detail
    except Exception as error:
        detail["reason"] = f"{type(error).__name__}: {error}"
        return {}, "fallback", True, detail
