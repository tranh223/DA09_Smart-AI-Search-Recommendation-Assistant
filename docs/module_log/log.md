# Tài liệu hệ thống: Luồng xử lý Chatbot, Logging, Đánh giá CSAT & Giám sát RAGAS

## 1. Tổng quan

Hệ thống gồm 4 khối chức năng chính, vận hành nối tiếp và phối hợp với nhau:

1. **Luồng trò chuyện Realtime** — xử lý câu hỏi của user, đo hiệu năng phản hồi, và quản lý bộ nhớ hội thoại (context).
2. **Thu thập Log trung gian qua Kafka** — hứng toàn bộ sự kiện phát sinh trong phiên chat và ghi vào MongoDB.
3. **Kết thúc phiên & tính CSAT** — khi user rời phiên, hệ thống tổng hợp đánh giá hài lòng (CSAT), hiệu năng trung bình và usage của phiên đó.
4. **Giám sát định kỳ RAGAS & đổ Dashboard Admin** — job cuối tuần lấy mẫu log để chấm chất lượng câu trả lời, đồng thời cấp dữ liệu cho dashboard quản trị.
Ba kho dữ liệu MongoDB chính được sử dụng xuyên suốt: **Summary Collection**, **Sessions Collection**, **Eval Collection**, và **Ragas Analytics**.

---

## 2. Luồng trò chuyện Realtime

**Các bước xử lý một lượt hỏi-đáp:**

| Bước | Node | Mô tả |
|---|---|---|
| 1 | `A` | User gửi câu hỏi (Question) |
| 2 | `B` | Hệ thống tính **Time To First Token (TTFT)** — thời gian từ lúc gửi câu hỏi đến khi nhận token đầu tiên |
| 3 | `C` | Tính **Latency** — tổng thời gian phản hồi toàn bộ câu trả lời |
| 4 | `D` | Bot hoàn thành câu trả lời (Answer) |

**Quản lý lịch sử hội thoại (Context Compression):**

Sau mỗi lượt trả lời, hệ thống kiểm tra số lượt hội thoại mới tích lũy (1 lượt = 1 cặp Hỏi + Đáp):

- **Nếu đã đủ 5 lượt mới**: hệ thống gọi LLM để nén lịch sử — tạo `New Summary = Old Summary + 5 lượt mới`, rồi lưu vào **MongoDB – Summary Collection**.
- **Nếu chưa đủ 5 lượt**: giữ nguyên lịch sử hiện tại, không nén.
Summary trong MongoDB sau đó được nạp lại làm context cho câu hỏi kế tiếp của user. Cụ thể, **context gửi cho LLM ở mỗi lượt gồm 3 phần**: System Prompt + Summary (đã nén) + 5 lượt hội thoại gần nhất (chưa nén).

Cơ chế này giúp giữ ngữ cảnh hội thoại dài mà không làm phình to context window gửi tới LLM.

---

## 3. Thu thập Log trung gian qua Kafka

Ngay khi bot hoàn thành câu trả lời (`D`), toàn bộ sự kiện của phiên hiện tại được đẩy qua **Kafka** (`I`) để hứng log theo thời gian thực, gồm 6 loại:

- **Log Chat History** — nội dung hội thoại
- **Log Likes/Dislikes** — phản ứng like/dislike dọc đường (inline reaction) và phản ứng cuối phiên (final reaction)
- **Log Latency & TTFT** — đo theo từng câu trả lời
- **Log booking** — trạng thái booking phát sinh trong phiên
- **Log input/output token** — số token sử dụng
- **Thời gian session end** — mốc thời gian phiên kết thúc
Toàn bộ 6 loại log này được ghi xuống **MongoDB – Sessions Collection**, đóng vai trò là kho log thô của từng phiên.

---

## 4. Kết thúc phiên & Tính CSAT

### 4.1 Trigger kết thúc phiên

Một phiên được xem là kết thúc khi xảy ra một trong hai sự kiện:

- **Bấm "New chat"** → hệ thống hiện **popup đánh giá tổng thể (final reaction)** cho user.
- **Tắt web / reload trang** → hệ thống bắn tín hiệu kết thúc phiên trực tiếp (không qua popup).
Cả hai nhánh đều hội tụ về một tín hiệu "kết thúc session", và tín hiệu này được đẩy ngược lại vào Kafka (`I`) để hoàn tất ghi log cho phiên.

### 4.2 Công thức tính CSAT

Khi phiên kết thúc (dựa trên mốc thời gian session end), hệ thống đánh giá phiên theo 3 trường hợp, tùy vào loại reaction mà user đã để lại:

| Trường hợp | Điều kiện | Công thức CSAT |
|---|---|---|
| Case 1 | Có cả inline reaction lẫn final reaction | `CSAT = 30 * Inline_CSAT + 70 * Final_Reaction` |
| Case 2 | Chỉ có inline reaction | `CSAT = Inline_CSAT * 100` (tỷ lệ Like/Dislike dọc đường) |
| Case 3 | Chỉ có final reaction | `CSAT = Final_Reaction * 100` |

Final reaction được ưu tiên trọng số cao hơn (70%) khi có đủ cả hai loại phản hồi, vì đây là đánh giá tổng thể của user sau khi kết thúc toàn bộ phiên.

### 4.3 Tổng hợp dữ liệu phiên

Sau khi tính CSAT, hệ thống tiếp tục:

1. Tính **Latency & TTFT trung bình** của toàn phiên.
2. Lưu **trạng thái booking** và tính **tổng token usage** (input + output) của phiên.
3. Ghi toàn bộ kết quả (CSAT, latency/TTFT trung bình, booking status, token usage) vào **MongoDB – Eval Collection**.
Eval Collection là nguồn dữ liệu đã qua tổng hợp ở mức phiên (session-level), khác với Sessions Collection vốn là log thô từng sự kiện.

---

## 5. Giám sát định kỳ RAGAS & Dashboard Admin

### 5.1 Job đánh giá cuối tuần (ragas_at_weekend)

Mỗi cuối tuần, hệ thống chạy hàm `ragas_at_weekend`:

- **Lấy mẫu**: bốc ngẫu nhiên 5% từ log chat thô (Sessions Collection), tối đa 30 bộ mẫu.
- **Chấm điểm**: tính 3 chỉ số chất lượng câu trả lời — **Faithfulness**, **Answer Relevance**, **Context Precision**.
- **Lưu kết quả** vào **MongoDB – Ragas Analytics**.
- **Dọn dẹp**: sau khi đánh giá xong, xóa toàn bộ log thô của các session đã được chấm, nhằm tránh phình kho dữ liệu thô.
### 5.2 Cấp dữ liệu cho Dashboard Admin

Hai nguồn dữ liệu đã qua xử lý — **Eval Collection** và **Ragas Analytics** — được đổ vào hai API tổng hợp:

- `analysis_by_day` — tổng hợp theo ngày
- `analysis_by_month` — tổng hợp theo tháng
Hai API này cấp dữ liệu cho **Dashboard Admin**, nơi cập nhật liên tục các chỉ số của ngày hiện tại và hiển thị mỗi metric dưới dạng 2 line chart (theo ngày và theo tháng), bao gồm: **CSAT, Latency, TTFT, hit rate, token usage, cost, và các chỉ số RAGAS**.

---

## 6. Tổng hợp các kho dữ liệu MongoDB

| Collection | Vai trò | Dữ liệu chính |
|---|---|---|
| **Summary Collection** | Bộ nhớ hội thoại đã nén | Summary tích lũy của từng phiên, dùng làm context cho LLM |
| **Sessions Collection** | Log thô theo thời gian thực | Chat history, like/dislike, latency/TTFT từng câu, booking, token, thời điểm kết thúc phiên |
| **Eval Collection** | Dữ liệu tổng hợp mức phiên | CSAT, latency/TTFT trung bình, booking status, tổng token usage |
| **Ragas Analytics** | Kết quả chấm chất lượng định kỳ | Faithfulness, Answer Relevance, Context Precision (theo mẫu 5%/tuần) |

---

## 7. Luồng dữ liệu tổng thể (tóm tắt)

```
User hỏi → Đo TTFT/Latency → Bot trả lời
        → (a) Nén context mỗi 5 lượt → Summary Collection → nạp lại cho câu sau
        → (b) Đẩy log qua Kafka → Sessions Collection

Kết thúc phiên (new chat / đóng web)
        → Popup final reaction (nếu có) → tín hiệu kết thúc → Kafka
        → Tính CSAT (3 case) + Latency/TTFT TB + booking + token → Eval Collection

Cuối tuần: lấy mẫu 5% (≤30) từ Sessions Collection
        → Chấm Faithfulness/Relevance/Precision → Ragas Analytics
        → Xóa log thô đã chấm

Eval Collection + Ragas Analytics → API by_day / by_month → Dashboard Admin
```