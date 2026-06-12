"""Candidate retrieval bằng đồ thị: câu hỏi tiếng Việt -> Cypher (GPT-4o) -> node.

Đây là MỘT phương pháp truy hồi ứng viên (graph-based). Các phương pháp khác
(vector, BM25, hybrid...) có thể đặt cạnh trong package app.retrieval.

Pipeline:
    user_query -> [get_schema] -> [generate_cypher] -> [validate read-only]
               -> [run_plan: chạy + nhận diện node] -> list[dict] (kèm khoá _type)

search() có cơ chế tự sửa lỗi: nếu Cypher chạy lỗi, đưa lỗi ngược cho LLM sửa lại.
"""

from __future__ import annotations

import json
import re

from neo4j.exceptions import Neo4jError

from app.core.llm_client import OPENAI_MODEL, get_openai
from app.core.neo4j_client import run_cypher_nodes
from app.retrieval.schema import get_schema

# Các từ khoá Cypher gây ghi/đổi dữ liệu -> tool sẽ từ chối thực thi.
_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|DELETE|DETACH|SET|MERGE|REMOVE|DROP|LOAD\s+CSV|CALL\s*\{|"
    r"FOREACH|CREATE\s+INDEX|CREATE\s+CONSTRAINT)\b",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
Bạn là chuyên gia chuyển câu hỏi tiếng Việt về khách sạn/du lịch thành truy vấn Cypher cho Neo4j.

Quy tắc:
- CHỈ sinh truy vấn READ-ONLY (chỉ MATCH/WHERE/RETURN/ORDER BY/LIMIT). Tuyệt đối KHÔNG dùng
  CREATE, MERGE, SET, DELETE, REMOVE, DROP, LOAD CSV.
- Dùng đúng tên label, relationship và property có trong schema được cung cấp.
- Khi lọc theo thành phố (City): PHẢI map tên người dùng gõ sang ĐÚNG tên trong "Danh mục
  tên City có sẵn", kể cả khi họ gõ sai dấu/chính tả (vd "Nhà Trang" -> "Nha Trang",
  "da nang" -> "Đà Nẵng"). Nếu không có thành phố nào trong danh mục khớp ý người dùng, hãy
  bỏ điều kiện thành phố thay vì dùng một tên không tồn tại.
- MỖI quan hệ phải bắt đầu từ ĐÚNG node nguồn theo schema. TUYỆT ĐỐI KHÔNG nối chuỗi nhiều
  quan hệ liên tiếp khiến một quan hệ xuất phát từ sai node.
  SAI:  (h:Hotel)-[:LOCATED_IN]->(c:City)-[:HAS_ROOM]->(r:Room)   // HAS_ROOM gắn vào City -> sai
  ĐÚNG: dùng nhiều mệnh đề MATCH riêng, đều bắt đầu từ (h):
        MATCH (h:Hotel)-[:LOCATED_IN]->(c:City {name:"Đà Nẵng"})
        MATCH (h)-[:HAS_ROOM]->(r:Room)-[:HAS_TAG]->(t:Tag {name:"Hướng Biển"})
- Khi lọc theo Tag: PHẢI chọn giá trị tag chính xác từ "Danh mục giá trị Tag có sẵn" trong
  schema (ánh xạ cách người dùng diễn đạt sang đúng tên tag, vd "wifi" -> "Wi-Fi miễn phí").
  Nếu không có tag nào khớp ý người dùng, mới fallback sang so khớp property bằng
  toLower(...) CONTAINS toLower(...).
- PHÂN BIỆT ngữ nghĩa nhiều điều kiện:
  - Người dùng cần CẢ nhiều tiện nghi (vd "wifi VÀ bể bơi"): khách sạn phải có TẤT CẢ tag đó.
    Dùng: MATCH (h)-[:HAS_TAG]->(t:Tag) WHERE t.name IN [...] WITH h, count(DISTINCT t) AS k
    WHERE k = <số tag yêu cầu> ... KHÔNG dùng IN đơn thuần vì IN cho ngữ nghĩa HOẶC.
  - Người dùng chấp nhận BẤT KỲ tiện nghi nào (vd "wifi hoặc bể bơi"): dùng t.name IN [...].
- Với so khớp văn bản tự do khác, dùng toLower(...) CONTAINS toLower(...) để không phân biệt
  hoa/thường.
- GIÁ khách sạn = giá phòng thấp nhất của nó. Property giá nằm trên Room.price (KHÔNG có giá
  trực tiếp trên Hotel). Vì vậy khi người dùng nói về giá ("rẻ nhất", "giá thấp", "dưới X",
  "đắt nhất"...), PHẢI lấy giá qua (h)-[:HAS_ROOM]->(:Room) và tính min(r.price):
    MATCH (h:Hotel)-[:HAS_ROOM]->(r:Room) WHERE r.price IS NOT NULL
    WITH h, min(r.price) AS min_price
    RETURN h AS hotel ORDER BY min_price ASC LIMIT $limit
  ("rẻ nhất" -> ORDER BY min_price ASC; "đắt nhất" -> DESC). KHÔNG được bỏ qua tiêu chí giá
  hay thay bằng review_score/star_rating.
  LƯU Ý: khi đã gom nhóm bằng WITH h, <aggregation> thì h đã là DUY NHẤT -> KHÔNG dùng
  DISTINCT nữa (DISTINCT sẽ chặn ORDER BY theo biến tổng hợp như min_price).
- RETURN PHẢI trả về NGUYÊN node phù hợp nhất với câu hỏi (KHÔNG trả lẻ từng property như
  h.name, h.address). Chọn LOẠI node theo ý người dùng:
  - Hỏi tìm khách sạn -> trả node Hotel (vd `RETURN DISTINCT h AS result`).
  - Hỏi "địa điểm gần khách sạn X" -> trả node Place (vd
    `MATCH (h:Hotel {name:"..."})-[:NEAR]->(p:Place) RETURN DISTINCT p AS result`).
  - Hỏi về phòng -> trả node Room; v.v.
  Code phía sau nhận diện loại node theo nhãn, nên chỉ cần trả nguyên node.
- Chống trùng lặp:
  - Mặc định (không gom nhóm): dùng `RETURN DISTINCT <node> AS result`.
  - Nếu đã gom nhóm bằng `WITH <node>, <aggregation>` (vd min_price để sắp theo giá): node đã
    DUY NHẤT, dùng `RETURN <node> AS result` (TUYỆT ĐỐI KHÔNG kèm DISTINCT, vì DISTINCT chặn
    ORDER BY theo biến tổng hợp).
- Với câu hỏi tìm khách sạn, cân nhắc ORDER BY h.review_score/h.star_rating giảm dần.
- Thêm LIMIT $limit vào cuối truy vấn.
- Nếu cần truyền giá trị, đặt vào trường "params" thay vì nhúng trực tiếp vào câu Cypher.
"""

_RESPONSE_SCHEMA = {
    "name": "cypher_query",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "cypher": {"type": "string", "description": "Câu Cypher read-only"},
            "params": {
                "type": "string",
                "description": (
                    "Tham số cho câu Cypher dưới dạng CHUỖI JSON, "
                    'ví dụ: {"limit": 10}. Nếu không có tham số nào thì trả "{}".'
                ),
            },
            "reasoning": {"type": "string", "description": "Giải thích ngắn gọn"},
        },
        "required": ["cypher", "params", "reasoning"],
        "additionalProperties": False,
    },
}

# Thông tin cơ bản theo từng loại node. Nhãn không có trong map -> trả toàn bộ property.
_BASIC_FIELDS_BY_LABEL: dict[str, list[str]] = {
    "Hotel": [
        "hotel_id", "name", "address", "city", "accommodation_type",
        "star_rating", "review_score", "review_count",
    ],
    "Place": ["place_id", "name", "type"],
    "Room": [
        "room_id", "name", "room_type_id", "price", "bed_type",
        "room_view", "room_size", "max_occupancy", "review_score",
    ],
    "City": ["name"],
    "Tag": ["name", "category"],
    "Activity": ["activity_id", "title", "price_amount", "review_score"],
}


def generate_cypher(
    user_query: str,
    limit: int = 10,
    error_feedback: str | None = None,
    prev_cypher: str | None = None,
) -> dict:
    """Gọi GPT-4o sinh ra {"cypher", "params", "reasoning"} từ schema + câu hỏi.

    Nếu truyền error_feedback (+ prev_cypher), LLM sẽ sửa lại câu Cypher trước đó
    dựa trên thông báo lỗi của Neo4j.
    """
    schema = get_schema()
    client = get_openai()

    user_content = (
        f"Schema của graph:\n{schema}\n\n"
        f"Câu hỏi của người dùng: {user_query}\n\n"
        f"Sinh câu Cypher phù hợp. Dùng tham số $limit = {limit} cho LIMIT."
    )

    if error_feedback:
        user_content += (
            f"\n\nCâu Cypher trước đó BỊ LỖI khi chạy trên Neo4j:\n{prev_cypher}\n\n"
            f"Thông báo lỗi:\n{error_feedback}\n\n"
            f"Hãy SỬA lại câu Cypher cho đúng cú pháp/ngữ nghĩa và thử lại."
        )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
    )

    data = json.loads(response.choices[0].message.content)

    # params được trả dưới dạng chuỗi JSON -> parse lại thành dict.
    raw_params = data.get("params") or "{}"
    params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
    params.setdefault("limit", limit)
    data["params"] = params
    return data


def assert_read_only(cypher: str) -> None:
    """Raise ValueError nếu câu Cypher chứa thao tác ghi/đổi dữ liệu."""
    match = _WRITE_KEYWORDS.search(cypher)
    if match:
        raise ValueError(
            f"Cypher bị từ chối vì chứa thao tác không phải read-only: '{match.group(0)}'.\n"
            f"Query: {cypher}"
        )


def run_plan(plan: dict) -> list[dict]:
    """Thực thi một plan (đã có cypher/params) -> danh sách kết quả cơ bản.

    Tách riêng khỏi search() để gọi LLM đúng MỘT lần: bên gọi có thể
    generate_cypher() rồi truyền plan vào đây, vừa lấy được câu Cypher thực thi
    vừa lấy kết quả mà không sinh Cypher lần hai.
    """
    cypher = plan["cypher"]
    params = plan.get("params", {})

    assert_read_only(cypher)

    nodes = run_cypher_nodes(cypher, params)
    return [_to_basic(label, props) for label, props in nodes]


def _to_basic(label: str, props: dict) -> dict:
    """Trả thông tin cơ bản của một node theo nhãn, kèm khoá _type."""
    fields = _BASIC_FIELDS_BY_LABEL.get(label)
    basic = {f: props.get(f) for f in fields} if fields else dict(props)
    return {"_type": label, **basic}


def search(user_query: str, limit: int = 10, max_retries: int = 2) -> list[dict]:
    """Nhận câu hỏi tiếng Việt, trả về danh sách kết quả (Hotel/Place/Room...).

    GPT-4o tự chọn loại node phù hợp; hậu xử lý nhận diện theo NHÃN và trả về thông
    tin cơ bản, mỗi dict kèm khoá "_type". Nếu Cypher lỗi, tự đưa lỗi cho LLM sửa
    và thử lại (tối đa max_retries lần).

    Ví dụ:
        >>> search("Tôi muốn tìm khách sạn có view biển")   # -> Hotel
        >>> search("những địa điểm gần khách sạn X")          # -> Place
    """
    plan = generate_cypher(user_query, limit=limit)

    for attempt in range(max_retries + 1):
        try:
            return run_plan(plan)
        except Neo4jError as exc:
            if attempt == max_retries:
                raise
            plan = generate_cypher(
                user_query,
                limit=limit,
                error_feedback=str(exc),
                prev_cypher=plan["cypher"],
            )

    return []  # không tới được (vòng lặp luôn return hoặc raise)


# Tương thích ngược: search_hotels là bí danh của search.
search_hotels = search
