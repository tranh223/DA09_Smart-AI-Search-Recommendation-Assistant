# INTENT v2

Tài liệu này mô tả luồng `Query Understanding / Intent v2` hiện tại của hệ thống VinBot. Trọng tâm của phiên bản này là backend sở hữu state, extract intent có context đầy đủ, quản lý vòng đời profile bằng `tagremoved`, bổ sung hidden intent, và sinh query template ổn định để gọi Search API khách sạn.

---

## 1. Mục tiêu chính

- Frontend chỉ gửi `user_id`, `session_id`, `query` và option kỹ thuật nếu có.
- Backend tự load `history`, `summary`, `session_context`, `long_term_profile`, `tagremoved_profile`.
- Intent extractor nhận được ngữ cảnh server-side thay vì phụ thuộc payload frontend.
- Feature/tag mới được merge có kiểm soát với profile cũ.
- Feature cũ không phù hợp được đưa sang `tagremoved_profile` thay vì xóa cứng.
- Search khách sạn dùng query template dựa trên current profile/session context.

---

## 2. Entry Point Trong Graph

Luồng `/chat` chạy qua LangGraph:

1. `session_node`
2. `intent_node`
3. `slot_check_node`
4. Nếu thiếu thông tin: `clarify_node`
5. Nếu đủ thông tin: `rewrite_node`
6. `rag_node` và `recommend_node` chạy sau rewrite
7. `rerank_node`
8. `response_builder_node`
9. `explain_node`
10. `format_response_node`
11. `analytics_node`

`intent_node` gọi `QueryUnderstandingPipeline.run()`, sau đó `pipeline_result_to_state()` chuyển kết quả QU thành state cho graph, bao gồm `slots`, `updated_user_profile`, `recommend_input`, `qu_trace`.

---

## 3. Server-Side Session State

### 3.1. Nguồn State Backend Load

Khi request vào `/chat`, `session_node` load:

- `Sessions.history` theo `session_id`
- `Sessions.session_context` theo `session_id`
- `Summary.history` fallback theo `user_id`
- `Summary.content` làm conversation summary
- `Summary.session_context` làm resume context theo `user_id`
- `Users.long_term_profile`
- `TagRemoved.tagremoved_profile`

### 3.2. Thứ Tự Ưu Tiên Session Context

Session context được merge theo thứ tự:

```text
Sessions.session_context > Summary.session_context > request fallback
```

Ý nghĩa:

- Nếu session hiện tại đã có state thì dùng state theo `session_id`.
- Nếu user reload web hoặc mở lại sau một thời gian, session mới/rỗng có thể dùng `Summary.session_context`.
- Payload frontend cũ chỉ là fallback backward-compatible.

### 3.3. Schema Summary.session_context

`Summary.session_context` dùng schema phẳng, chỉ lưu các field resume quan trọng:

```json
{
  "session_context": {
    "destination": "Hạ Long",
    "number_of_guests": 2,
    "check_in": "2026-06-12",
    "check_out": "2026-06-19",
    "budget_min": 500000,
    "budget_max": 1000000
  }
}
```

Khi load vào runtime QU:

```text
destination      -> session_context.destination
number_of_guests -> session_context.number_of_guests
check_in         -> session_context.check_in
check_out        -> session_context.check_out
budget_min       -> session_context.session_price_range.min
budget_max       -> session_context.session_price_range.max
```

Khi persist ngược về Mongo, backend map từ runtime về schema trên.

### 3.4. Persist Summary Context An Toàn

Khi persist `Summary.session_context`, backend merge từng field có giá trị, không thay nguyên object nếu turn hiện tại chỉ có partial context.

Ví dụ turn hiện tại chỉ extract được:

```json
{
  "destination": "Đà Nẵng"
}
```

thì không được ghi đè mất:

```json
{
  "check_in": "2026-07-20",
  "check_out": "2026-07-21"
}
```

Điều này tránh lỗi user đổi điểm đến nhưng làm mất ngày đã lưu.

---

## 4. Guardrail

Guardrail chạy đầu tiên trong `QueryUnderstandingPipeline.run()`.

### 4.1. Rule-Based Block

Các query nguy hiểm hoặc bất thường bị chặn trước LLM:

- prompt injection
- jailbreak
- spam
- anomalous input

### 4.2. Rule-Based Allow Cho OTA Query

Nếu query rõ ràng liên quan khách sạn/lưu trú, backend allow ngay thay vì phụ thuộc LLM guardrail.

Ví dụ:

- `Tìm cho tôi khách sạn phù hợp ở Đà Nẵng`
- `Gợi ý khách sạn có hồ bơi`
- `Khách sạn nào phù hợp cho gia đình`

Mục đích là tránh lỗi LLM trả output mâu thuẫn như:

```json
{
  "allow": false,
  "category": "SAFE"
}
```

### 4.3. Normalize Output Mâu Thuẫn

Nếu LLM guardrail trả:

```text
category=SAFE nhưng allow=false
```

backend normalize thành:

```text
allow=true, category=SAFE
```

Nếu `category != SAFE` nhưng `allow=true`, backend normalize thành block.

---

## 5. Profile Model

`UserProfile` hiện có 3 lớp chính:

### 5.1. session_context

State ngắn hạn theo phiên/chat:

- destination
- check_in
- check_out
- number_of_guests
- nearby_place
- session_price_range
- session_trip_types
- session_budget_levels
- session_preference_habits
- session_hotel_types
- session_room_views
- session_amenities
- runtime_tag_expansion

### 5.2. long_term_profile

State dài hạn theo user:

- traveler_type
- long_term_trip_types
- long_term_budget_levels
- long_term_price_range
- long_term_preference_habits
- long_term_hotel_types
- long_term_room_views
- long_term_amenities
- long_term_negative_preferences

### 5.3. tagremoved_profile

Pool lưu các feature từng có nhưng hiện không nên nằm trong active profile.

`tagremoved_profile` có shape gần giống `long_term_profile`. Tag không bị xóa cứng; nó được đưa ra khỏi active profile và có thể quay lại nếu user thể hiện lại nhu cầu.

---

## 6. Luồng QueryUnderstandingPipeline

### 6.1. Coerce User Profile

Pipeline nhận `user_profile_input` từ `session_node`, sau đó coerce về dataclass `UserProfile`.

Các log liên quan:

- `qu_user_profile.json`
- `qu_current_active_profile.json`

### 6.2. Guardrail

Pipeline chạy guardrail.

Nếu `allow=false`:

- dừng pipeline
- không extract intent
- không update session profile
- trả `classification=blocked_by_guardrail`

Nếu `allow=true`:

- tiếp tục check readiness/extract intent

### 6.3. Initial Profile Check

`ModelChecker` kiểm tra current profile trước khi extract:

- session hiện có destination chưa
- check_in/check_out chưa
- budget hoặc budget level chưa
- có đủ để build recommendation plan chưa

Nếu profile đã đủ và query phù hợp, pipeline có thể chạy search plan/router sớm.

### 6.4. Extract + Merge Current Profile

Nếu cần extract thêm, pipeline gọi `_extract_merge_current_profile_with_timing()`.

Trong bước này có 2 luồng LLM:

1. Explicit intent extractor
2. Hidden intent extractor

---

## 7. Explicit Intent Extractor

Explicit extractor dùng LLM để extract các thông tin rõ ràng trong query/history/context:

- entities
- constraints
- semantic_preferences

Ví dụ entities:

- destination
- check_in
- check_out
- budget_min
- budget_max
- budget_scope
- trip_type
- nearby_place
- number_of_guests

Ví dụ constraints:

- budget_level
- location_hint
- note_amenities

Ví dụ semantic preferences:

- `view đẹp`
- `sạch sẽ`
- `dịch vụ tốt`
- `phù hợp cho cặp đôi`
- `có bếp nướng`

---

## 8. Hidden Intent Extractor

Hidden intent extractor chạy song song để suy luận các tín hiệu mềm từ query, history, long-term profile và tagremoved.

### 8.1. Output Chính

Hidden extractor trả:

- `semantic_preferences`
- `profile_signals`
- `scalar_signals`

### 8.2. Profile Signals

Các nhóm signal được hỗ trợ:

- `traveler_type`: `Explorer`, `Comfort seeker`, `Planer`, `Spontaneous`
- `long_term_budget_levels`: `low`, `medium`, `high`
- `long_term_preference_habits`: `luxury`, `comfort`, `quiet`, `privacy`, `unique`, `safety`, `vibrant`

### 8.3. Không Tạo Slot Cứng

Hidden flow không được tự tạo:

- destination
- check_in
- check_out
- budget_min
- budget_max

Nó chỉ bổ sung soft signal hoặc semantic tags.

### 8.4. Không Graph Expansion Cho Hidden Intent

Hidden semantic mapping hiện không chạy graph expansion.

Thay vào đó:

- hidden semantic items được map sang tag
- tag được đưa vào runtime tags với `source="hidden_intent"`
- tránh tăng latency không cần thiết

---

## 9. Semantic Mapping Và Graph Expansion

### 9.1. Explicit Semantic Mapping

Semantic preferences explicit được map sang tag catalog:

- REVIEW_TAG
- HOTEL_AMENITY
- ROOM_AMENITY
- ROOM_VIEW
- HOTEL_TYPE
- SUITABLE_FOR

### 9.2. Graph Expansion

Explicit mapped tags có thể được graph expansion để lấy tag liên quan.

Ví dụ:

- `view đẹp` -> `Hướng Thành phố`, `Hướng Ngoài trời`
- `cặp đôi` -> tag suitable/review liên quan

### 9.3. Runtime Tag Expansion

Kết quả gồm:

- `mapped_tags`
- `expanded_tags`
- `final_tags`

`final_tags` là nguồn để update session profile.

---

## 10. Update Session Profile

`SessionProfileUpdater` cập nhật `session_context` từ:

- entities
- constraints
- runtime tags
- semantic mapping

### 10.1. Budget Normalization

Logic budget hiện tại:

- `dưới X`: window một phía xuống dưới
- `trên X`: window một phía lên trên
- `khoảng X`: expand đối xứng theo bucket OTA

Bucket window:

- `< 1.5 triệu`: 50%
- `1.5 - 3 triệu`: 40%
- `3 - 5 triệu`: 30%
- `5 - 10 triệu`: 25%
- `> 10 triệu`: 20%

Ví dụ:

```text
khoảng 1 triệu
```

sẽ thành:

```json
{
  "min": 500000,
  "max": 1500000
}
```

Nếu LLM parse lệch `khoảng 1 triệu` thành chỉ `budget_max=1000000`, backend có correction deterministic để đưa về dạng approximate trước khi normalize.

---

## 11. Active Profile Và Retention

Sau khi session context được update, hệ thống build active profile.

### 11.1. CurrentProfileMerger

Merger nhận:

- long_term_profile
- session_context
- hidden_profile_signals
- tagremoved_profile

### 11.2. ProfileRetentionResolver

LLM retention resolver quyết định:

- feature nào giữ trong active/long-term profile
- feature nào chuyển sang tagremoved
- feature nào từ tagremoved được đưa lại profile

Nguyên tắc:

- explicit/session signal thắng hidden signal
- không invent tag mới
- không xóa cứng feature
- nếu không chắc thì giữ bucket hiện tại

### 11.3. Reconcile TagRemoved

Theo chu kỳ cấu hình:

```text
TAGREMOVED_RECONCILE_INTERVAL_HOURS
```

backend merge `Users.long_term_profile` với `TagRemoved.tagremoved_profile`, sau đó clear tagremoved.

Mặc định: `24` giờ.

---

## 12. Search Plan Và Router

Sau khi có active profile:

1. `SearchPlanner` phân loại nhu cầu tìm kiếm.
2. `Router` tạo các execution steps.

Các nhánh chính:

- recommendation plan
- RAG plan

Nếu đủ điều kiện recommend, `router_result` sẽ được build và `pipeline_result_to_state()` tạo `recommend_input`.

Nếu thiếu slot quan trọng, pipeline trả `needs_clarification=true`.

---

## 13. Rewrite Node Và Search Query Template

Sau `slot_check` complete, graph chạy `rewrite_node`.

Hiện `rewrite_node` không rewrite raw query cho RAG theo nghĩa cũ. Nó build thêm:

```text
search_query_template
```

từ `RecommendInput`.

Template được gắn vào:

```text
RecommendInput.search_query_template
```

Nhờ đó `recommend_node` và Search API dùng cùng một query template đã được sinh ở rewrite stage.

---

## 14. Template Search API

Module hiện tại:

```text
backend/app/recommendation/candidate_generation/hotel_search/template_search_api.py
```

Module cũ `embedding_search.py` đã được đổi tên vì luồng này không còn là embedding search nội bộ, mà là adapter gọi external Search API bằng template query.

### 14.1. Dữ Liệu Dùng Để Build Template

`slots.py` lấy các field từ `RecommendInput`:

- destination
- check_in
- check_out
- budget_min
- budget_max
- trip_type
- traveler_type
- budget_levels
- hotel_types
- room_views
- amenities
- preference_habits
- profile_features

### 14.2. Template Hiện Tại

Các phần có dữ liệu thì được append, phần thiếu thì bỏ:

- `Tôi sắp đi {destination} từ ngày {check_in} đến ngày {check_out}.`
- `Tôi muốn khách sạn phù hợp cho {trip_type}.`
- `Phong cách du lịch của tôi là {traveler_type}.`
- `Mức ngân sách ưu tiên là {budget_level}.`
- `Tôi muốn phòng có giá khoảng {budget_min} triệu đến {budget_max} triệu.`
- `Tôi ưu tiên loại hình lưu trú như {hotel_types}.`
- `Tôi muốn phòng có hướng nhìn như {room_views}.`
- `Tôi muốn khách sạn có tiện ích như {amenities}.`
- `Tôi muốn khách sạn có đặc điểm như {preference_habits}.`

### 14.3. Format Giá

Giá được chuẩn hóa về đơn vị triệu:

```text
500000  -> 0.5 triệu
1000000 -> 1 triệu
1200000 -> 1.2 triệu
2800000 -> 2.8 triệu
```

Ví dụ:

```text
Tôi muốn phòng có giá khoảng 0.5 triệu đến 1 triệu.
```

Nếu chỉ có `budget_max`:

```text
Tôi muốn phòng có giá khoảng tối đa 1 triệu.
```

Nếu chỉ có `budget_min`:

```text
Tôi muốn phòng có giá khoảng từ 1 triệu.
```

### 14.4. Payload Gửi Sang Search API

```json
{
  "query": "<search_query_template>",
  "filters": {},
  "top_k": 10
}
```

URL mặc định:

```text
https://search-api-760679907616.asia-southeast1.run.app/search
```

Env config:

```text
HOTEL_SEARCH_API_URL
HOTEL_SEARCH_API_TIMEOUT_SECONDS
```

---

## 15. Persist Sau Mỗi Turn

`analytics_node` persist state trực tiếp vào Mongo để không phụ thuộc Kafka cho state cốt lõi.

Các collection được cập nhật:

- `Sessions.session_context`
- `Users.long_term_profile`
- `TagRemoved.tagremoved_profile`
- `Summary.session_context`
- `Sessions.history`
- `Summary.history`

`Summary.session_context` được merge field-by-field để tránh turn thiếu thông tin ghi đè mất context cũ.

---

## 16. Logging Và Trace

Các file log JSON chính:

- `backend/logs/qu_user_profile.json`
- `backend/logs/qu_active_user_profile.json`
- `backend/logs/qu_current_active_profile.json`
- `backend/logs/qu_tag_mapping.json`
- `backend/logs/qu_query_classification.json`
- `backend/logs/qu_profile_retention.json`
- `backend/logs/qu_hidden_intent.json`

Ý nghĩa:

- `qu_user_profile.json`: state đầu vào sau coerce/load
- `qu_active_user_profile.json`: active profile sau session update và merge
- `qu_current_active_profile.json`: snapshot profile theo stage
- `qu_tag_mapping.json`: semantic mapping, hidden mapping, graph expansion
- `qu_query_classification.json`: guardrail, readiness, intent, router
- `qu_profile_retention.json`: quyết định giữ/bỏ profile/tagremoved
- `qu_hidden_intent.json`: output và trace của hidden intent extractor

Ngoài ra `ota_trace.jsonl` ghi trace theo request id, gồm input/output từng node trong graph.

---

## 17. Một Số Case Quan Trọng

### 17.1. User Đổi Destination Nhưng Giữ Ngày Cũ

Summary đang có:

```json
{
  "destination": "Hà Nội",
  "check_in": "2026-07-20",
  "check_out": "2026-07-21",
  "budget_min": 500000,
  "budget_max": 1000000
}
```

User hỏi:

```text
Tìm cho tôi khách sạn phù hợp ở Đà Nẵng
```

Guardrail allow, extractor lấy `destination=Đà Nẵng`, session context giữ `check_in/check_out/budget` nếu query không phủ định. Nếu đủ slot, hệ thống recommend luôn.

### 17.2. Guardrail Output Mâu Thuẫn

Nếu LLM trả:

```json
{
  "allow": false,
  "category": "SAFE"
}
```

backend normalize thành allow để không chặn nhầm query hợp lệ.

### 17.3. Reload Web

Frontend gửi lại `user_id`, `session_id`, `query`. Nếu session mới chưa có context, backend load `Summary.session_context` để khôi phục:

- destination
- check_in
- check_out
- number_of_guests
- budget_min/budget_max

---

## 18. Kết Luận

`INTENT v2` hiện tại chuyển từ flow phụ thuộc frontend/raw query sang flow backend-owned state:

- state được load/persist server-side
- guardrail có rule-based allow/block và normalize output mâu thuẫn
- explicit intent và hidden intent bổ trợ nhau
- hidden intent chỉ tạo soft signals, không ghi đè slot cứng
- profile có retention bằng LLM và `tagremoved`
- search query được chuẩn hóa thành template dựa trên current profile
- Summary lưu resume session context để hỗ trợ reload/mở lại web

Những thay đổi này giúp hệ thống ổn định hơn với follow-up query, giảm mất context, dễ debug và dễ tích hợp Search API bên ngoài.
