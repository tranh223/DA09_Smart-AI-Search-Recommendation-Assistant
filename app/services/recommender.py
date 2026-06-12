"""Gợi ý khách sạn cá nhân hóa: dựa trên hồ sơ User trong graph -> top 5 + lý do.

Luồng:
    user_id (+ điều kiện tùy chọn)
        -> [lấy hồ sơ: sở thích + đặc điểm + lịch sử đặt]
        -> [lấy khách sạn ứng viên]
              · không điều kiện: KS khớp sở thích, chưa từng đặt
              · có điều kiện: search lọc CỨNG trước, rồi gắn thông tin cá nhân hóa
        -> [GPT-4o chọn TOP 5 + giải thích vì sao phù hợp]
"""

from __future__ import annotations

import json

from app.config import CANDIDATE_LIMIT
from app.core.llm_client import OPENAI_MODEL, get_openai
from app.core.neo4j_client import run_cypher
from app.retrieval.graph_search import search


# --------------------------------------------------------------------------- #
# Lấy dữ liệu từ graph
# --------------------------------------------------------------------------- #
def get_user_profile(user_id: str) -> dict | None:
    """Lấy hồ sơ người dùng: sở thích (tags), đặc điểm, lịch sử đặt phòng."""
    rows = run_cypher(
        """
        MATCH (u:User {user_id: $uid})
        OPTIONAL MATCH (u)-[:INTERESTED_IN]->(it:Tag)
        OPTIONAL MATCH (u)-[:HAS_FEATURES]->(f:UserFeature)
        OPTIONAL MATCH (u)-[:BOOKED]->(bh:Hotel)
        RETURN u.name AS name, u.nationality AS nationality,
               collect(DISTINCT it.name) AS interests,
               collect(DISTINCT {category: f.category, name: f.name}) AS features,
               collect(DISTINCT {name: bh.name, city: bh.city}) AS booked
        """,
        {"uid": user_id},
    )
    if not rows or rows[0]["name"] is None and not rows[0]["interests"]:
        # Phân biệt user không tồn tại với user tồn tại nhưng thiếu dữ liệu.
        exists = run_cypher(
            "MATCH (u:User {user_id: $uid}) RETURN count(u) AS c", {"uid": user_id}
        )[0]["c"]
        if not exists:
            return None

    row = rows[0]
    return {
        "user_id": user_id,
        "name": row.get("name"),
        "nationality": row.get("nationality"),
        "interests": [t for t in row.get("interests", []) if t],
        "features": [f for f in row.get("features", []) if f.get("name")],
        "booked": [b for b in row.get("booked", []) if b.get("name")],
    }


def get_candidates(user_id: str, limit: int = CANDIDATE_LIMIT) -> list[dict]:
    """Khách sạn ứng viên: khớp sở thích của user, chưa từng đặt, kèm thông tin xếp hạng."""
    return run_cypher(
        """
        MATCH (u:User {user_id: $uid})-[:INTERESTED_IN]->(it:Tag)
        WITH u, collect(DISTINCT it.name) AS interests
        MATCH (h:Hotel)-[:HAS_TAG]->(t:Tag)
        WHERE t.name IN interests AND NOT (u)-[:BOOKED]->(h)
        WITH h, count(DISTINCT t.name) AS match_count,
             collect(DISTINCT t.name) AS matched_tags
        OPTIONAL MATCH (h)-[:HAS_ROOM]->(r:Room) WHERE r.price IS NOT NULL
        WITH h, match_count, matched_tags, min(r.price) AS min_price
        RETURN h.hotel_id AS hotel_id, h.name AS name, h.city AS city,
               h.star_rating AS star_rating, h.review_score AS review_score,
               h.review_count AS review_count, min_price, match_count, matched_tags
        ORDER BY match_count DESC, h.review_score DESC
        LIMIT $limit
        """,
        {"uid": user_id, "limit": limit},
    )


def _candidates_from_query(user_id: str, query: str) -> list[dict]:
    """Lọc CỨNG khách sạn theo điều kiện (vd 'Nha Trang có view biển') qua search,
    rồi gắn thông tin cá nhân hóa (tag khớp sở thích, giá) để xếp hạng.

    search() chỉ đóng vai trò lấy candidate; ưu tiên/giải thích do hồ sơ user lo.
    """
    results = search(query, limit=CANDIDATE_LIMIT)
    hotel_ids = [
        r["hotel_id"] for r in results
        if r.get("_type") == "Hotel" and r.get("hotel_id") is not None
    ]
    if not hotel_ids:
        return []
    return get_candidates_for_hotels(user_id, hotel_ids)


def get_candidates_for_hotels(user_id: str, hotel_ids: list[int]) -> list[dict]:
    """Với một tập hotel_id (đã lọc cứng), tính thông tin cá nhân hóa so với user.

    Trả mỗi KS kèm: tag khớp sở thích của user, số tag khớp, giá phòng thấp nhất.
    Loại các KS user đã từng đặt. Giữ thứ tự khớp nhiều sở thích -> điểm cao.
    """
    return run_cypher(
        """
        MATCH (u:User {user_id: $uid})
        OPTIONAL MATCH (u)-[:INTERESTED_IN]->(it:Tag)
        WITH u, collect(DISTINCT it.name) AS interests
        MATCH (h:Hotel) WHERE h.hotel_id IN $ids AND NOT (u)-[:BOOKED]->(h)
        OPTIONAL MATCH (h)-[:HAS_TAG]->(t:Tag) WHERE t.name IN interests
        WITH h, collect(DISTINCT t.name) AS matched_tags
        OPTIONAL MATCH (h)-[:HAS_ROOM]->(r:Room) WHERE r.price IS NOT NULL
        WITH h, matched_tags, min(r.price) AS min_price
        RETURN h.hotel_id AS hotel_id, h.name AS name, h.city AS city,
               h.star_rating AS star_rating, h.review_score AS review_score,
               h.review_count AS review_count, min_price,
               size(matched_tags) AS match_count, matched_tags
        ORDER BY match_count DESC, h.review_score DESC
        """,
        {"uid": user_id, "ids": hotel_ids},
    )


# --------------------------------------------------------------------------- #
# Gọi GPT-4o chọn top 5 + giải thích
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = """\
Bạn là CHUYÊN GIA TƯ VẤN KHÁCH SẠN CAO CẤP, tinh tế và thấu hiểu khách hàng — như một
concierge riêng đã quen gu của họ. Nhiệm vụ: từ HỒ SƠ người dùng (sở thích, ngân sách,
thói quen, kiểu du khách, lịch sử đặt phòng) và DANH SÁCH khách sạn ứng viên (kèm tag khớp
sở thích, giá phòng thấp nhất, hạng sao, điểm đánh giá), chọn TOP 5 khách sạn PHÙ HỢP NHẤT
và viết lý do thuyết phục, khiến khách thấy "đúng gu mình".

NGUYÊN TẮC CHỌN:
- CHỈ chọn trong danh sách ứng viên (dùng đúng hotel_id và name đã cho). Tuyệt đối KHÔNG bịa
  khách sạn hay bịa tiện nghi không có trong dữ liệu.
- Xếp hạng theo độ phù hợp với hồ sơ giảm dần; ưu tiên khách sạn vừa khớp nhiều sở thích,
  vừa hợp ngân sách, vừa có điểm đánh giá tốt.
- 5 lý do phải KHÁC NHAU về góc nhìn — đừng lặp lại cùng một mô-típ cho mọi khách sạn.

CÁCH VIẾT "reason" (tiếng Việt, giọng chuyên gia, ấm áp, tự tin, 2-3 câu):
- Mở đầu bằng một ĐIỂM NHẤN cá nhân hóa, gọi thẳng vào gu của khách (vd "Đúng gu yên tĩnh
  và riêng tư của anh/chị:" hoặc "Nếu anh/chị mê không gian sang trọng ven biển:").
- Nêu 2-3 lý do CỤ THỂ, lấy TỪ DỮ LIỆU thật: tiện nghi khớp sở thích (dẫn đúng tên tag),
  mức giá so với ngân sách của khách, điểm đánh giá/hạng sao, hay nét tương đồng với nơi họ
  từng đặt. Biến mỗi dữ kiện thành LỢI ÍCH cho khách (vd không chỉ "có hồ bơi" mà "hồ bơi để
  thư giãn sau ngày dài").
- Kết bằng một câu khơi gợi cảm giác trải nghiệm, ngắn gọn và tinh tế.

VĂN PHONG:
- Tự nhiên, sang trọng, đáng tin — như tư vấn viên thật, KHÔNG sáo rỗng, KHÔNG liệt kê khô khan.
- Không dùng emoji, không markdown, không phóng đại quá mức; mọi khẳng định phải bám dữ liệu.
- Xưng hô lịch sự, trung tính ("anh/chị" hoặc "bạn"), nhất quán trong cả 5 lý do.
"""

_RESPONSE_SCHEMA = {
    "name": "recommendations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hotel_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["hotel_id", "name", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["recommendations"],
        "additionalProperties": False,
    },
}


def _format_profile(profile: dict) -> str:
    feats: dict[str, list[str]] = {}
    for f in profile["features"]:
        feats.setdefault(f["category"], []).append(f["name"])
    feat_lines = "; ".join(f"{k}: {', '.join(sorted(set(v)))}" for k, v in feats.items())
    booked = "; ".join(f"{b['name']} ({b.get('city')})" for b in profile["booked"]) or "(chưa có)"
    interests = ", ".join(sorted(set(profile["interests"]))) or "(chưa có)"
    return (
        f"Tên: {profile.get('name') or '(ẩn danh)'} | Quốc tịch: {profile.get('nationality') or '?'}\n"
        f"Đặc điểm: {feat_lines or '(không có)'}\n"
        f"Sở thích (tiện nghi quan tâm): {interests}\n"
        f"Đã từng đặt: {booked}"
    )


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        price = f"{int(c['min_price']):,}".replace(",", ".") + "đ" if c.get("min_price") else "?"
        matched = ", ".join(c.get("matched_tags", [])[:8])
        lines.append(
            f"- id={c['hotel_id']} | {c['name']} | {c.get('city')} | "
            f"{c.get('star_rating')}★ | điểm {c.get('review_score')} | giá từ {price} | "
            f"khớp {c['match_count']} sở thích: {matched}"
        )
    return "\n".join(lines)


def recommend(user_id: str, query: str | None = None, top_k: int = 5) -> dict:
    """Trả về gợi ý cá nhân hóa cho user_id.

    - Không có `query`: lấy ứng viên theo sở thích của user (khớp tag, chưa từng đặt).
    - Có `query` (vd "khách sạn ở Nha Trang có view biển"): search lọc CỨNG theo điều
      kiện trước, rồi cá nhân hóa để xếp hạng + giải thích trong số đó.

    Kết quả:
        {
            "profile": {...},
            "query": <câu điều kiện hoặc None>,
            "recommendations": [
                {"rank", "hotel_id", "name", "city", "star_rating",
                 "review_score", "min_price", "reason"}, ...
            ]
        }
    Raise ValueError nếu user không tồn tại hoặc không đủ dữ liệu để gợi ý.
    """
    profile = get_user_profile(user_id)
    if profile is None:
        raise ValueError(f"Không tìm thấy user '{user_id}'.")
    if not profile["interests"]:
        raise ValueError(f"User '{user_id}' chưa có sở thích (INTERESTED_IN) để gợi ý.")

    if query:
        candidates = _candidates_from_query(user_id, query)
        if not candidates:
            raise ValueError(f"Không có khách sạn nào khớp điều kiện '{query}'.")
    else:
        candidates = get_candidates(user_id)
        if not candidates:
            raise ValueError(f"Không có khách sạn ứng viên phù hợp cho user '{user_id}'.")

    cand_by_id = {c["hotel_id"]: c for c in candidates}

    constraint_note = (
        f"Tất cả khách sạn ứng viên dưới đây ĐÃ thỏa điều kiện người dùng yêu cầu: "
        f'"{query}". Hãy xếp hạng theo độ phù hợp với HỒ SƠ và giải thích.\n\n'
        if query else ""
    )
    user_content = (
        f"HỒ SƠ NGƯỜI DÙNG:\n{_format_profile(profile)}\n\n"
        f"{constraint_note}"
        f"DANH SÁCH KHÁCH SẠN ỨNG VIÊN:\n{_format_candidates(candidates)}\n\n"
        f"Hãy chọn TOP {top_k} khách sạn phù hợp nhất và giải thích lý do."
    )

    client = get_openai()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
    )
    data = json.loads(response.choices[0].message.content)

    recs = []
    for rank, rec in enumerate(data.get("recommendations", [])[:top_k], 1):
        cand = cand_by_id.get(rec["hotel_id"], {})
        recs.append({
            "rank": rank,
            "hotel_id": rec["hotel_id"],
            "name": cand.get("name", rec.get("name")),
            "city": cand.get("city"),
            "star_rating": cand.get("star_rating"),
            "review_score": cand.get("review_score"),
            "review_count": cand.get("review_count"),
            "min_price": cand.get("min_price"),
            "reason": rec["reason"],
        })

    return {"profile": profile, "query": query, "recommendations": recs}
