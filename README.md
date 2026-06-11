# OTA Travel Assistant

Trợ lý **gợi ý dịch vụ du lịch cá nhân hóa** trên Neo4j: nhận câu hỏi tiếng Việt,
dùng **GPT-4o** sinh truy vấn **Cypher**, và trả về khách sạn/địa điểm/phòng. Có thêm
tính năng **gợi ý khách sạn cá nhân hóa** dựa trên hồ sơ người dùng trong graph.

## Tính năng
- **Tìm kiếm ngôn ngữ tự nhiên → Cypher**: trả nhiều loại node (Hotel/Place/Room...).
- **Khớp thông minh**: tự nhồi danh mục City/Tag thật để map đúng tên (sai dấu/chính tả,
  cách diễn đạt khác nhau).
- **Tự sửa lỗi**: nếu Cypher chạy lỗi, đưa lỗi ngược lại cho LLM sửa và thử lại.
- **Gợi ý cá nhân hóa**: dựa trên `INTERESTED_IN` / `HAS_FEATURES` / `BOOKED`, GPT-4o chọn
  top 5 + giải thích lý do. Có thể kèm điều kiện lọc cứng (vd "ở Nha Trang có view biển").
- **CLI đẹp** bằng `rich`.

## Cấu trúc dự án
```
ota_ai_assitant/
├── main.py                  # entrypoint -> mở CLI
├── requirements.txt
├── .env.example
├── README.md
└── app/
    ├── config.py            # cấu hình tập trung (đọc .env)
    ├── core/                # tầng hạ tầng
    │   ├── neo4j_client.py  # driver + run_cypher / run_cypher_nodes / close
    │   └── llm_client.py    # OpenAI client + model
    ├── services/            # tầng nghiệp vụ
    │   ├── schema.py        # introspect schema + danh mục City/Tag
    │   ├── search.py        # NL -> Cypher -> kết quả (generate_cypher, run_plan, search)
    │   └── recommender.py   # gợi ý cá nhân hóa (recommend)
    └── cli/
        └── interface.py     # CLI tương tác (rich)
```

## Cài đặt
```bash
pip install -r requirements.txt
cp .env.example .env   # rồi điền NEO4J_* và OPENAI_API_KEY
```

Biến môi trường (xem `.env.example`):
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `OPENAI_API_KEY` (bắt buộc), `OPENAI_MODEL` (mặc định `gpt-4o`)

## Sử dụng

### CLI
```bash
python main.py
```
- Tìm kiếm: `khách sạn ở Đà Nẵng có view biển`
- Gợi ý: `goiy user_141`
- Gợi ý kèm điều kiện: `goiy user_141 khách sạn ở Nha Trang có view biển`
- Thoát: `thoát`

### Dùng như thư viện
```python
from app.services.search import search
from app.services.recommender import recommend
from app.core.neo4j_client import close

hotels = search("khách sạn rẻ nhất ở Đà Nẵng", limit=5)
recs = recommend("user_141", query="ở Nha Trang có view biển", top_k=5)
close()
```
