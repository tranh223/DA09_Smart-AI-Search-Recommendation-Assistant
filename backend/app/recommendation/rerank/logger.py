from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import Settings


def write_rerank_log(settings: Settings, payload: dict[str, Any], write_debug_file: bool = True) -> None:
    log_path = settings.base_dir / "logs" / "rerank_runs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    # Optionally write a human-friendly debug JSON file for the last run
    if write_debug_file:
        try:
            pretty_path = settings.base_dir / "logs" / "rerank_last_debug.json"
            with pretty_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        except Exception:
            # Do not raise logging errors
            pass


def write_mapping_log(settings: Any, raw_input: list[dict], normalized: list[dict]) -> None:
    try:
        path = settings.base_dir / "logs" / "rerank_candidates_mapping.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_candidates_input": raw_input,
            "normalized_candidates": normalized
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


