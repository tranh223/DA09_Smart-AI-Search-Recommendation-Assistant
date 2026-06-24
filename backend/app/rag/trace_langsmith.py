from __future__ import annotations

import contextlib
from typing import Any, Iterator

try:
    from app.rag.utils.langsmith_tracer import tracer
except Exception:  # pragma: no cover - standalone app/rag script mode
    from utils.langsmith_tracer import tracer


@contextlib.contextmanager
def rag_langsmith_span(
    name: str,
    *,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Best-effort LangSmith span boundary."""

    enabled = getattr(tracer, "enabled", False)
    if not enabled:
        yield
        return

    with tracer.span(
        name,
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
    ):
        yield

