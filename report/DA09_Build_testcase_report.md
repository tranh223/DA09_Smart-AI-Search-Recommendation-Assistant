# Báo Cáo Công Việc: Xây Dựng Test Case và Automation Test

## DA09: Smart AI Search & Recommendation Assistant

---

## 1. Mục Tiêu Dự Án

Thiết kế bộ kiểm thử cho **Smart AI Search & Recommendation Assistant** nhằm:

- Đảm bảo tính đúng đắn của các module AI
- Đánh giá chất lượng phản hồi của hệ thống
- Kiểm tra sự ổn định của pipeline end-to-end
- Tự động hóa quá trình kiểm thử để phục vụ regression testing

---

## 2. Quy Trình Xây Dựng Bộ Test Case

Quy trình xây dựng test case:

```text
Phân tích yêu cầu
        ↓
Xác định intent cần kiểm thử
        ↓
Thiết kế input query
        ↓
Xác định expected behavior
        ↓
Chuẩn hóa testcase
        ↓
Thực hiện automation test
        ↓
Đánh giá kết quả
```

### Cấu trúc chuẩn mỗi testcase

| Trường | Ý nghĩa |
|--------|---------|
| `test_id` | Mã testcase |
| `group` | Nhóm chức năng |
| `query` | Câu hỏi đầu vào |
| `expected_intent` | Intent mong đợi |
| `expected_keywords` | Từ khóa cần xuất hiện |
| `expected_recommendation` | Điều kiện recommendation |
| `expected_sources` | Nguồn dữ liệu cần gọi |
| `expected_status` | Kết quả mong muốn |

### Ví dụ

```json
{
  "test_id": "E2E-06",
  "group": "E2E",
  "query": "Tìm resort 5 sao có bãi biển riêng ở Phú Quốc",
  "expected_intent": "personalization",
  "expected_keywords": [
    "5 sao",
    "bãi biển riêng"
  ],
  "expected_recommendation": true
}
```

---

## 3. Phân Loại Test Case

Xây dựng nhiều nhóm testcase nhằm kiểm tra toàn diện hệ thống.

### 3.1. API Test

**Mục tiêu:**

- Kiểm tra API hoạt động
- Kiểm tra status code
- Kiểm tra schema output

**Ví dụ endpoint:**

```text
POST /chat
POST /recommendation
POST /rag
```

### 3.2. Planner Test

**Mục tiêu:**

- Kiểm tra khả năng phân tích intent
- Kiểm tra routing logic

**Ví dụ:**

- **Query:** `Cho tôi thông tin khách sạn Mường Thanh`
- **Expected:**
  - `intent = hotel_information`
  - `tool = hotel_sql_tool`

### 3.3. RAG Test

**Mục tiêu:**

- Kiểm tra retrieval
- Kiểm tra generation
- Kiểm tra schema output

**Ví dụ:**

- **Query:** `Khách sạn có checkin lúc mấy giờ?`
- **Expected:** policy được trả về

### 3.4. Recommendation Test

**Mục tiêu:**

- Kiểm tra personalization
- Kiểm tra ranking
- Kiểm tra filtering

**Ví dụ:**

- **Query:** `Tìm resort cho gia đình tại Phú Quốc`
- **Expected:** `recommendation > 0`

### 3.5. Session Context Test

**Mục tiêu:**

- Kiểm tra khả năng lưu ngữ cảnh hội thoại

**Ví dụ:**

```text
User: tìm khách sạn ở Đà Nẵng
User: khách sạn đầu tiên có hồ bơi không?
```

### 3.6. Guardrail Test

**Mục tiêu:**

- Kiểm tra các trường hợp ngoại lệ
- Kiểm tra hallucination
- Kiểm tra input bất thường

**Ví dụ:**

- **Query:** `Khách sạn ở sao Hỏa`

### 3.7. End-to-End Test

**Mục tiêu:**

- Kiểm thử toàn bộ pipeline

**Pipeline:**

```text
User Query
    ↓
Planner
    ↓
Retrieval
    ↓
Aggregation
    ↓
Generation
    ↓
Response
```

---

## 4. Xây Dựng Automation Test Framework

Framework automation test được xây dựng bằng **Python**.

### Kiến trúc

```text
testcases.xlsx
        ↓
test_loader
        ↓
api_client
        ↓
executor
        ↓
validator
        ↓
report_generator
```

### Các thành phần

#### Test Loader

**Chức năng:**

- Đọc testcase từ Excel
- Chuẩn hóa dữ liệu

**Ví dụ:**

```python
load_testcases()
```

#### Executor

**Chức năng:**

- Gửi request tới hệ thống
- Đo thời gian phản hồi

**Ví dụ:**

```python
response = client.chat(query)
```

#### Validator

**Chức năng:**

So sánh kết quả thực tế với expected. Kiểm tra:

- Status code
- Intent
- Recommendation
- Keywords
- Source retrieval
- Output schema

**Ví dụ:**

```python
validate_intent()
validate_recommendations()
validate_answer()
```

#### Report Generator

**Chức năng:**

Sinh báo cáo gồm:

- PASS
- FAIL
- SKIP
- MANUAL CHECK
- LATENCY
- SUCCESS RATE

---

## 5. Các Chỉ Số Đánh Giá

Trong quá trình test, sử dụng các metric sau:

| Metric | Ý nghĩa |
|--------|---------|
| **Accuracy** | Độ chính xác intent |
| **Recall** | Khả năng truy hồi |
| **Precision** | Độ chính xác retrieval |
| **Response Time** | Thời gian phản hồi |
| **Pass Rate** | Tỷ lệ pass |
| **Recommendation Hit Rate** | Độ chính xác recommendation |

---

## 6. Kết Quả Đạt Được

- Xây dựng được bộ test gồm **47 testcase**, bao phủ **11 nhóm chức năng**
- **Pass:** 46/47 (**97.9%**)
- **Fail:** 1/47 (**2.1%**)
- **Thời gian phản hồi trung bình:** 23.2 giây/request
- **Thời gian phản hồi tối đa:** 53.3 giây/request

Hoàn thiện framework automation test cho toàn bộ pipeline.

Hỗ trợ regression testing và benchmark hệ thống.

Giúp phát hiện lỗi trong:

- Planner
- Retrieval
- Recommendation
- Generation
- Response Builder
