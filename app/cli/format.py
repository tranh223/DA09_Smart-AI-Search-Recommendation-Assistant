"""Hàm định dạng giá trị dùng chung cho các CLI (trả chuỗi có markup của rich)."""

from __future__ import annotations


def money(v) -> str:
    if v is None:
        return "[dim]—[/]"
    try:
        return f"{int(v):,}".replace(",", ".") + "đ"
    except (ValueError, TypeError):
        return str(v)


def stars(v) -> str:
    if v is None:
        return "[dim]—[/]"
    return f"[yellow]{v:g}★[/]"


def score(v) -> str:
    if v is None:
        return "[dim]—[/]"
    color = "green" if v >= 9 else "cyan" if v >= 8 else "white"
    return f"[{color}]{v:g}[/]"


def txt(v) -> str:
    return "[dim]—[/]" if v in (None, "") else str(v)
