"""CLI tìm kiếm (không cá nhân hóa): câu hỏi tiếng Việt -> kết quả Hotel/Place/Room.

Chạy:
    python -m app.cli.search_cli
Gõ câu hỏi (vd "khách sạn ở Đà Nẵng có view biển"), Enter để tìm.
Gõ 'thoát' / 'q' / Ctrl+C để dừng.

Gợi ý cá nhân hóa nằm ở CLI chính: python main.py
"""

from __future__ import annotations

from neo4j.exceptions import Neo4jError
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from app.cli.format import money, score, stars, txt
from app.core.neo4j_client import close
from app.retrieval.graph_search import generate_cypher, run_plan

console = Console()

_EXIT_WORDS = {"thoát", "thoat", "quit", "exit", "q", ""}
_MAX_RETRIES = 2


def run_query(user_query: str, limit: int = 10) -> tuple[dict, list[dict]]:
    """Sinh Cypher + chạy, tự sửa lỗi; trả (plan đã chạy, kết quả)."""
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
                str(i), txt(h.get("name")), txt(h.get("city")),
                stars(h.get("star_rating")), score(h.get("review_score")),
                txt(h.get("review_count")),
            )
    elif node_type == "Place":
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Địa điểm", style="bold", ratio=3)
        table.add_column("Loại", ratio=2)
        for i, p in enumerate(results, 1):
            table.add_row(str(i), txt(p.get("name")), txt(p.get("type")))
    elif node_type == "Room":
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Phòng", style="bold", ratio=3)
        table.add_column("Giá", justify="right")
        table.add_column("View", ratio=1)
        table.add_column("Giường", ratio=1)
        table.add_column("Sức chứa", justify="center")
        for i, r in enumerate(results, 1):
            table.add_row(
                str(i), txt(r.get("name")), money(r.get("price")),
                txt(r.get("room_view")), txt(r.get("bed_type")),
                txt(r.get("max_occupancy")),
            )
    else:
        keys = [k for k in results[0] if k != "_type"]
        table.add_column("#", style="dim", width=3, justify="right")
        for k in keys:
            table.add_column(k, overflow="fold")
        for i, row in enumerate(results, 1):
            table.add_row(str(i), *[txt(row.get(k)) for k in keys])

    return table


def render(user_query: str, plan: dict, results: list[dict]) -> None:
    console.print()
    console.print(Panel(f"[bold]{user_query}[/]", title="🔎 Câu hỏi", border_style="cyan"))
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


def main() -> None:
    console.print(
        Panel.fit(
            "[bold]OTA Search[/] — tìm kiếm dịch vụ du lịch bằng câu hỏi tiếng Việt\n"
            "[dim]Gõ câu hỏi (vd 'khách sạn ở Đà Nẵng có view biển'). Thoát: 'thoát'.[/]",
            border_style="green",
        )
    )
    try:
        while True:
            query = console.input("\n[bold cyan]🔎 Nhập câu hỏi:[/] ").strip()
            if query.lower() in _EXIT_WORDS:
                break
            try:
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
