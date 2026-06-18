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
from app.core import trace
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


def get_candidates_collaborative(
    user_id: str, cities: list[str] | None = None, limit: int = CANDIDATE_LIMIT
) -> list[dict]:
    """Retrieval theo Collaborative Filtering (user-based, qua co-booking).

    Ý tưởng: tìm "hàng xóm cùng gu" — những user khác từng đặt TRÙNG khách sạn với
    user mục tiêu — rồi lấy các khách sạn họ đã đặt mà user CHƯA từng đặt làm ứng viên::

        (u)-[:BOOKED]->(sharedHotel)<-[:BOOKED]-(other)-[:BOOKED]->(h)

    `cities`: nếu truyền, CHỈ giữ ứng viên thuộc các thành phố này (vd khi khách yêu cầu
    "Đà Nẵng"). Bản thân CF không biết địa điểm — nó đi theo hành vi đặt phòng nên có thể
    trả khách sạn ở mọi nơi; tham số này áp ràng buộc địa điểm lên kết quả. None = không lọc.

    Tín hiệu CF cho mỗi ứng viên `h`:
        · neighbor_count — số hàng xóm KHÁC NHAU cùng đặt h (càng nhiều càng đáng tin)
        · overlap_count  — số khách sạn lịch sử trùng nhau dẫn tới h (độ "đồng điệu")
        · cf_score       — overlap_count / (overlap_count + 2) ∈ [0,1), làm trơn như
                           hệ số trong truy vấn tổng hợp (tránh thiên vị user ít dữ liệu)

    Trả về cùng bộ field như get_candidates() (kèm matched_tags/min_price để tương
    thích bước format + LLM), cộng thêm các tín hiệu CF ở trên.
    Rỗng nếu user chưa từng đặt phòng (không có cơ sở để CF).
    """
    return run_cypher(
        """
        MATCH (u:User {user_id: $uid})
        OPTIONAL MATCH (u)-[:INTERESTED_IN]->(it:Tag)
        WITH u, collect(DISTINCT it.name) AS interests

        // Hàng xóm cùng gu: user khác từng đặt CHUNG khách sạn với u
        MATCH (u)-[:BOOKED]->(sharedHotel:Hotel)<-[:BOOKED]-(other:User)-[:BOOKED]->(h:Hotel)
        WHERE other <> u AND NOT (u)-[:BOOKED]->(h)
              // Ràng buộc địa điểm (nếu có): chỉ giữ KS trong các city yêu cầu
              AND ($cities IS NULL OR h.city IN $cities)
        WITH u, interests, h,
             count(DISTINCT other) AS neighbor_count,
             count(DISTINCT sharedHotel) AS overlap_count

        // Gắn tag khớp sở thích (cá nhân hóa + tương thích _format_candidates)
        OPTIONAL MATCH (h)-[:HAS_TAG]->(t:Tag) WHERE t.name IN interests
        WITH h, neighbor_count, overlap_count, collect(DISTINCT t.name) AS matched_tags
        OPTIONAL MATCH (h)-[:HAS_ROOM]->(r:Room) WHERE r.price IS NOT NULL
        WITH h, neighbor_count, overlap_count, matched_tags, min(r.price) AS min_price
        RETURN h.hotel_id AS hotel_id, h.name AS name, h.city AS city,
               h.star_rating AS star_rating, h.review_score AS review_score,
               h.review_count AS review_count, min_price,
               neighbor_count, overlap_count,
               1.0 * overlap_count / (overlap_count + 2.0) AS cf_score,
               size(matched_tags) AS match_count, matched_tags
        ORDER BY neighbor_count DESC, cf_score DESC, h.review_score DESC
        LIMIT $limit
        """,
        {"uid": user_id, "cities": cities or None, "limit": limit},
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
    hard = get_candidates_for_hotels(user_id, hotel_ids)

    # Bổ sung tín hiệu Collaborative Filtering, NHƯNG khoá trong đúng (các) thành phố
    # mà search đã lọc ra — vì bản thân CF không biết địa điểm. Khách sạn vừa khớp
    # điều kiện cứng vừa được "hàng xóm cùng gu" đặt sẽ được _merge_candidates đẩy lên đầu.
    cities = sorted({c["city"] for c in hard if c.get("city")})
    cf = get_candidates_collaborative(user_id, cities=cities) if cities else []
    merged = _merge_candidates(hard, cf)

    # Đánh dấu nguồn: _strict=True nếu KS qua được lọc CỨNG (thỏa MỌI điều kiện query);
    # False = chỉ là gợi ý CF cùng thành phố (có thể chưa khớp điều kiện chi tiết).
    hard_ids = {c["hotel_id"] for c in hard}
    for c in merged:
        c["_strict"] = c["hotel_id"] in hard_ids
    return merged


def get_hotel_facts(hotel_id: int | None = None, name: str | None = None) -> list[dict]:
    """Chi tiết một khách sạn để TRẢ LỜI câu hỏi: tiện nghi/đặc điểm (tag theo nhóm như
    view, hồ bơi...), các hạng phòng + giá, hạng sao, điểm đánh giá.

    Tìm theo `hotel_id` (ưu tiên, chính xác) hoặc `name` (CONTAINS, không phân biệt hoa
    thường — dùng khi chỉ biết tên). Trả danh sách (có thể >1 nếu tên mơ hồ) để bên gọi
    chọn đúng. Rỗng nếu không khớp khách sạn nào.
    """
    if hotel_id is None and not name:
        return []
    return run_cypher(
        """
        MATCH (h:Hotel)
        WHERE ($hid IS NOT NULL AND h.hotel_id = $hid)
           OR ($name IS NOT NULL AND toLower(h.name) CONTAINS toLower($name))
        OPTIONAL MATCH (h)-[:HAS_TAG]->(t:Tag)
        WITH h, collect(DISTINCT {category: t.category, name: t.name}) AS tags
        OPTIONAL MATCH (h)-[:HAS_ROOM]->(r:Room)
        WITH h, tags, collect(DISTINCT {type: r.room_type, name: r.name, price: r.price}) AS rooms
        RETURN h.hotel_id AS hotel_id, h.name AS name, h.city AS city,
               h.star_rating AS star_rating, h.review_score AS review_score,
               h.review_count AS review_count,
               [x IN tags WHERE x.name IS NOT NULL] AS tags,
               [x IN rooms WHERE x.price IS NOT NULL] AS rooms
        LIMIT 5
        """,
        {"hid": hotel_id, "name": name},
    )


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


def _merge_candidates(*lists: list[dict], limit: int = CANDIDATE_LIMIT) -> list[dict]:
    """Hợp nhất nhiều nguồn ứng viên (interest + CF...) theo hotel_id, khử trùng lặp.

    Khi một khách sạn xuất hiện ở nhiều nguồn, gộp field: giữ thông tin đã có và bù
    các tín hiệu còn thiếu từ nguồn sau (vd interest cho matched_tags, CF cho cf_score).
    Khách sạn được CẢ HAI nguồn đề xuất là tín hiệu mạnh nhất nên xếp lên đầu.
    """
    merged: dict[int, dict] = {}
    sources: dict[int, int] = {}
    for cands in lists:
        for c in cands:
            hid = c["hotel_id"]
            if hid in merged:
                for k, v in c.items():
                    if merged[hid].get(k) in (None, [], 0) and v not in (None, [], 0):
                        merged[hid][k] = v
                sources[hid] += 1
            else:
                merged[hid] = dict(c)
                sources[hid] = 1

    def sort_key(c: dict) -> tuple:
        hid = c["hotel_id"]
        return (
            sources[hid],                    # xuất hiện ở càng nhiều nguồn càng tốt
            c.get("match_count") or 0,       # độ khớp sở thích
            c.get("neighbor_count") or 0,    # số hàng xóm CF
            c.get("cf_score") or 0.0,
            c.get("review_score") or 0.0,
        )

    return sorted(merged.values(), key=sort_key, reverse=True)[:limit]


# --------------------------------------------------------------------------- #
# Gọi GPT-4o chọn top 5 + giải thích
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = """\
Bạn là CHUYÊN GIA TƯ VẤN KHÁCH SẠN, tinh tế và thấu hiểu khách hàng — như một
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
  và riêng tư của bạn:" hoặc "Nếu bạn mê không gian sang trọng ven biển:").
- Nêu 2-3 lý do CỤ THỂ, lấy TỪ DỮ LIỆU thật: tiện nghi khớp sở thích (dẫn đúng tên tag),
  mức giá so với ngân sách của khách, điểm đánh giá/hạng sao, hay nét tương đồng với nơi họ
  từng đặt. Biến mỗi dữ kiện thành LỢI ÍCH cho khách (vd không chỉ "có hồ bơi" mà "hồ bơi để
  thư giãn sau ngày dài").
- Kết bằng một câu khơi gợi cảm giác trải nghiệm, ngắn gọn và tinh tế.

CÁCH VIẾT "intro" (câu MỞ ĐẦU trước khi liệt kê, tiếng Việt, ấm áp, 2-3 câu):
- Là lời dẫn tự nhiên như một concierge đang trò chuyện trực tiếp với khách, mời họ xem qua
  các gợi ý phía dưới. Phải DÀI và có cảm xúc, không cụt lủn.
- TUYỆT ĐỐI KHÔNG nhắc tới "hồ sơ", "dữ liệu", "hệ thống", "phân tích" hay bất kỳ cơ chế kỹ
  thuật nào — chỉ nói chuyện như con người thật quan tâm tới chuyến đi của khách.
- Có thể nhắc khéo tới mong muốn/điểm đến khách đang tìm để thấy được lắng nghe, rồi khơi gợi
  sự háo hức trước những lựa chọn sắp giới thiệu. KHÔNG liệt kê tên khách sạn trong intro.

VĂN PHONG:
- Tự nhiên, sang trọng, đáng tin — như tư vấn viên thật, KHÔNG sáo rỗng, KHÔNG liệt kê khô khan.
- Không dùng emoji, không markdown, không phóng đại quá mức; mọi khẳng định phải bám dữ liệu.
- Xưng hô DUY NHẤT bằng "bạn" (TUYỆT ĐỐI không dùng "anh/chị"), nhất quán trong intro và cả 5 lý do.
"""

_RESPONSE_SCHEMA = {
    "name": "recommendations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "intro": {"type": "string"},
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
            },
        },
        "required": ["intro", "recommendations"],
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
        # Nhãn nhóm: gợi ý CF cùng thành phố nhưng có thể chưa khớp hết điều kiện chi tiết.
        tag = "" if c.get("_strict", True) else " | [GỢI Ý THÊM: khách cùng gu hay đặt, có thể chưa khớp đủ điều kiện]"
        lines.append(
            f"- id={c['hotel_id']} | {c['name']} | {c.get('city')} | "
            f"{c.get('star_rating')}★ | điểm {c.get('review_score')} | giá từ {price} | "
            f"khớp {c['match_count']} sở thích: {matched}{tag}"
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
    with trace.step("Lấy hồ sơ người dùng") as s:
        profile = get_user_profile(user_id)
        if profile is None:
            raise ValueError(f"Không tìm thấy user '{user_id}'.")
        if not profile["interests"]:
            raise ValueError(f"User '{user_id}' chưa có sở thích (INTERESTED_IN) để gợi ý.")
        s.note(
            f"{profile.get('name') or user_id}: {len(profile['interests'])} sở thích, "
            f"{len(profile['booked'])} lần đặt"
        )

    if query:
        with trace.step("Tìm khách sạn theo yêu cầu của bạn") as s:
            candidates = _candidates_from_query(user_id, query)
            if not candidates:
                raise ValueError(f"Không có khách sạn nào khớp điều kiện '{query}'.")
            strict = sum(1 for c in candidates if c.get("_strict"))
            s.note(f"{len(candidates)} ứng viên (khớp cứng {strict}, CF thêm {len(candidates) - strict})")
            s.note("Top: " + ", ".join(f"#{c['hotel_id']} {c['name']}" for c in candidates[:5]))
    else:
        # Hợp nhất 2 nguồn retrieval: khớp sở thích (interest) + Collaborative Filtering.
        # CF rỗng nếu user chưa từng đặt phòng -> rơi về interest-based như cũ.
        with trace.step("Tìm khách sạn hợp gu của bạn") as s:
            interest = get_candidates(user_id)
            collaborative = get_candidates_collaborative(user_id)
            candidates = _merge_candidates(interest, collaborative)
            if not candidates:
                raise ValueError(f"Không có khách sạn ứng viên phù hợp cho user '{user_id}'.")
            s.note(
                f"interest {len(interest)} + CF {len(collaborative)} -> gộp {len(candidates)} ứng viên"
            )
            s.note("Top: " + ", ".join(f"#{c['hotel_id']} {c['name']}" for c in candidates[:5]))

    cand_by_id = {c["hotel_id"]: c for c in candidates}

    constraint_note = (
        f'Người dùng yêu cầu: "{query}".\n'
        f"- Khách sạn KHÔNG có nhãn [GỢI Ý THÊM] đã thỏa ĐẦY ĐỦ điều kiện này — ưu tiên xếp lên trên.\n"
        f"- Khách sạn có nhãn [GỢI Ý THÊM] chỉ cùng thành phố và được khách cùng gu hay đặt, "
        f"CÓ THỂ chưa khớp hết điều kiện chi tiết: chỉ giới thiệu như lựa chọn THÊM, và TUYỆT ĐỐI "
        f"không khẳng định nó có tiện nghi/đặc điểm mà dữ liệu không nêu.\n"
        f"Hãy xếp hạng theo độ phù hợp với HỒ SƠ và giải thích.\n\n"
        if query else ""
    )
    user_content = (
        f"HỒ SƠ NGƯỜI DÙNG:\n{_format_profile(profile)}\n\n"
        f"{constraint_note}"
        f"DANH SÁCH KHÁCH SẠN ỨNG VIÊN:\n{_format_candidates(candidates)}\n\n"
        f"Hãy chọn TOP {top_k} khách sạn phù hợp nhất và giải thích lý do."
    )

    with trace.step(f"Chọn {top_k} gợi ý tốt nhất & viết lý do") as s:
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
        chosen = data.get("recommendations", [])[:top_k]
        s.note("Chọn: " + ", ".join(f"#{r.get('hotel_id')} {r.get('name')}" for r in chosen))

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

    return {
        "profile": profile,
        "query": query,
        "intro": data.get("intro"),
        "recommendations": recs,
    }
