"""
PERSONALIZATION Candidate Generator
Input : RecommendInput  (user_id + session_context.destination)
Output: list[CandidateHotel]  source = "personalization"

Chiến lược hai tầng — chọn tự động theo lịch sử booking của user:

  Tầng 1 — User-first Collaborative Filtering (user có booking history):
    - Tìm user tương đồng qua booking overlap + UserFeature Jaccard
    - Lấy hotel các user tương đồng đã đặt, loại hotel user hiện tại đã biết
    - Boost thêm bằng interest (INTERESTED_IN × HAS_TAG) của user hiện tại
    - Điểm cuối: 0.70 * collaborativeScore + 0.20 * interestFit + 0.10 * reviewScore

  Tầng 2 — Demographic Fallback (user chưa có booking hoặc ít booking):
    - Tìm user cùng phân khúc UserFeature trong city
    - Lấy hotel mà nhóm user đó đã đặt
    - Điểm cuối: 0.60 * demographicScore + 0.30 * interestFit + 0.10 * reviewScore
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j_client import run_read_query  # neo4j_client lives at backend/ root in sys.path
from app.recommendation.models import RecommendInput, CandidateHotel
from app.recommendation.trace import RecommendTrace

logger = logging.getLogger(__name__)

# Số booking tối thiểu để dùng collaborative, dưới ngưỡng này fallback demographic
_MIN_BOOKING_COUNT_FOR_COLLABORATIVE = 1

# ── Tầng 1: User-first Collaborative Filtering ────────────────────────────────
#
# Luồng: User → shared BOOKED hotels → similar users → their other BOOKEDs → target hotels
#        Boost target hotel score bằng interest fit của user hiện tại.
#
# user-user similarity = 0.65 * bookingOverlapScore + 0.35 * featureJaccardScore
# finalScore           = 0.70 * collaborativeScore  + 0.20 * interestFit + 0.10 * reviewScore

_CYPHER_COLLABORATIVE = """
// Bước 0: Kiểm tra user tồn tại
MATCH (u:User {user_id: $user_id})

// Bước 1: Thu thập danh sách hotel user đã đặt (dùng để loại trừ)
OPTIONAL MATCH (u)-[:BOOKED]->(alreadyBooked:Hotel)
WITH u, collect(DISTINCT alreadyBooked.hotel_id) AS bookedHotelIds

// Bước 2: Interest vector của user hiện tại (time-decay lambda=0.05)
OPTIONAL MATCH (u)-[iRel:INTERESTED_IN]->(iTag:Tag)
WITH u, bookedHotelIds,
     collect({
       name:     iTag.name,
       category: iTag.category,
       score:    coalesce(iRel.count, 1) *
                 exp(-0.05 * duration.inDays(
                   date(coalesce(iRel.last_interaction, toString(date()))),
                   date()
                 ).days)
     }) AS userInterests

// Bước 3: Feature set của user hiện tại
OPTIONAL MATCH (u)-[:HAS_FEATURES]->(uf:UserFeature)
WITH u, bookedHotelIds, userInterests,
     collect(DISTINCT uf.name) AS userFeatureNames,
     count(DISTINCT uf)        AS userFeatureCount

// Bước 4: Tìm similar users qua booking overlap
MATCH (u)-[:BOOKED]->(sharedHotel:Hotel)<-[:BOOKED]-(other:User)
WHERE other <> u
WITH u, bookedHotelIds, userInterests, userFeatureNames, userFeatureCount, other,
     count(DISTINCT sharedHotel) AS bookingOverlap

// Bước 5: Tính Jaccard similarity trên UserFeature
OPTIONAL MATCH (other)-[:HAS_FEATURES]->(of:UserFeature)
WITH u, bookedHotelIds, userInterests, userFeatureNames, userFeatureCount,
     other, bookingOverlap,
     count(DISTINCT of)                                                         AS otherFeatureCount,
     count(DISTINCT CASE WHEN of.name IN userFeatureNames THEN of END)         AS sharedFeatureCount

WITH u, bookedHotelIds, userInterests, other, bookingOverlap,
     CASE
       WHEN (userFeatureCount + otherFeatureCount - sharedFeatureCount) > 0
       THEN 1.0 * sharedFeatureCount / (userFeatureCount + otherFeatureCount - sharedFeatureCount)
       ELSE 0.0
     END AS featureJaccard

// Bước 6: Tổng hợp user-user similarity score
WITH u, bookedHotelIds, userInterests, other,
     bookingOverlap,
     featureJaccard,
     (
       0.65 * (1.0 * bookingOverlap / (bookingOverlap + 2.0)) +
       0.35 * featureJaccard
     ) AS userSimilarity
WHERE userSimilarity > 0.0

// Bước 7: Lấy hotel mà similar users đã đặt, lọc city và loại hotel user đã biết
MATCH (other)-[:BOOKED]->(hotel:Hotel)
WHERE toLower(hotel.city) CONTAINS toLower($city)
  AND NOT hotel.hotel_id IN bookedHotelIds

// Bước 8: Gom user signals về theo hotel TRƯỚC KHI join tags
//   → other vẫn còn trong scope ở bước này, sau đây sẽ không cần nữa
WITH hotel, userInterests,
     sum(userSimilarity)   AS collaborativeScore,
     max(userSimilarity)   AS bestSimilarUserScore,
     count(DISTINCT other) AS similarUserCount

// Bước 9: Tính interest fit từ hotel tags (join sau khi đã có collaborative aggregates)
OPTIONAL MATCH (hotel)-[htRel:HAS_TAG]->(htTag:Tag)
WITH hotel, collaborativeScore, bestSimilarUserScore, similarUserCount, userInterests,
     htTag, htRel
WITH hotel, collaborativeScore, bestSimilarUserScore, similarUserCount,
     sum(
       CASE
         WHEN htTag IS NOT NULL
              AND any(ui IN userInterests WHERE ui.name = htTag.name AND ui.category = htTag.category)
         THEN coalesce(htRel.weight, 0.0) *
              head([ui IN userInterests WHERE ui.name = htTag.name | ui.score])
         ELSE 0.0
       END
     ) AS rawInterestFit,
     collect(DISTINCT CASE WHEN htTag IS NOT NULL THEN htTag.name ELSE null END)[..8] AS matchedTags

// Bước 10: Chuẩn hóa interestFit và tính finalScore
WITH hotel, collaborativeScore, bestSimilarUserScore, similarUserCount, matchedTags,
     CASE
       WHEN rawInterestFit > 0 THEN rawInterestFit / (rawInterestFit + 5.0)
       ELSE 0.0
     END AS interestFit

WITH hotel, collaborativeScore, bestSimilarUserScore, similarUserCount, interestFit, matchedTags,
     (
       0.70 * (collaborativeScore / (collaborativeScore + 3.0)) +
       0.20 * interestFit +
       0.10 * coalesce(hotel.review_score, 0.0) / 10.0
     ) AS finalScore
WHERE finalScore > 0

RETURN
  hotel.hotel_id          AS hotelId,
  hotel.name              AS hotelName,
  hotel.city              AS city,
  hotel.review_score      AS reviewScore,
  collaborativeScore,
  bestSimilarUserScore,
  similarUserCount,
  interestFit,
  matchedTags,
  finalScore
ORDER BY finalScore DESC, reviewScore DESC
LIMIT $limit
"""

# ── Tầng 2: Demographic Fallback ──────────────────────────────────────────────
#
# Luồng: User → shared UserFeature → similar segment users → their BOOKEDs → target hotels
#        Boost thêm bằng interest fit để có độ cá nhân hóa tốt hơn.
#
# finalScore = 0.60 * demographicScore + 0.30 * interestFit + 0.10 * reviewScore

_CYPHER_DEMOGRAPHIC_FALLBACK = """
MATCH (u:User {user_id: $user_id})

// Bước 1: Interest vector của user (time-decay)
OPTIONAL MATCH (u)-[iRel:INTERESTED_IN]->(iTag:Tag)
WITH u,
     collect({
       name:     iTag.name,
       category: iTag.category,
       score:    coalesce(iRel.count, 1) *
                 exp(-0.05 * duration.inDays(
                   date(coalesce(iRel.last_interaction, toString(date()))),
                   date()
                 ).days)
     }) AS userInterests

// Bước 2: Tìm user cùng phân khúc UserFeature và hotel họ đã đặt trong city
MATCH (u)-[:HAS_FEATURES]->(f:UserFeature)<-[:HAS_FEATURES]-(other:User)
WHERE other <> u
MATCH (other)-[:BOOKED]->(hotel:Hotel)
WHERE toLower(hotel.city) CONTAINS toLower($city)
  AND NOT (u)-[:BOOKED]->(hotel)

// Bước 3: Gom điểm theo hotel TRƯỚC KHI join tags
WITH hotel, userInterests,
     count(DISTINCT f)     AS sharedFeatureCount,
     count(DISTINCT other) AS similarUserCount

// Bước 4: Tính interest fit từ hotel tags
OPTIONAL MATCH (hotel)-[htRel:HAS_TAG]->(htTag:Tag)
WITH hotel, sharedFeatureCount, similarUserCount, userInterests,
     htTag, htRel
WITH hotel, sharedFeatureCount, similarUserCount,
     sum(
       CASE
         WHEN htTag IS NOT NULL
              AND any(ui IN userInterests WHERE ui.name = htTag.name AND ui.category = htTag.category)
         THEN coalesce(htRel.weight, 0.0) *
              head([ui IN userInterests WHERE ui.name = htTag.name | ui.score])
         ELSE 0.0
       END
     ) AS rawInterestFit,
     collect(DISTINCT CASE WHEN htTag IS NOT NULL THEN htTag.name ELSE null END)[..8] AS matchedTags

WITH hotel, sharedFeatureCount, similarUserCount, matchedTags,
     CASE
       WHEN rawInterestFit > 0 THEN rawInterestFit / (rawInterestFit + 5.0)
       ELSE 0.0
     END AS interestFit

// Bước 5: Tính finalScore
WITH hotel, sharedFeatureCount, similarUserCount, interestFit, matchedTags,
     (
       0.60 * (1.0 * sharedFeatureCount / (sharedFeatureCount + 3.0)) +
       0.30 * interestFit +
       0.10 * coalesce(hotel.review_score, 0.0) / 10.0
     ) AS finalScore
WHERE finalScore > 0

RETURN
  hotel.hotel_id          AS hotelId,
  hotel.name              AS hotelName,
  hotel.city              AS city,
  hotel.review_score      AS reviewScore,
  sharedFeatureCount,
  similarUserCount,
  interestFit,
  matchedTags,
  0.0                     AS collaborativeScore,
  0.0                     AS bestSimilarUserScore,
  finalScore
ORDER BY finalScore DESC, reviewScore DESC
LIMIT $limit
"""

# ── Query kiểm tra booking count ──────────────────────────────────────────────

_CYPHER_CHECK_BOOKING_COUNT = """
MATCH (u:User {user_id: $user_id})-[:BOOKED]->(h:Hotel)
RETURN count(h) AS bookingCount
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_booking_count(user_id: str) -> int:
    """Lấy số lượng hotel user đã đặt. Trả 0 nếu lỗi."""
    try:
        rows = run_read_query(_CYPHER_CHECK_BOOKING_COUNT, {"user_id": user_id})
        if rows:
            return int(rows[0].get("bookingCount") or 0)
    except Exception as exc:
        logger.debug("[Personalization] Không đếm được booking của user %s: %s", user_id, exc)
    return 0


def _rows_to_candidates(rows: list[dict[str, Any]], strategy: str) -> list[CandidateHotel]:
    candidates: list[CandidateHotel] = []
    for row in rows:
        hotel_id_raw = row.get("hotelId")
        if hotel_id_raw is None:
            continue

        try:
            hotel_id = int(hotel_id_raw)
        except (TypeError, ValueError):
            logger.debug("[Personalization] Bỏ qua row có hotelId không hợp lệ: %r", hotel_id_raw)
            continue

        final_score = float(row.get("finalScore") or 0.0)
        review_score = row.get("reviewScore")
        collab_score = float(row.get("collaborativeScore") or 0.0)
        best_sim = float(row.get("bestSimilarUserScore") or 0.0)
        similar_count = int(row.get("similarUserCount") or 0)
        shared_features = int(row.get("sharedFeatureCount") or 0)
        interest_fit = float(row.get("interestFit") or 0.0)
        matched_tags: list[str] = row.get("matchedTags") or []

        paths = [f"Hotel-[:HAS_TAG]->Tag({tag})" for tag in matched_tags[:5]]

        reason_parts: list[str] = []
        if collab_score > 0:
            reason_parts.append(
                f"cộng tác ({similar_count} user tương đồng, sim={best_sim:.2f})"
            )
        if shared_features > 0:
            reason_parts.append(f"nhân khẩu học ({shared_features} đặc trưng chung)")
        if interest_fit > 0:
            tags_preview = ", ".join(matched_tags[:3]) or "sở thích"
            reason_parts.append(f"sở thích [{tags_preview}] (fit={interest_fit:.2f})")

        candidates.append(
            CandidateHotel(
                hotel_id=hotel_id,
                hotel_name=row.get("hotelName"),
                source="personalization",
                score=final_score,
                matched_paths=paths,
                reason="Khớp " + " + ".join(reason_parts) if reason_parts else "personalization score",
                metadata={
                    "review_score": review_score,
                    "city": row.get("city"),
                    "collaborative_score": collab_score,
                    "best_similar_user_score": best_sim,
                    "similar_user_count": similar_count,
                    "shared_feature_count": shared_features,
                    "interest_fit": interest_fit,
                    "matched_tags": matched_tags,
                    "strategy": strategy,
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
    Chọn strategy tự động:
      - Nếu user có >= _MIN_BOOKING_COUNT_FOR_COLLABORATIVE bookings → Collaborative.
      - Ngược lại → Demographic Fallback.

    Cả 2 đều boost thêm interest fit từ INTERESTED_IN × HAS_TAG.
    """
    city = inp.session_context.destination
    if not city:
        if trace and trace.enabled:
            trace.info("Thiếu destination → bỏ qua personalization")
        logger.info("[Personalization] Không có destination → bỏ qua.")
        return []

    # Xác định strategy
    booking_count = _get_booking_count(inp.user_id)
    use_collaborative = booking_count >= _MIN_BOOKING_COUNT_FOR_COLLABORATIVE

    strategy = "collaborative" if use_collaborative else "demographic_fallback"
    cypher = _CYPHER_COLLABORATIVE if use_collaborative else _CYPHER_DEMOGRAPHIC_FALLBACK

    params: dict[str, Any] = {
        "user_id": inp.user_id,
        "city": city,
        "limit": inp.limit_per_source,
    }

    if trace and trace.enabled:
        trace.step("Personalization params", {
            "user_id": inp.user_id,
            "city": city,
            "limit": inp.limit_per_source,
            "booking_count": booking_count,
            "strategy": strategy,
        })
        if use_collaborative:
            trace.info(
                f"Strategy: COLLABORATIVE — user có {booking_count} booking(s). "
                "Luồng: user-first → similar users → hotel họ đặt → boost interest"
            )
        else:
            trace.info(
                f"Strategy: DEMOGRAPHIC FALLBACK — user có {booking_count} booking(s). "
                "Luồng: shared UserFeature → similar segment users → hotel họ đặt → boost interest"
            )

    try:
        rows = run_read_query(cypher, params)
        candidates = _rows_to_candidates(rows, strategy)

        if trace and trace.enabled and rows:
            top = rows[0]
            trace.info(
                f"Top result: {top.get('hotelName')} | "
                f"finalScore={top.get('finalScore', 0):.4f} | "
                f"strategy={strategy} | "
                f"interestFit={top.get('interestFit', 0):.3f} | "
                f"collab={top.get('collaborativeScore', 0):.3f} | "
                f"demo_features={top.get('sharedFeatureCount', 0)}"
            )

        logger.info(
            "[Personalization] strategy=%s | user=%s | city=%s | candidates=%d",
            strategy, inp.user_id, city, len(candidates),
        )
        return candidates

    except Exception as exc:
        if trace and trace.enabled:
            trace.info(f"Lỗi ({strategy}): {exc}")
        logger.warning("[Personalization] Lỗi truy vấn strategy=%s: %s", strategy, exc)
        return []
