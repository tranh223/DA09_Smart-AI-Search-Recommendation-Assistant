from __future__ import annotations

import contextlib
from typing import Any, Iterator

from langsmith import Client, traceable

try:
    from langsmith import trace as langsmith_trace
except Exception:  # pragma: no cover - depends on installed langsmith version
    langsmith_trace = None

try:
    from utils.settings import settings
    from utils.logger import get_logger
except Exception:  # pragma: no cover - standalone app/rag script mode
    from utils.settings import settings
    from utils.logger import get_logger


logger = get_logger(__name__)


class LangSmithTracer:
    """Small best-effort wrapper around LangSmith tracing."""

    def __init__(self) -> None:
        self.enabled = False
        self.client = None

        if not settings.LANGSMITH_TRACING or not settings.LANGSMITH_API_KEY:
            return

        try:
            self.client = Client(
                api_key=settings.LANGSMITH_API_KEY,
                api_url=settings.LANGSMITH_ENDPOINT,
            )
            self.enabled = True
            logger.info("LangSmith tracing enabled")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to initialize LangSmith: {str(exc)}")

    def trace(self, name: str):
        """Return a decorator that traces a function when LangSmith is enabled."""

        def decorator(func):
            if not self.enabled:
                return func
            return traceable(
                name=name,
                project_name=settings.LANGSMITH_PROJECT,
            )(func)

        return decorator

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        *,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        run_type: str = "chain",
    ) -> Iterator[Any]:
        """Create a LangSmith span if possible, without affecting runtime flow."""

        if not self.enabled:
            yield None
            return

        if langsmith_trace is not None:
            try:
                with langsmith_trace(
                    name=name,
                    run_type=run_type,
                    inputs=inputs or {},
                    metadata=metadata or {},
                    project_name=settings.LANGSMITH_PROJECT,
                ) as run:
                    try:
                        yield run
                    except Exception as exc:
                        self._end_run(run, error=repr(exc))
                        raise
                    else:
                        if outputs is not None:
                            self._end_run(run, outputs=outputs)
                return
            except TypeError:
                # Older langsmith versions may expose a different trace() API.
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Error creating LangSmith span {name}: {str(exc)}")
                yield None
                return

        self._trace_marker(name, inputs=inputs, metadata=metadata, run_type=run_type)
        yield None

    def _trace_marker(
        self,
        name: str,
        *,
        inputs: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        run_type: str,
    ) -> None:
        def _span_marker(**kwargs: Any) -> dict[str, Any]:
            return kwargs

        try:
            traced = traceable(
                name=name,
                run_type=run_type,
                project_name=settings.LANGSMITH_PROJECT,
                metadata=metadata or None,
            )(_span_marker)
            traced(**(inputs or {}))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Error logging LangSmith marker {name}: {str(exc)}")

    def _end_run(
        self,
        run: Any,
        *,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if run is None or not hasattr(run, "end"):
            return

        try:
            if error is not None:
                run.end(error=error)
            elif outputs is not None:
                run.end(outputs=outputs)
        except TypeError:
            try:
                run.end(outputs=outputs or {})
            except Exception:
                pass
        except Exception:
            pass

    def log_run(
        self,
        name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        run_type: str = "chain",
    ) -> None:
        """Compatibility shim for older callers."""

        if not self.enabled:
            return

        with self.span(name, inputs=inputs, outputs=outputs, run_type=run_type):
            return


tracer = LangSmithTracer()
