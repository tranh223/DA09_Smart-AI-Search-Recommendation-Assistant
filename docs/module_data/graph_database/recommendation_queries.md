# Hướng dẫn & Thư viện Truy vấn Cypher phục vụ gợi ý Khách sạn và Du lịch (Graph-Native Queries)

Tài liệu này cung cấp sơ đồ Graph Database (Neo4j) và các mẫu truy vấn Cypher **phức tạp, có độ sâu liên kết cao (multi-hop)** mà cơ sở dữ liệu quan hệ (SQL) khó thực hiện hoặc tốn nhiều thời gian xử lý (nhiều JOINs phức tạp, tính toán động). 

LLM dùng Neo4j để xử lý các nghiệp vụ gợi ý cá nhân hóa, tìm kiếm ngữ cảnh, và phân tích hành vi đặt phòng chéo; còn các tác vụ tra cứu thông tin cơ bản (tìm theo tên, lấy danh sách phòng cụ thể, lọc giá đơn thuần) được truy vấn từ PostgreSQL.

---

## 1. Sơ đồ dữ liệu (Graph Schema Reference)

### 1.1 Các loại Node và Thuộc tính
*   **`User`**: Người dùng hệ thống.
    *   `user_id` (String): ID định danh người dùng.
    *   `name` (String): Tên người dùng.
    *   `nationality` (String): Quốc tịch.
    *   `current_workplace` (String): Nơi làm việc hiện tại.
*   **`Hotel`**: Khách sạn / Resort.
    *   `hotel_id` (Integer): ID khách sạn.
    *   `name` (String): Tên khách sạn.
    *   `accommodation_type` (String): Loại hình lưu trú.
    *   `star_rating` (Float): Số sao đánh giá.
    *   `review_score` (Float): Điểm review trung bình (0.0 - 10.0).
    *   `review_count` (Integer): Số lượng lượt đánh giá.
    *   `city` (String): Thành phố.
    *   `address` (String): Địa chỉ chi tiết.
    *   `latitude` (Float): Vĩ độ.
    *   `longitude` (Float): Kinh độ.
*   **`Room`**: Phòng ngủ thuộc khách sạn.
    *   `room_id` (Integer): ID phòng.
    *   `name` (String): Tên phòng.
    *   `price` (Float): Giá phòng.
    *   `room_size` (String): Diện tích phòng.
    *   `max_occupancy` (Integer): Số lượng khách tối đa.
    *   `room_view` (String): Hướng nhìn phòng.
    *   `bed_type` (String): Loại giường.
    *   `room_type_id` (Integer): ID loại phòng.
    *   `review_score` (Float): Điểm đánh giá của phòng.
*   **`Place`**: Điểm du lịch, vui chơi gần khách sạn.
    *   `place_id` (Integer), `name` (String), `type` (String).
*   **`Activity`**: Hoạt động trải nghiệm mà khách sạn cung cấp.
    *   `activity_id` (Integer), `title` (String), `price_amount` (Float), `review_score` (Float).
*   **`City`**: Thành phố.
    *   `name` (String).
*   **`Tag`**: Nhãn phân loại trung gian, liên kết các đối tượng.
    *   `name` (String): Tên tag (ví dụ: "WiFi miễn phí", "Cặp đôi", "Hướng Biển").
    *   `category` (String): Nhóm phân loại của tag. Gồm các category chính:
        *   `HOTEL_AMENITY`: Tiện ích khách sạn.
        *   `SUITABLE_FOR`: Đối tượng phù hợp.
        *   `REVIEW_TAG`: Thẻ đánh giá từ review của khách.
        *   `ROOM_VIEW`: Hướng nhìn phòng.
        *   `ROOM_AMENITY`: Tiện ích trong phòng.
        *   `HOTEL_TYPE`: Loại hình khách sạn.
        *   `PLACE_TYPE`: Loại hình điểm du lịch.
*   **`UserFeature`**: Đặc điểm hành vi / nhân khẩu học của User.
    *   `user_feature_id` (String), `name` (String), `category` (String).

### 1.2 Các loại Quan hệ (Relationships)
*   `(:User)-[:INTERESTED_IN]->(:Tag)`: Sở thích của User đối với các Tag.
    *   **Properties**: `count` (Integer - Số lần tương tác), `last_interaction` (String - Ngày tương tác cuối, định dạng "YYYY-MM-DD").
*   `(:User)-[:HAS_FEATURES]->(:UserFeature)`: Liên kết User với các đặc trưng hành vi / nhân khẩu học của họ.
    *   **Properties**: `count` (Integer - Số lần ghi nhận/tương tác), `last_interaction` (String - Ngày tương tác cuối, định dạng "YYYY-MM-DD").
*   `(:User)-[:BOOKED]->(:Hotel)`: Lịch sử đặt phòng của User.
*   `(:Hotel)-[:HAS_ROOM]->(:Room)`
*   `(:Hotel)-[:LOCATED_IN]->(:City)`
*   `(:Hotel)-[:NEAR]->(:Place)`: Vị trí gần các điểm du lịch.
    *   **Properties**: `distance_km` (Float - Khoảng cách tính bằng km).
*   `(:Hotel)-[:OFFERS_ACTIVITY]->(:Activity)`
*   `(:Hotel)-[:HAS_TAG]->(:Tag)`: Trọng số của khách sạn với các nhãn dịch vụ/tiện ích.
    *   **Properties**: `weight` (Float - Độ mạnh liên kết $[0.0, 1.0]$), `mentioned` (Integer), `positive_pct` (Float).
*   `(:Room)-[:HAS_TAG]->(:Tag)`
*   `(:Place)-[:HAS_TAG]->(:Tag)`

---

## 2. Thư viện truy vấn gợi ý phức tạp (Complex Graph-Native Queries)

### 2.1 Tính Độ Tương Đồng Sở Thích Cá Nhân Hóa (Cosine Similarity + Time Decay)
*   **Mục đích**: Tìm khách sạn có phân phối các dịch vụ/nhãn khớp nhất với phân phối hành vi/sở thích của người dùng.

```cypher
MATCH (u:User {user_id: $user_id})-[i:INTERESTED_IN]->(t:Tag)<-[h:HAS_TAG]-(hotel:Hotel)
WHERE hotel.city = $city
WITH hotel, t,
     // Tính điểm sở thích có áp dụng Time-decay (hệ số suy giảm lambda = 0.05)
     i.count * exp(-0.05 * duration.inDays(date(i.last_interaction), date()).days) AS userInterestScore,
     h.weight AS hotelTagWeight
WITH hotel,
     sum(userInterestScore * hotelTagWeight) AS dotProduct,
     sqrt(sum(userInterestScore * userInterestScore)) * sqrt(sum(hotelTagWeight * hotelTagWeight)) AS norm,
     collect(t.name) AS matchedTags
RETURN hotel.hotel_id AS hotel_id,
       hotel.name AS name,
       hotel.star_rating AS star_rating,
       hotel.review_score AS review_score,
       CASE WHEN norm > 0 THEN dotProduct / norm ELSE 0.0 END AS match_score,
       matchedTags[..5] AS matchedTags
ORDER BY match_score DESC, hotel.review_score DESC
LIMIT $limit
```

### 2.2 Gợi ý Lan Truyền Nhãn Gián Tiếp (Indirect Tag/Feature Propagation)
*   **Mục đích**: Gợi ý khách sạn khi sở thích của người dùng không gắn trực tiếp vào khách sạn đó, mà nằm ở hoạt động xung quanh hoặc tiện nghi phòng cụ thể (ví dụ: User thích "Lặn biển" - là nhãn của Activity, hoặc "Hướng Biển" - là nhãn của Room).

```cypher
MATCH (u:User {user_id: $user_id})-[i:INTERESTED_IN]->(t:Tag)
WITH t, i.count * exp(-0.05 * duration.inDays(date(i.last_interaction), date()).days) AS userInterestScore
MATCH (hotel:Hotel)
WHERE hotel.city = $city
// Khớp trực tiếp vào khách sạn
OPTIONAL MATCH (hotel)-[h:HAS_TAG]->(t)
// Khớp gián tiếp qua Room, Activity, hoặc các địa điểm lân cận
OPTIONAL MATCH (hotel)-[:HAS_ROOM|OFFERS_ACTIVITY|NEAR]->()-[h2:HAS_TAG]->(t)
WITH hotel, t, userInterestScore,
     coalesce(h.weight, 0) * 1.0 + coalesce(h2.weight, 0) * 0.5 AS combinedWeight
WHERE combinedWeight > 0
WITH hotel,
     sum(userInterestScore * combinedWeight) AS rawMatchScore,
     collect(DISTINCT t.name) AS matchedTags
RETURN hotel.hotel_id AS hotel_id,
       hotel.name AS name,
       hotel.review_score AS review_score,
       rawMatchScore AS score,
       matchedTags[..5] AS matchedTags
ORDER BY score DESC, hotel.review_score DESC
LIMIT $limit
```

### 2.3 Gợi ý Lọc Đa Chặng (Multi-hop Contextual Search)
*   **Mục đích**: Tìm kiếm các gói du lịch trọn gói phức tạp: *"Tôi muốn tìm khách sạn ở Phú Quốc gần công viên chủ đề, có tổ chức đi bộ dưới biển và phòng hướng biển dưới 3 triệu."*

```cypher
MATCH (hotel:Hotel)-[:LOCATED_IN]->(c:City {name: $city})
MATCH (hotel)-[n:NEAR]->(p:Place)-[:HAS_TAG]->(t1:Tag {name: $place_tag})
MATCH (hotel)-[:OFFERS_ACTIVITY]->(act:Activity)-[:HAS_TAG]->(t2:Tag {name: $activity_tag})
MATCH (hotel)-[:HAS_ROOM]->(r:Room)-[:HAS_TAG]->(t3:Tag {name: $room_view_tag})
WHERE n.distance_km <= $max_distance_km 
  AND r.price <= $max_room_price
RETURN hotel.hotel_id AS hotel_id,
       hotel.name AS hotel_name,
       p.name AS nearby_place,
       n.distance_km AS distance_km,
       act.title AS activity_title,
       r.name AS room_name,
       r.price AS room_price
ORDER BY n.distance_km ASC, r.price ASC
LIMIT $limit
```

### 2.4 Lọc Cộng Tác Đa Chiều (Multi-Dimensional Collaborative Filtering)
*   **Mục đích**: Gợi ý kiểu "Người dùng giống bạn cũng đã đặt những khách sạn này".

```cypher
MATCH (u:User {user_id: $user_id})-[:BOOKED]->(h1:Hotel)
WITH u, collect(h1) AS bookedHotels
MATCH (u)-[:BOOKED]->(sharedHotel:Hotel)<-[:BOOKED]-(other:User)
WITH u, bookedHotels, other, count(sharedHotel) AS sharedBookings
MATCH (other)-[:BOOKED]->(recHotel:Hotel)
WHERE NOT recHotel IN bookedHotels
// Tính toán độ trùng khớp sở thích của những người dùng này với các tag của khách sạn được gợi ý
MATCH (recHotel)-[h:HAS_TAG]->(t:Tag)
MATCH (u)-[i:INTERESTED_IN]->(t)
WITH recHotel, sharedBookings, 
     sum(h.weight * i.count) AS preferenceFit
RETURN recHotel.hotel_id AS hotel_id,
       recHotel.name AS name,
       recHotel.review_score AS review_score,
       sum(sharedBookings) AS booking_overlap_score,
       sum(preferenceFit) AS preference_match_score
ORDER BY preference_match_score DESC, booking_overlap_score DESC
LIMIT $limit
```


### 2.5 Tối ưu hóa gợi ý bằng Thuộc tính Người dùng (UserFeature)
Có 2 hướng tiếp cận chính để sử dụng các thuộc tính đặc trưng (`UserFeature` bao gồm độ tuổi, mức ngân sách, thói quen đi lại, sở thích nghỉ dưỡng) nhằm tối ưu gợi ý:

#### Hướng 1: Lọc cộng tác theo phân khúc nhân khẩu học (Demographic Collaborative Filtering)
*   **Ý tưởng**: Tìm các người dùng khác có cùng đặc trưng profile (`UserFeature`) với người dùng hiện tại, sau đó gợi ý các khách sạn mà những người này từng đặt phòng và đánh giá tốt. Điều này giải quyết bài toán cold-start khi lịch sử đặt phòng trực tiếp của người dùng còn trống hoặc thưa thớt.
*   **Mục đích**: Gợi ý các khách sạn được đặt nhiều bởi những người dùng cùng phân khúc (cùng tầm tuổi, ngân sách và thói quen du lịch).

```cypher
MATCH (u:User {user_id: $user_id})-[r1:HAS_FEATURES]->(f:UserFeature)<-[r2:HAS_FEATURES]-(other:User)
WHERE other <> u
MATCH (other)-[:BOOKED]->(hotel:Hotel)
WHERE NOT (u)-[:BOOKED]->(hotel) AND hotel.city = $city
WITH hotel, count(distinct f) AS sharedFeaturesCount, count(distinct other) AS otherUsersCount
RETURN hotel.hotel_id AS hotel_id,
       hotel.name AS name,
       hotel.review_score AS review_score,
       sharedFeaturesCount AS shared_features_score,
       otherUsersCount AS other_users_count
ORDER BY shared_features_score DESC, hotel.review_score DESC
LIMIT $limit
```

#### Hướng 2: Lọc theo luật đặc trưng trực tiếp (Content-based Feature Rule Boosting)
*   **Ý tưởng**: So khớp trực tiếp đặc trưng của người dùng với thông tin chi tiết của khách sạn (ví dụ: người dùng có ngân sách thấp `uf_budget_low` sẽ ưu tiên khách sạn có phòng `< 2 triệu`, người dùng có thói quen an toàn `uf_habit_safety` sẽ ưu tiên khách sạn có các tiện ích như `Bảo vệ 24 giờ` hay `CCTV`).
*   **Mục đích**: Tăng/giảm điểm xếp hạng (boosting score) của khách sạn một cách tường minh dựa trên các luật nghiệp vụ cứng.

```cypher
MATCH (u:User {user_id: $user_id})-[r:HAS_FEATURES]->(f:UserFeature)
WITH u, collect(f.user_feature_id) AS feature_ids

MATCH (hotel:Hotel) WHERE hotel.city = $city
OPTIONAL MATCH (hotel)-[:HAS_ROOM]->(room:Room)
OPTIONAL MATCH (hotel)-[:HAS_TAG]->(tag:Tag)

WITH hotel, feature_ids, 
     collect(distinct room.price) AS prices,
     collect(distinct tag.name) AS tag_names
     
// 1. Áp dụng luật về ngân sách (Budget Rule)
WITH hotel, tag_names,
     CASE 
       WHEN "uf_budget_low" IN feature_ids AND any(p IN prices WHERE p < 2000000.0) THEN 1.0
       WHEN "uf_budget_medium" IN feature_ids AND any(p IN prices WHERE p >= 2000000.0 AND p <= 5000000.0) THEN 1.0
       WHEN "uf_budget_high" IN feature_ids AND any(p IN prices WHERE p > 5000000.0) THEN 1.0
       ELSE 0.0
     END AS budgetScore,
     
     // 2. Áp dụng luật thói quen (Habit Rule)
     CASE
       WHEN "uf_habit_luxury" IN feature_ids AND hotel.star_rating >= 4.5 THEN 1.0
       ELSE 0.0
     END +
     CASE
       WHEN "uf_habit_safety" IN feature_ids AND (any(t IN tag_names WHERE t IN ["Bảo vệ 24 giờ", "CCTV trong khu vực chung"])) THEN 1.0
       ELSE 0.0
     END +
     CASE
       WHEN "uf_habit_quiet" IN feature_ids AND any(t IN tag_names WHERE t = "Cách âm") THEN 1.0
       ELSE 0.0
     END AS habitScore
     
WITH hotel, budgetScore, habitScore, (budgetScore * 2.0 + habitScore * 1.0) AS featureMatchScore
WHERE featureMatchScore > 0
RETURN hotel.hotel_id AS hotel_id,
       hotel.name AS name,
       hotel.star_rating AS star_rating,
       hotel.review_score AS review_score,
       featureMatchScore AS feature_match_score
ORDER BY feature_match_score DESC, hotel.review_score DESC
LIMIT $limit
```

---

## 3. Các lưu ý quan trọng dành cho LLM khi viết Cypher
> **1. Chuyển đổi kiểu dữ liệu Ngày**
> Thuộc tính `last_interaction` được lưu dưới dạng chuỗi (String) `"YYYY-MM-DD"`. Do đó khi tính toán hiệu ngày, bắt buộc phải ép kiểu về `date()` trong Cypher:
> `duration.inDays(date(i.last_interaction), date()).days`

> **2. Phòng tránh giá trị `nan` khi chia cho 0**
> Khi chạy các thuật toán tương đồng Vector/Cosine, nếu khách sạn mới hoặc không có nhãn trùng khớp, chuẩn hóa độ dài vector (norm) có thể bằng `0`. Luôn dùng biểu thức `CASE WHEN` để bao bọc phép chia:
> `CASE WHEN norm > 0 THEN dotProduct / norm ELSE 0.0 END AS score`

> **3. Phân loại Category của Tag**
> Khi so khớp Tag, hãy chú ý thuộc tính `category` của Tag để tránh nhầm lẫn các tag trùng tên (ví dụ: tag `"WiFi miễn phí"` tồn tại ở cả `HOTEL_AMENITY` và `ROOM_AMENITY`).
