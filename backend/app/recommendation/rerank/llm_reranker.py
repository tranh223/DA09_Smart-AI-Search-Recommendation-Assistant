from __future__ import annotations

import json
import time
from typing import Any

from .config import Settings
from .mock_store import MockStore
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


def _openrouter_response(settings: Settings, query: str | None, profile: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    import requests

    messages = build_llm_messages(query, profile, candidates)
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-Title": "OTA Hotel Reranking Demo",
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=settings.llm_timeout_seconds,
    )
    if not response.ok:
        raise RuntimeError(f"openrouter_http_{response.status_code}: {_compact_response_text(response.text)}")
    raw = response.json()
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not choices:
        raise RuntimeError(f"openrouter_missing_choices: {_compact_response_text(json.dumps(raw, ensure_ascii=False, default=str))}")
    content = choices[0].get("message", {}).get("content") if isinstance(choices[0], dict) else None
    if not content:
        raise RuntimeError("openrouter_empty_message_content")
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
        "model": settings.openrouter_model,
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
        if settings.mock_mode:
            payload = MockStore(settings).get_llm_response()
            validated = validate_llm_output(payload, allowed_ids)
            detail["raw_response"] = payload
            detail["validated"] = summarize_llm_validation(payload, allowed_ids)
            detail["reason"] = None if validated else "mock_llm_response_has_no_valid_items"
            return validated, "mock", False, detail
        if dry_run:
            detail["reason"] = "options.llm_dry_run=true"
            return {}, "dry_run", True, detail
        if not settings.openrouter_api_key:
            detail["reason"] = "missing_openrouter_api_key"
            return {}, "fallback", True, detail
        payload = None
        last_error = None
        max_attempts = max(settings.llm_max_retries + 1, 1)
        for attempt in range(1, max_attempts + 1):
            try:
                payload = _openrouter_response(settings, query, profile, candidates)
                detail["attempts"].append({"attempt": attempt, "ok": True})
                break
            except Exception as error:
                last_error = error
                detail["attempts"].append({"attempt": attempt, "ok": False, "error": f"{type(error).__name__}: {error}"})
                if attempt < max_attempts:
                    time.sleep(min(0.5 * attempt, 2.0))
        if payload is None:
            detail["reason"] = f"{type(last_error).__name__}: {last_error}" if last_error else "openrouter_no_response"
            return {}, "fallback", True, detail
        validated = validate_llm_output(payload, allowed_ids)
        detail["raw_response"] = payload
        detail["validated"] = summarize_llm_validation(payload, allowed_ids)
        detail["reason"] = None if validated else "openrouter_response_has_no_valid_items"
        return validated, "openrouter", not bool(validated), detail
    except Exception as error:
        detail["reason"] = f"{type(error).__name__}: {error}"
        return {}, "fallback", True, detail
