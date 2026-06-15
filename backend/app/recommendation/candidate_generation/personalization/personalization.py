"""
PERSONALIZATION Candidate Generator
Input : RecommendInput  (user_id + session_context.destination)
Output: list[CandidateHotel]  source = "personalization"

Dùng một Cypher template thống nhất kết hợp 3 yếu tố:
  - Demographic Similarity  (UserFeature, weight 0.3)
  - Cosine Interest         (INTERESTED_IN × HAS_TAG, weight 0.4)
  - Collaborative Filtering (BOOKED overlap, weight 0.3)
"""

from __future__ import annotations
import logging

from neo4j_client import run_read_query
from app.recommendation.models import RecommendInput, CandidateHotel
from app.recommendation.trace import RecommendTrace

logger = logging.getLogger(__name__)

# ── Unified Cypher Template ───────────────────────────────────────────────────

_CYPHER_PERSONALIZATION = """
// 1. Lấy thông tin user, các phân khúc (UserFeature) và top sở thích (decayed Tag)
MATCH (u:User {user_id: $user_id})
OPTIONAL MATCH (u)-[:HAS_FEATURES]->(f:UserFeature)
WITH u, collect(distinct f.name) AS userFeatures
OPTIONAL MATCH (u)-[i:INTERESTED_IN]->(t:Tag)
WITH u, userFeatures, t,
     i.count * exp(-0.05 * duration.inDays(date(i.last_interaction), date()).days) AS decayedScore
ORDER BY decayedScore DESC
WITH u, userFeatures, collect({tag: t.name, score: decayedScore}) AS userInterests

// 2. Duyệt qua các khách sạn trong city để tính toán 3 yếu tố gợi ý
MATCH (hotel:Hotel)
WHERE toLower(hotel.city) CONTAINS toLower($city)

// --- Yếu tố 1: Demographic Similarity (Nhân khẩu học) ---
OPTIONAL MATCH (other:User)-[:BOOKED]->(hotel)
WHERE other <> u
OPTIONAL MATCH (other)-[:HAS_FEATURES]->(f:UserFeature)
WHERE f.name IN userFeatures
WITH u, userFeatures, userInterests, hotel,
     count(distinct f) AS sharedFeaturesCount,
     count(distinct other) AS otherUsersCount

// --- Yếu tố 2: Cosine Interest Similarity (Độ tương đồng sở thích) ---
OPTIONAL MATCH (t:Tag)<-[h:HAS_TAG]-(hotel)
WITH u, userFeatures, userInterests, hotel, sharedFeaturesCount, otherUsersCount, t, h
UNWIND userInterests AS ui
WITH u, userFeatures, userInterests, hotel, sharedFeaturesCount, otherUsersCount, t, h, ui
WHERE t.name = ui.tag
WITH u, userFeatures, userInterests, hotel, sharedFeaturesCount, otherUsersCount,
     sum(ui.score * h.weight) AS dotProduct,
     sqrt(sum(ui.score * ui.score)) * sqrt(sum(h.weight * h.weight)) AS normInterest

// --- Yếu tố 3: Collaborative Filtering (Lịch sử đặt phòng trùng lặp) ---
OPTIONAL MATCH (u)-[:BOOKED]->(sharedHotel:Hotel)<-[:BOOKED]-(otherCollaborative:User)-[:BOOKED]->(hotel)
WHERE otherCollaborative <> u AND NOT (u)-[:BOOKED]->(hotel)
WITH u, userFeatures, userInterests, hotel, sharedFeaturesCount, otherUsersCount,
     dotProduct, normInterest,
     count(distinct sharedHotel) AS bookingOverlapCount,
     count(distinct otherCollaborative) AS otherUsersCollaborativeCount

// 3. Chuẩn hóa và tổng hợp điểm số cuối cùng
WITH u, userFeatures, userInterests, hotel,
     1.0 * sharedFeaturesCount / (sharedFeaturesCount + 2.0) AS demoScore,
     CASE WHEN normInterest > 0 THEN dotProduct / normInterest ELSE 0.0 END AS interestScore,
     1.0 * bookingOverlapCount / (bookingOverlapCount + 2.0) AS collaborativeScore
WITH u, userFeatures, userInterests, hotel, demoScore, interestScore, collaborativeScore,
     (demoScore * 0.3 + interestScore * 0.4 + collaborativeScore * 0.3) AS finalScore
WHERE finalScore > 0
RETURN
  u.user_id          AS userId,
  u.name             AS userName,
  userFeatures       AS userSegments,
  userInterests[..5] AS top5Interests,
  hotel.hotel_id     AS hotelId,
  hotel.name         AS hotelName,
  hotel.city         AS city,
  hotel.review_score AS reviewScore,
  demoScore,
  interestScore,
  collaborativeScore,
  finalScore
ORDER BY finalScore DESC
LIMIT $limit
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_candidates(rows: list[dict]) -> list[CandidateHotel]:
    candidates = []
    for row in rows:
        top_interests = row.get("top5Interests") or []
        matched_tags = [
            item["tag"] for item in top_interests
            if isinstance(item, dict) and item.get("tag")
        ]
        paths = [f"Hotel -[:HAS_TAG]-> Tag({tag})" for tag in matched_tags]

        demo = row.get("demoScore") or 0.0
        interest = row.get("interestScore") or 0.0
        collab = row.get("collaborativeScore") or 0.0

        reason_parts = []
        if demo > 0:
            reason_parts.append(f"nhân khẩu học ({demo:.2f})")
        if interest > 0:
            tags_str = ", ".join(matched_tags[:3]) or "sở thích"
            reason_parts.append(f"sở thích [{tags_str}] ({interest:.2f})")
        if collab > 0:
            reason_parts.append(f"cộng tác ({collab:.2f})")

        candidates.append(
            CandidateHotel(
                hotel_id=int(row["hotelId"]),
                hotel_name=row.get("hotelName"),
                source="personalization",
                score=float(row.get("finalScore") or 0.0),
                matched_paths=paths,
                reason="Khớp " + " + ".join(reason_parts) if reason_parts else "personalization score",
                metadata={
                    "review_score": row.get("reviewScore"),
                    "city": row.get("city"),
                    "demo_score": demo,
                    "interest_score": interest,
                    "collaborative_score": collab,
                    "user_segments": row.get("userSegments") or [],
                    "top5_interests": top_interests,
                    "strategy": "unified_personalization",
                },
            )
        )
    return candidates


# ── Public API ────────────────────────────────────────────────────────────────

def get_personalization_candidates(
    inp: RecommendInput,
    trace: RecommendTrace | None = None,
) -> list[CandidateHotel]:
    """
    Chạy unified Cypher template → trả về top-N CandidateHotel sorted by finalScore DESC.
    """
    city = inp.session_context.destination
    if not city:
        if trace and trace.enabled:
            trace.info("Thiếu destination → bỏ qua personalization")
        logger.info("[Personalization] Không có destination → bỏ qua.")
        return []

    params = {
        "user_id": inp.user_id,
        "city": city,
        "limit": inp.limit_per_source,
    }

    if trace and trace.enabled:
        trace.step("Neo4j unified Cypher params", params)
        trace.info("3 yếu tố: demographic(0.3) + interest(0.4) + collaborative(0.3)")

    try:
        rows = run_read_query(_CYPHER_PERSONALIZATION, params)
        candidates = _rows_to_candidates(rows)
        if trace and trace.enabled and rows:
            top = rows[0]
            trace.info(
                f"Top result: {top.get('hotelName')} | finalScore={top.get('finalScore'):.4f} | "
                f"demo={top.get('demoScore'):.2f} interest={top.get('interestScore'):.2f} "
                f"collab={top.get('collaborativeScore'):.2f}"
            )
        logger.info("[Personalization] Trả về %d candidates cho user=%s tại %s.",
                    len(candidates), inp.user_id, city)
        return candidates
    except Exception as exc:
        if trace and trace.enabled:
            trace.info(f"Lỗi: {exc}")
        logger.warning("[Personalization] Lỗi truy vấn: %s", exc)
        return []
