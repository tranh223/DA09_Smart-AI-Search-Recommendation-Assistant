# Tài Liệu Bàn Giao Hệ Thống - Module Rerank

Tài liệu này cung cấp toàn bộ thông tin chi tiết về kiến trúc, cấu trúc mã nguồn, cơ chế chấm điểm và hướng dẫn vận hành kiểm thử của module Rerank thuộc dự án **Smart-AI-Search-Recommendation-Assistant**.

---

## 1. Tổng Quan về Module Rerank

Trong hệ thống gợi ý khách sạn, **Rerank** đóng vai trò là chốt chặn cuối cùng (Phase xếp hạng lại). Nó nhận đầu vào là danh sách các khách sạn ứng viên (được sinh ra từ Qdrant Search hoặc Neo4j Personalization) và thực hiện tối ưu hóa thứ tự hiển thị dựa trên sở thích ngắn hạn (Session context), lịch sử dài hạn (Long-term profile), khoảng ngân sách, đối tượng đi cùng và xu hướng đặt phòng thực tế của người dùng.

### Vị trí trong Graph Pipeline:
```
[User Query] 
     │
     ▼
[Session & Intent Parsing] ──► [Candidate Generation] ──► [Rec Merge] ──► [Rerank] ──► [Response Builder]
```

---

## 2. Kiến Trúc và Luồng Xử Lý (5 Phase)

Quy trình Reranking được điều phối tại hàm `rerank()` thuộc tệp `reranker.py` và trải qua 5 giai đoạn:

```
┌────────────────────────────────────────────────────────┐
│ Phase 1: DB Enrichment (Nạp chi tiết khách sạn)         │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Phase 2: Normalize Candidates (Đồng nhất kiểu dữ liệu)   │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Phase 3: Load Profile & Bookings (Nạp ngữ cảnh user)    │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Phase 4: Scoring (Tính 10 Feature Scores & Điểm phạt)   │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Phase 5: Rank & Filter (Lọc, đa dạng hoá & sinh lý do) │
└────────────────────────────────────────────────────────┘
```

### Chi tiết các Giai đoạn:
* **Phase 1 (DB Enrichment)**: Nạp thông tin chi tiết khách sạn (tiện nghi, các phòng, vị trí lân cận). Nếu ứng viên có sẵn trường `raw_hit` từ Search API, hệ thống sẽ tự động parse và bỏ qua bước gọi SQL vào Postgres DB (Supabase) để tăng hiệu năng tối đa.
* **Phase 2 (Normalize Candidates)**: Chuyển đổi và làm sạch dữ liệu ứng viên về Schema `CandidateHotel` chuẩn hóa. Đồng bộ hóa toàn bộ các key giá phòng về tên khóa thống nhất là `"price"`.
* **Phase 3 (Load Profile & Bookings)**:
  * Lấy `user_context` (bao gồm `session_context` và `long_term_profile`), thực hiện chuẩn hóa tương tác thô (`count`) thành trọng số tương đối từ `0.0` đến `1.0`.
  * Truy vấn cơ sở dữ liệu MongoDB để lấy thống kê lượt đặt phòng (bookings) của các khách sạn ứng viên trong 30 ngày qua.
* **Phase 4 (Scoring)**: Chạy qua các bộ lọc cứng (Hard Filters), tính toán điểm của 10 Features thành phần và trừ đi điểm phạt của các thuộc tính người dùng muốn tránh (Negative Penalty).
* **Phase 5 (Rank & Filter)**: Sắp xếp theo điểm tổng kết giảm dần, áp dụng thuật toán đa dạng hóa (Diversity Rerank) nếu bật, sinh lý do đề xuất tự nhiên và ghi nhật ký debug lượt chạy.

---

## 3. Cấu Trúc Thư Mục và Mã Nguồn

Toàn bộ module Rerank nằm tại thư mục [backend/app/recommendation/rerank/](file:///Users/tranvangiaban/Code/DA09_Smart-AI-Search-Recommendation-Assistant/backend/app/recommendation/rerank/) với các file thành phần:

1. **`reranker.py`**: Điểm điều phối trung tâm của luồng Rerank.
2. **`rule_scorer.py`**: Chứa logic chấm điểm 10 features, tính điểm phạt và áp dụng bộ lọc cứng.
3. **`normalizer.py`**: Chuẩn hóa thông tin khách sạn thô từ DB/Search API sang Pydantic Model.
4. **`profile_normalizer.py`**: Chuẩn hóa tương tác trong Profile người dùng thành trọng số tương đối [0.0 - 1.0].
5. **`schemas.py`**: Khai báo các Pydantic Models (`CandidateHotel`, `RankedItem`) để ràng buộc kiểu dữ liệu đầu ra/vào.
6. **`explain_builder.py`**: Tự động sinh ra lý do gợi ý thân thiện dạng ngôn ngữ tự nhiên.
7. **`trend_scorer.py` & `booking_signals.py`**: Xử lý logic và tính điểm xu hướng đặt phòng của khách sạn.
8. **`utils.py`**: Chứa các hàm tiện ích toán học (`weighted_overlap`, `clamp`) và chuẩn hóa chuỗi viết.
9. **`logger.py`**: Hỗ trợ ghi lại nhật ký chạy chi tiết và xuất kết quả lượt chạy gần nhất ra file JSON.

---

## 4. Công Thức Chấm Điểm và Quy Tắc Vận Hành

### A. Công thức tính Điểm Tổng Kết (Final Score)
> **Final Score = Clamp( [Tổng các Feature Score x Trọng số tương ứng] - Negative Penalty )**
* *Trọng số (Weights) hiện tại:* `keyword`: 0.20 | `budget`: 0.15 | `location`: 0.15 | `personalization`: 0.10 | `suitability`: 0.10 | `trend`: 0.08 | `amenity`: 0.07 | `review`: 0.07 | `room_view`: 0.05 | `availability`: 0.03
* *Negative Penalty:* Tối đa là `0.8` (tránh điểm tổng bị âm).

### B. Công thức so khớp trùng khớp có trọng số (weighted_overlap)
Áp dụng cho các đặc trưng dạng chữ/danh sách (như tiện nghi, hướng phòng, đối tượng chuyến đi):
> **Điểm trùng khớp = (Tổng trọng số của các tag trùng khớp) / (Tổng trọng số của toàn bộ tag yêu cầu)**

### C. Công thức tính Điểm Ngân Sách (budget_score)
> **Budget Score = 0.65 x Coverage + 0.35 x Center_Score**
* Trong đó, **Coverage** là tỷ lệ trùng khớp giữa khoảng giá khách sạn và ngân sách user. **Center_Score** là điểm số đo độ lệch tâm giữa trung tâm giá khách sạn và trung tâm ngân sách.
* Nếu giá khách sạn hoàn toàn nằm ngoài ngân sách, điểm số sẽ bị giảm dần theo khoảng cách xa gần.

### D. Công thức tính Điểm Đánh Giá (review_score)
> **Review Score = 0.70 x [ (Rating - 3.0) / 2.0 ] + 0.30 x Sentiment**
* Trong đó, **Rating** là điểm sao (từ 3.0 đến 5.0). **Sentiment** là điểm cảm xúc tích cực phân tích từ bình luận thực tế (từ 0.0 đến 1.0).

---

### 5. Cách xem log kiểm tra lỗi (Debugging)
Mỗi lượt chạy qua API hoặc luồng test sẽ tự động tạo/cập nhật hai file log chi tiết trong thư mục [backend/app/recommendation/rerank/logs/](file:///Users/tranvangiaban/Code/DA09_Smart-AI-Search-Recommendation-Assistant/backend/app/recommendation/rerank/logs/):
* **`rerank_last_debug.json`**: Chứa toàn bộ danh sách khách sạn kèm chi tiết điểm số của từng feature thành phần và câu lý do gợi ý tương ứng.
* **`rerank_candidates_mapping.json`**: Chứa thông tin so sánh đầu vào thô (Raw Candidates) và đầu ra đã chuẩn hóa để kiểm tra việc đồng bộ hóa dữ liệu.
