"""CLI gợi ý khách sạn cá nhân hóa (chức năng chính).

Chạy:
    python main.py
Nhập user_id (vd 'user_141'), tuỳ chọn thêm điều kiện lọc (vd 'ở Nha Trang có
view biển'), hệ trả về top 5 khách sạn kèm lý do phù hợp.

Tìm kiếm thuần (không cá nhân hóa) nằm ở file riêng: app/cli/search_cli.py
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from app.cli.format import money, score, stars, txt
from app.core.neo4j_client import close
from app.services.recommender import recommend

console = Console()

_EXIT_WORDS = {"thoát", "thoat", "quit", "exit", "q", ""}


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
    suffix = f" [dim](theo yêu cầu: {q})[/]" if q else ""
    console.print(f"[bold green]✨ Top {len(recs)} khách sạn gợi ý cho bạn:[/]{suffix}")
    for r in recs:
        facts = (
            f"📍 {txt(r.get('city'))}   {stars(r.get('star_rating'))}   "
            f"⭐ {score(r.get('review_score'))}   💰 từ {money(r.get('min_price'))}"
        )
        body = f"{facts}\n\n[italic]💡 {r['reason']}[/]"
        console.print(
            Panel(body, title=f"[bold]#{r['rank']}  {r['name']}[/]",
                  border_style="green", title_align="left")
        )


def main() -> None:
    console.print(
        Panel.fit(
            "[bold]OTA Travel Assistant[/] — Gợi ý khách sạn cá nhân hóa\n"
            "[dim]• Nhập user_id (vd 'user_141') để nhận top 5 gợi ý + lý do.\n"
            "• Có thể thêm yêu cầu cụ thể ở bước sau (vd 'ở Nha Trang có view biển').\n"
            "• Thoát: 'thoát' hoặc Ctrl+C[/]",
            border_style="green",
        )
    )
    try:
        while True:
            user_id = console.input("\n[bold magenta]👤 Nhập user_id:[/] ").strip()
            if user_id.lower() in _EXIT_WORDS:
                break

            extra = console.input(
                "[cyan]🎯 Yêu cầu của bạn[/] [dim](Enter để bỏ qua):[/] "
            ).strip() or None

            try:
                with console.status("[magenta]Đang tạo gợi ý cá nhân hóa...[/]", spinner="dots"):
                    result = recommend(user_id, query=extra, top_k=5)
                render_recommendations(user_id, result)
            except Exception as exc:  # noqa: BLE001 - hiển thị lỗi cho người dùng
                console.print(Panel(f"[red]Lỗi: {exc}[/]", border_style="red"))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        close()
        console.print("\n[dim]Tạm biệt![/]")


if __name__ == "__main__":
    main()
