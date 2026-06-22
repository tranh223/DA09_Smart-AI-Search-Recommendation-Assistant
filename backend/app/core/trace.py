"""
Central request-scoped tracing cho toàn bộ OTA Smart AI pipeline.

Hai kênh output:
  ota.flow    — console, một dòng tóm tắt mỗi span (human-readable)
  ota.trace   — file JSON, mỗi request dump một dòng JSON đầy đủ (machine-readable)

Sử dụng:
    # Khởi tạo khi nhận request (chat.py):
    trace = FlowTrace(request_id, user_id, session_id, query)
    token = set_current_trace(trace)
    trace.log_start()

    # Bất kỳ node/module nào muốn ghi thêm:
    trace = current_trace()
    if trace:
        span = trace.begin("my_span")
        span.add(field1=value1, field2=value2)
        span.finish()
        trace.log_span(span)

    # Khi kết thúc request:
    trace.log_end(needs_clarify=..., intent=..., n_recs=...)
    trace.finalize()          # dump full JSON
    reset_trace(token)
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

# ── Loggers ───────────────────────────────────────────────────────────────────

FLOW_LOG = logging.getLogger("ota.flow")      # console, một dòng tóm tắt
DETAIL_LOG = logging.getLogger("ota.trace")   # file JSON, toàn bộ detail

_SEP = "═" * 60

# ── ContextVar ────────────────────────────────────────────────────────────────

_trace_var: contextvars.ContextVar["FlowTrace | None"] = contextvars.ContextVar(
    "flow_trace", default=None
)


# ── Span ──────────────────────────────────────────────────────────────────────

@dataclass
class Span:
    """Một đơn vị thời gian trong request trace."""

    name: str
    started_at: float = field(default_factory=time.perf_counter)
    elapsed_ms: float = 0.0
    status: str = "ok"          # ok | error | skip | warn
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    sub_spans: list["Span"] = field(default_factory=list)

    def finish(self, status: str = "ok", **data: Any) -> None:
        """Đóng span và tính elapsed_ms."""
        self.elapsed_ms = round((time.perf_counter() - self.started_at) * 1000, 2)
        self.status = status
        if data:
            self.data.update(data)

    def add(self, **kwargs: Any) -> "Span":
        """Thêm metadata vào span, trả về self để chain."""
        self.data.update(kwargs)
        return self

    def sub(self, name: str) -> "Span":
        """Tạo sub-span con, tự động append vào sub_spans."""
        s = Span(name=name)
        self.sub_spans.append(s)
        return s

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "elapsed_ms": self.elapsed_ms,
            "status": self.status,
        }
        if self.error:
            d["error"] = self.error
        if self.data:
            d["data"] = self.data
        if self.sub_spans:
            d["sub_spans"] = [s.to_dict() for s in self.sub_spans]
        return d


# ── FlowTrace ─────────────────────────────────────────────────────────────────

class FlowTrace:
    """
    Tập hợp tất cả spans cho một request /chat.

    Console output (ota.flow): mỗi span → 1 dòng tóm tắt.
    File output  (ota.trace):  finalize() → 1 dòng JSON đầy đủ cuối request.
    """

    def __init__(
        self,
        request_id: str,
        user_id: str,
        session_id: str,
        query: str,
    ) -> None:
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.query = query
        self.started_at = time.perf_counter()
        self.spans: list[Span] = []

    # ── Tiện ích ─────────────────────────────────────────────────────────────

    @property
    def _p(self) -> str:
        return f"[{self.request_id[:16]}]"

    def elapsed_total_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 2)

    # ── Span API ─────────────────────────────────────────────────────────────

    def begin(self, name: str) -> Span:
        """Tạo span mới và append vào danh sách."""
        s = Span(name=name)
        self.spans.append(s)
        return s

    @contextmanager
    def span(self, name: str) -> Generator[Span, None, None]:
        """Context-manager tự động finish span khi thoát."""
        s = self.begin(name)
        try:
            yield s
        except Exception as exc:
            if s.elapsed_ms == 0.0:
                s.finish(status="error", error=str(exc))
            raise
        else:
            if s.elapsed_ms == 0.0:
                s.finish()

    # ── Console logging ───────────────────────────────────────────────────────

    def log_start(self) -> None:
        p = self._p
        FLOW_LOG.info("%s %s", p, _SEP)
        FLOW_LOG.info("%s ► POST /chat  user=%s  session=%s", p, self.user_id, self.session_id)
        FLOW_LOG.info("%s   query=%r", p, self.query[:140])

    def log_span(self, span: Span) -> None:
        """Log một dòng tóm tắt cho span (bỏ qua field dạng dict/list để console sạch)."""
        p = self._p
        icon = "✗" if span.status == "error" else ("~" if span.status in ("skip", "warn") else "─")
        scalar_pairs = [
            f"{k}={v}"
            for k, v in span.data.items()
            if not isinstance(v, (dict, list))
        ]
        data_str = "  ".join(scalar_pairs)
        if data_str:
            FLOW_LOG.info(
                "%s %s %-22s %8.1fms  %s",
                p, icon, span.name, span.elapsed_ms, data_str,
            )
        else:
            FLOW_LOG.info("%s %s %-22s %8.1fms", p, icon, span.name, span.elapsed_ms)

    def log_end(
        self,
        *,
        needs_clarify: bool,
        intent: str,
        n_recs: int = 0,
        n_srcs: int = 0,
    ) -> None:
        total_ms = round(self.elapsed_total_ms())
        p = self._p
        stage_ms = {s.name: s.elapsed_ms for s in self.spans}
        bottleneck = max(stage_ms, key=stage_ms.__getitem__) if stage_ms else "?"
        bottleneck_ms = stage_ms.get(bottleneck, 0.0) if isinstance(bottleneck, str) else 0.0
        if needs_clarify:
            FLOW_LOG.info(
                "%s ◆ DONE %dms  → CLARIFY  intent=%s  bottleneck=%s(%.0fms)",
                p, total_ms, intent, bottleneck, bottleneck_ms,
            )
        else:
            FLOW_LOG.info(
                "%s ◆ DONE %dms  intent=%s  recs=%d  srcs=%d  bottleneck=%s(%.0fms)",
                p, total_ms, intent, n_recs, n_srcs, bottleneck, bottleneck_ms,
            )
        FLOW_LOG.info("%s %s", p, _SEP)

    # ── JSON dump (detail) ────────────────────────────────────────────────────

    def finalize(self) -> None:
        """Dump toàn bộ trace ra ota.trace logger (JSON một dòng)."""
        doc: dict[str, Any] = {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "query": self.query,
            "total_ms": self.elapsed_total_ms(),
            "spans": [s.to_dict() for s in self.spans],
        }
        DETAIL_LOG.info(json.dumps(doc, ensure_ascii=False, default=str))


# ── ContextVar helpers ────────────────────────────────────────────────────────

def current_trace() -> "FlowTrace | None":
    """Trả về FlowTrace hiện tại của request, hoặc None nếu chưa set."""
    return _trace_var.get()


def set_current_trace(trace: "FlowTrace") -> contextvars.Token:
    return _trace_var.set(trace)


def reset_trace(token: contextvars.Token) -> None:
    _trace_var.reset(token)
