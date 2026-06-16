from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import Settings


def write_rerank_log(settings: Settings, payload: dict[str, Any]) -> None:
    log_path = settings.base_dir / "logs" / "rerank_runs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

