"""
Candidate Generation Orchestrator
Nhận RecommendInput → quyết định nguồn nào cần chạy → chạy song song → trả về
list[CandidateHotel] từ tất cả nguồn (chưa merge, chưa rank).

Quy tắc bật nguồn:
  TEMPLATE_SEARCH_API — luôn bật nếu có city (external search API từ template query)
  PERSONALIZATION  — bật nếu user_id không phải guest/anonymous
"""

from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.recommendation.models import RecommendInput, CandidateHotel
from app.recommendation.trace import RecommendTrace
from app.recommendation.candidate_generation.hotel_search.template_search_api import (
    get_template_search_api_candidates,
)
from app.recommendation.candidate_generation.personalization.personalization import (
    get_personalization_candidates,
)

logger = logging.getLogger(__name__)

_ANONYMOUS_PREFIXES = ("guest_", "anonymous_", "anon_")


def _is_anonymous(user_id: str) -> bool:
    uid = user_id.lower()
    return any(uid.startswith(p) for p in _ANONYMOUS_PREFIXES)


def _decide_sources(inp: RecommendInput) -> dict[str, bool]:
    city = inp.session_context.destination
    use_template_search = bool(city)
    use_personal = bool(city) and not _is_anonymous(inp.user_id)
    return {
        "template_search_api": use_template_search,
        "personalization": use_personal,
    }


def generate_candidates(
    inp: RecommendInput,
    trace: RecommendTrace | None = None,
) -> list[CandidateHotel]:
    """
    Chạy các nguồn candidate.
    trace=True → chạy tuần tự và in log từng nguồn; mặc định chạy song song.
    """
    sources = _decide_sources(inp)

    if trace and trace.enabled:
        trace.section("② ORCHESTRATOR — chọn nguồn")
        trace.step("destination", inp.session_context.destination)
        trace.step("user_id", inp.user_id)
        for name, on in sources.items():
            reason = "BẬT" if on else "TẮT"
            why = ""
            if name == "personalization" and not on:
                why = " (guest/anonymous hoặc thiếu destination)"
            elif not on:
                why = " (thiếu destination)"
            trace.info(f"{name}: {reason}{why}")

    if not any(sources.values()):
        if trace and trace.enabled:
            trace.info("Không có nguồn nào được bật → return []")
        logger.warning("[Orchestrator] Không có nguồn nào được bật.")
        return []

    all_candidates: list[CandidateHotel] = []

    if trace and trace.enabled:
        if sources["template_search_api"]:
            trace.section("③ TEMPLATE SEARCH API")
            results = get_template_search_api_candidates(inp, trace=trace)
            trace.candidates("template_search_api", results)
            all_candidates.extend(results)

        if sources["personalization"]:
            trace.section("④ PERSONALIZATION (Neo4j unified Cypher)")
            results = get_personalization_candidates(inp, trace=trace)
            trace.candidates("personalization", results)
            all_candidates.extend(results)

        return all_candidates

    logger.info(
        "[Orchestrator] Sources bật: %s",
        [s for s, on in sources.items() if on],
    )

    tasks: dict[str, callable] = {}
    if sources["template_search_api"]:
        tasks["template_search_api"] = lambda: get_template_search_api_candidates(inp)
    if sources["personalization"]:
        tasks["personalization"] = lambda: get_personalization_candidates(inp)

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                results = future.result()
                logger.info("[Orchestrator][%s] Nhận %d candidates.", source_name, len(results))
                all_candidates.extend(results)
            except Exception as exc:
                logger.error("[Orchestrator][%s] Lỗi: %s", source_name, exc)

    return all_candidates
