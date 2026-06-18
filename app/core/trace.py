"""Trace thời gian + output từng bước của pipeline, phát ra khi được BẬT.

Tầng service (recommender, chat) chỉ phát "sự kiện bước" qua context manager `step()`,
KHÔNG phụ thuộc rich/CLI/HTTP. Mặc định TẮT (sink = None). Nơi nào muốn xem thì gắn sink:
    · CLI/terminal  -> trace.stdout_sink (in ra stdout)
    · API           -> sink đẩy event vào hàng đợi để stream xuống frontend

Sink VÀ depth đều là ContextVar nên mỗi request/luồng có trạng thái riêng — an toàn khi
server xử lý song song nhiều request.

Dùng ở tầng service:
    from app.core import trace
    with trace.step("Lấy hồ sơ") as s:
        ...
        s.note(f"{n} sở thích")        # tóm tắt output của bước
"""

from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable, Iterator

# Sink nhận mỗi sự kiện bước ĐÃ hoàn tất. None = trace tắt (trong context hiện tại).
# event = {"name": str, "seconds": float, "notes": list[str], "depth": int}
_sink: ContextVar[Callable[[dict], None] | None] = ContextVar("trace_sink", default=None)
_depth: ContextVar[int] = ContextVar("trace_depth", default=0)


def set_sink(sink: Callable[[dict], None] | None):
    """Gắn sink cho context hiện tại; trả token để reset() nếu cần."""
    return _sink.set(sink)


def reset(token) -> None:
    _sink.reset(token)


def is_enabled() -> bool:
    return _sink.get() is not None


class Step:
    """Tay cầm của một bước: thu thập các dòng tóm tắt output qua note()."""

    __slots__ = ("name", "notes")

    def __init__(self, name: str) -> None:
        self.name = name
        self.notes: list[str] = []

    def note(self, message: str) -> None:
        """Ghi một mẩu output/tóm tắt của bước (chỉ giữ khi trace bật)."""
        if _sink.get() is not None:
            self.notes.append(message)


@contextmanager
def step(name: str) -> Iterator[Step]:
    """Đo thời gian một bước; khi kết thúc, phát sự kiện cho sink (nếu bật).

    Gần như miễn phí khi trace tắt. Bước lồng nhau được đánh `depth` để hiển thị thụt lề.
    """
    s = Step(name)
    depth = _depth.get()
    token = _depth.set(depth + 1)
    start = time.perf_counter()
    try:
        yield s
    finally:
        _depth.reset(token)
        sink = _sink.get()
        if sink is not None:
            sink({
                "name": name,
                "seconds": time.perf_counter() - start,
                "notes": s.notes,
                "depth": depth,
            })


# --------------------------------------------------------------------------- #
# Sink in ra stdout (terminal nơi tiến trình đang chạy, vd server uvicorn)
# --------------------------------------------------------------------------- #
def stdout_sink(event: dict) -> None:
    """In một bước ra stdout dưới dạng JSON NGAY khi hoàn tất (flush để hiện live).

    Mỗi bước = một object JSON {step, duration_ms, notes}. Note nhiều dòng (vd câu Cypher)
    được tách thành MẢNG từng dòng để dễ đọc và copy. Cả khối JSON được thụt lề theo độ sâu.
    """
    notes: list = []
    for note in event["notes"]:
        lines = note.split("\n")
        notes.append(lines[0] if len(lines) == 1 else lines)

    record: dict = {"step": event["name"], "duration_ms": round(event["seconds"] * 1000, 1)}
    if notes:
        record["notes"] = notes

    prefix = "  " * event["depth"]
    text = json.dumps(record, ensure_ascii=False, indent=2)
    print("\n".join(prefix + line for line in text.split("\n")), file=sys.stdout, flush=True)


def enable_stdout():
    """Bật trace, in mỗi bước ra stdout của tiến trình đang chạy. Trả token để reset()."""
    return set_sink(stdout_sink)
