"""CLI tương tác: gõ câu hỏi tiếng Việt -> tìm kiếm / gợi ý, hiển thị đẹp mắt (rich).

Chế độ:
    • Tìm kiếm: gõ câu hỏi (vd "khách sạn ở Đà Nẵng có view biển").
    • Gợi ý cá nhân hóa: 'goiy <user_id>' (vd 'goiy user_141').
    • Gợi ý kèm điều kiện: 'goiy <user_id> <câu điều kiện>'.
    • Thoát: 'thoát' / 'q' / Ctrl+C.
"""

from __future__ import annotations

from neo4j.exceptions import Neo4jError
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from app.core.neo4j_client import close
from app.services.recommender import recommend
from app.services.search import generate_cypher, run_plan

console = Console()

_EXIT_WORDS = {"thoát", "thoat", "quit", "exit", "q", ""}
_RECOMMEND_CMDS = ("goiy", "gợi ý", "goi y", "/goiy", "/recommend", "recommend")
_MAX_RETRIES = 2


# --------------------------------------------------------------------------- #
# Định dạng giá trị
# --------------------------------------------------------------------------- #
def _money(v) -> str:
    if v is None:
        return "[dim]—[/]"
    try:
        return f"{int(v):,}".replace(",", ".") + "đ"
    except (ValueError, TypeError):
        return str(v)


def _stars(v) -> str:
    if v is None:
        return "[dim]—[/]"
    return f"[yellow]{v:g}★[/]"


def _score(v) -> str:
    if v is None:
        return "[dim]—[/]"
    color = "green" if v >= 9 else "cyan" if v >= 8 else "white"
    return f"[{color}]{v:g}[/]"


def _txt(v) -> str:
    return "[dim]—[/]" if v in (None, "") else str(v)


# --------------------------------------------------------------------------- #
# Tìm kiếm (kèm retry tự sửa lỗi, đồng thời lấy được câu Cypher đã chạy)
# --------------------------------------------------------------------------- #
def run_query(user_query: str, limit: int = 10) -> tuple[dict, list[dict]]:
    plan = generate_cypher(user_query, limit=limit)
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return plan, run_plan(plan)
        except Neo4jError as exc:
            if attempt == _MAX_RETRIES:
                raise
            plan = generate_cypher(
                user_query, limit=limit, error_feedback=str(exc), prev_cypher=plan["cypher"]
            )
    return plan, []


# --------------------------------------------------------------------------- #
# Hiển thị kết quả tìm kiếm theo loại node
# --------------------------------------------------------------------------- #
def _build_table(results: list[dict]) -> Table:
    node_type = results[0].get("_type", "Unknown")
    table = Table(box=box.ROUNDED, header_style="bold magenta", expand=True)

    if node_type == "Hotel":
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Khách sạn", style="bold", ratio=3)
        table.add_column("Thành phố", ratio=1)
        table.add_column("Hạng", justify="center")
        table.add_column("Điểm", justify="center")
        table.add_column("Lượt ĐG", justify="right")
        for i, h in enumerate(results, 1):
            table.add_row(
                str(i), _txt(h.get("name")), _txt(h.get("city")),
                _stars(h.get("star_rating")), _score(h.get("review_score")),
                _txt(h.get("review_count")),
            )
    elif node_type == "Place":
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Địa điểm", style="bold", ratio=3)
        table.add_column("Loại", ratio=2)
        for i, p in enumerate(results, 1):
            table.add_row(str(i), _txt(p.get("name")), _txt(p.get("type")))
    elif node_type == "Room":
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Phòng", style="bold", ratio=3)
        table.add_column("Giá", justify="right")
        table.add_column("View", ratio=1)
        table.add_column("Giường", ratio=1)
        table.add_column("Sức chứa", justify="center")
        for i, r in enumerate(results, 1):
            table.add_row(
                str(i), _txt(r.get("name")), _money(r.get("price")),
                _txt(r.get("room_view")), _txt(r.get("bed_type")),
                _txt(r.get("max_occupancy")),
            )
    else:
        # Loại node khác: in mọi trường (trừ _type).
        keys = [k for k in results[0] if k != "_type"]
        table.add_column("#", style="dim", width=3, justify="right")
        for k in keys:
            table.add_column(k, overflow="fold")
        for i, row in enumerate(results, 1):
            table.add_row(str(i), *[_txt(row.get(k)) for k in keys])

    return table


def render(user_query: str, plan: dict, results: list[dict]) -> None:
    console.print()
    console.print(Panel(f"[bold]{user_query}[/]", title="🔎 Câu hỏi", border_style="cyan"))

    # Câu Cypher GPT-4o sinh ra (dim, gọn cho demo).
    console.print(
        Panel(
            Syntax(plan["cypher"], "cypher", theme="ansi_dark", word_wrap=True),
            title="Cypher", border_style="dim", title_align="left",
        )
    )

    if not results:
        console.print(Panel("[yellow]Không tìm thấy kết quả nào.[/]", border_style="yellow"))
        return

    node_type = results[0].get("_type", "Unknown")
    label = {"Hotel": "khách sạn", "Place": "địa điểm", "Room": "phòng"}.get(node_type, node_type)
    console.print(f"[bold green]✓ Tìm thấy {len(results)} {label}:[/]")
    console.print(_build_table(results))


# --------------------------------------------------------------------------- #
# Hiển thị gợi ý cá nhân hóa
# --------------------------------------------------------------------------- #
def render_recommendations(user_id: str, result: dict) -> None:
    profile = result["profile"]
    recs = result["recommendations"]

    console.print()
    feats: dict[str, set] = {}
    for f in profile["features"]:
        feats.setdefault(f["category"], set()).add(f["name"])
    feat_str = " | ".join(f"{k}: {', '.join(sorted(v))}" for k, v in feats.items())
    console.print(
        Panel(
            f"[bold]{profile.get('name') or user_id}[/] ([dim]{user_id}[/])\n"
            f"[dim]{feat_str}[/]",
            title="👤 Hồ sơ người dùng", border_style="magenta", title_align="left",
        )
    )

    if not recs:
        console.print(Panel("[yellow]Chưa có gợi ý phù hợp.[/]", border_style="yellow"))
        return

    q = result.get("query")
    suffix = f" [dim](lọc theo: {q})[/]" if q else ""
    console.print(f"[bold green]✨ Top {len(recs)} khách sạn gợi ý cho bạn:[/]{suffix}")
    for r in recs:
        price = _money(r.get("min_price"))
        facts = (
            f"📍 {_txt(r.get('city'))}   {_stars(r.get('star_rating'))}   "
            f"⭐ {_score(r.get('review_score'))}   💰 từ {price}"
        )
        body = f"{facts}\n\n[italic]💡 {r['reason']}[/]"
        console.print(
            Panel(body, title=f"[bold]#{r['rank']}  {r['name']}[/]",
                  border_style="green", title_align="left")
        )


# --------------------------------------------------------------------------- #
# Vòng lặp CLI
# --------------------------------------------------------------------------- #
def _parse_recommend(query: str) -> tuple[str, str | None] | None:
    """Nếu là lệnh gợi ý, trả về (user_id, câu_điều_kiện|None); ngược lại None.

    Cú pháp: 'goiy <user_id> [câu điều kiện]'
    Ví dụ: 'goiy user_141'  /  'goiy user_141 khách sạn ở Nha Trang có view biển'
    """
    low = query.lower()
    for cmd in _RECOMMEND_CMDS:
        if low.startswith(cmd + " "):
            rest = query[len(cmd):].strip()
            parts = rest.split(maxsplit=1)
            if not parts:
                return None
            user_id = parts[0]
            extra = parts[1].strip() if len(parts) > 1 else None
            return user_id, extra
    return None


def main() -> None:
    console.print(
        Panel.fit(
            "[bold]OTA Travel Assistant[/] — tìm kiếm & gợi ý dịch vụ du lịch bằng tiếng Việt\n"
            "[dim]• Tìm kiếm: gõ câu hỏi (vd 'khách sạn ở Đà Nẵng có view biển')\n"
            "• Gợi ý cá nhân hóa: 'goiy <user_id>' (vd 'goiy user_141')\n"
            "• Gợi ý kèm điều kiện: 'goiy <user_id> <câu điều kiện>'\n"
            "   (vd 'goiy user_141 khách sạn ở Nha Trang có view biển')\n"
            "• Thoát: 'thoát' hoặc Ctrl+C[/]",
            border_style="green",
        )
    )
    try:
        while True:
            query = console.input("\n[bold cyan]🔎 Nhập câu hỏi:[/] ").strip()
            if query.lower() in _EXIT_WORDS:
                break

            parsed = _parse_recommend(query)
            try:
                if parsed is not None:
                    user_id, extra = parsed
                    with console.status("[magenta]Đang tạo gợi ý cá nhân hóa...[/]", spinner="dots"):
                        result = recommend(user_id, query=extra, top_k=5)
                    render_recommendations(user_id, result)
                else:
                    with console.status("[cyan]Đang tìm kiếm...[/]", spinner="dots"):
                        plan, results = run_query(query, limit=10)
                    render(query, plan, results)
            except Exception as exc:  # noqa: BLE001 - hiển thị lỗi cho người dùng
                console.print(Panel(f"[red]Lỗi: {exc}[/]", border_style="red"))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        close()
        console.print("\n[dim]Tạm biệt![/]")


if __name__ == "__main__":
    main()
