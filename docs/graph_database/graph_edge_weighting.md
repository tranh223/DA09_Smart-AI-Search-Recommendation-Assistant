# Báo cáo: Đánh trọng số cạnh & Kết nối User–Hotel trong Graph DB

> Trình bày công thức gán trọng số cho cạnh `HAS_TAG` (Hotel → Tag) và phương thức
> nối `User` tới `Hotel` qua tầng Tag.
>
> **Ràng buộc dữ liệu:** chỉ dùng `amenities`, `reviews_detail.tags[]`,
> `reviews_detail.demographics[]`, `Hotel.review_score`.
> **Không** dùng `amenity_groups`, **không** dùng `reviews_detail.grades`.

---

## 1. Ý tưởng cốt lõi: chấm điểm amenity theo CỤM dựa trên review tag

Amenity tag (275 loại) gần như không trùng tên review tag (45 loại), nên **không match
1‑1 theo tên**. Thay vào đó:

> **45 review tag đóng vai "tâm cụm" có điểm chất lượng** (`positive_pct`).
> Mỗi amenity được gán vào một (hoặc vài) **cụm chủ đề**, và **thừa hưởng điểm review
> tag của cụm đó**.

Ví dụ tại Vinpearl: review tag `Dịch vụ` được khách chấm `positive_pct = 69%`. Toàn bộ
cụm amenity dịch vụ — *Dịch vụ phòng, Dịch vụ giặt là, Bàn tiếp tân 24h, Dọn phòng
hằng ngày, Giữ hành lý, Đổi ngoại tệ…* — đều lấy `0.69` làm điểm gốc rồi điều chỉnh.
Tương tự: cụm bể bơi ← tag `Bể bơi` (73%), cụm bữa sáng ← tag `Bữa sáng` (77%), v.v.

Nhờ vậy chỉ ~15–18 review tag là đủ "phủ" phần lớn 275 amenity, và mỗi amenity có
trọng số **phản ánh chất lượng thật theo chủ đề** thay vì chỉ là presence.

Baseline chung: $R_0(H) = \dfrac{\text{Hotel.review\_score}}{10} \in [0,1]$ — **bản chống‑0**
(thiếu `review_score` → $\tilde R_0$) và prior đầy đủ định nghĩa ở **§2.3**; các công thức
§2.1–§2.2 dưới đây viết gọn theo $R_0$/`prior`, hiểu là prior §2.3.

---

## 2. Công thức trọng số

### 2.1 Cạnh HOTEL_AMENITY — theo cụm

Gọi $\text{cl}(a)$ là (các) cụm chủ đề mà amenity $a$ thuộc về. Mỗi cụm $j$ gắn với một
review tag tại khách sạn $H$, có `mentioned` $m_j$ và `positive_pct` $p_j$:

$$
S_j = \frac{p_j}{100}, \qquad
c_j = \frac{m_j}{m_j + k}\ \ (k = 20)
$$

Điểm của một cụm (shrinkage về **prior** khi ít lượt nhắc — `prior` theo §2.3, không
phải $R_0$ trần, để không bao giờ về 0):

$$
w_j = c_j \cdot S_j + (1 - c_j)\cdot \text{prior}_j(H)
$$

Trọng số amenity = trung bình các cụm của nó, **có trọng số theo độ tin cậy** $m_j$
(nếu thuộc nhiều cụm); nếu không thuộc cụm nào / cụm không được review tại $H$ →
$\text{prior}(H,a)$ (§2.3):

$$
\boxed{\,w_{\text{amenity}}(H,a) =
\begin{cases}
\dfrac{\sum_{j \in \text{cl}(a)} m_j\, w_j}{\sum_{j \in \text{cl}(a)} m_j}, & \text{cl}(a) \neq \varnothing\\[3mm]
\text{prior}(H,a), & \text{ngược lại}
\end{cases}}
$$

- $S_j$ cao (khách khen) → đẩy cụm lên; thấp (khách chê) → kéo cụm xuống.
- $m_j$ nhỏ → $c_j$ nhỏ → cụm co về `prior` (chưa đủ bằng chứng để lệch).

### 2.2 Cạnh SUITABLE_FOR — theo `demographics`

Mỗi nhóm khách trong `demographics[]` có `count` và `score`. Gom bản ghi trùng tên
(trung bình có trọng số theo `count`) được $(\text{count}(g), \overline{score}(g))$:

$$
w_{\text{suitable}}(H,g) = c_d(g)\cdot \frac{\overline{score}(g)}{10}
+ \big(1-c_d(g)\big)\cdot \text{prior}(H,g),
\qquad
c_d(g) = \frac{\text{count}(g)}{\text{count}(g) + k_d}\ \ (k_d = 50)
$$

($g$ không thuộc cụm amenity → $\text{prior}(H,g)=R_0(H)$ bản chống‑0, §2.3.)

### 2.3 Fallback prior — khi tag CÓ mặt nhưng thiếu bằng chứng review

> **Phân biệt trước:** nếu khách sạn **không sở hữu** một tag thì trong graph
> **không có cạnh `HAS_TAG`** tới tag đó (vắng mặt = không có cạnh, *không phải*
> `weight = 0`). `MatchScore` chỉ cộng trên giao $T(U)\cap T(H)$ nên tag vắng mặt tự
> động không tham gia — **không gán giá trị cho nó**. Phần này chỉ xử lý tag **thực sự
> có mặt** (amenity trong `amenities[]`, demographic trong `demographics[]`, review tag
> trong `reviews_detail.tags[]`) nhưng **không/ít được review** → tránh để $w$ rớt về 0.

> **Lỗi gốc đã quan sát (dump 2026-06-15):** 162 cạnh `HOTEL_AMENITY` = 0, tập trung ở
> **10 khách sạn không có review nào** (vd *Sofitel Plaza Hanoi, Mercure Hoi An, KS Bắc
> Kạn*). Các KS này thiếu `review_score` → $R_0=0$, và không có cụm review nào → **mọi**
> amenity fallback về 0. Phải sửa cả baseline ($R_0$ rỗng) lẫn cách chọn prior.

**Bước 1 — baseline không-bao-giờ-0.** Sửa $R_0$ để dữ liệu thiếu không kéo về 0:

$$
R_0(H) = \begin{cases} \text{review\_score}/10 & \text{nếu có và } >0 \\[1mm]
\tilde{R}_0 & \text{ngược lại} \end{cases}
\qquad \tilde{R}_0 = \text{trung vị } \tfrac{\text{review\_score}}{10}\text{ toàn dataset}
$$

**Bước 2 — prior toàn cục theo cụm (shrunk, robust với cụm hiếm).** Pool toàn bộ review
của cụm $t$ trên mọi khách sạn, kéo nhẹ về $\tilde{R}_0$ bằng pseudo-count $k_0$:

$$
\bar{w}_t = \frac{\sum_{H'} m_{t,H'}\,S_{t,H'} + k_0\,\tilde{R}_0}{\sum_{H'} m_{t,H'} + k_0},
\qquad k_0 = 50
$$

**Bước 3 — prior 2 thành phần (empirical-Bayes: hotel × cụm).** Khi thiếu bằng chứng
cục bộ, prior kết hợp *chất lượng tổng thể của khách sạn* và *chất lượng điển hình của
loại tiện ích*:

$$
\boxed{\ \text{prior}_t(H) = \alpha\,R_0(H) + (1-\alpha)\,\bar{w}_t\ }, \qquad \alpha = 0.5
$$

(amenity không thuộc cụm nào → không có $\bar{w}_t$ → prior $= R_0(H)$.)

**Bước 4 — trọng số cuối** (shrink local về prior, có sàn):

$$
w_t(H) = \max\!\Big(\, c\cdot S_t + (1-c)\,\text{prior}_t(H),\ \varepsilon \,\Big),
\qquad c=\frac{m}{m+k},\ \ \varepsilon = 0.05
$$

- $m$ lớn → bám điểm review thật $S_t$.
- $m=0$ nhưng KS có điểm → prior phân biệt theo **cả** $R_0(H)$ **và** $\bar{w}_t$.
- KS **không review** ($R_0=\tilde{R}_0$) → prior $=0.5\tilde{R}_0+0.5\bar{w}_t$, vẫn phân
  hoá theo loại amenity → **hết 0**. Bị chê mạnh ($p$ thấp, $m$ cao) → $w_t$ thấp thật.

Sàn $\varepsilon$ giữ cho "có sở hữu" vẫn được tính chút trong cosine (tag $w=0$ đóng góp
0 vào cả tử số lẫn chuẩn → bị bỏ qua y như vắng mặt).

### 2.4 Coverage: review tag trừu tượng

Một số review tag **không phải amenity, không phải demographic** (vd *Địa điểm, Đáng
tiền, Độ thoải mái của phòng, Không khí, Kích thước phòng, Hướng nhìn từ phòng, Thiết kế
phòng, Bộ đồ giường, Khả năng đi bộ thuận tiện…*) hiện không có cụm → nếu không tạo cạnh,
user quan tâm chúng sẽ không khớp khách sạn nào. Tạo cạnh **trực tiếp**
`(Hotel)-[:HAS_TAG {weight}]->(Tag)` với $w = w_t$ theo công thức §2.3 (chúng đã có sẵn
`mentioned` + `positive_pct`).

> Khi review tag trừu tượng có mặt nhưng $m$ nhỏ, prior của nó $=R_0(H)$ (không có cụm
> amenity) hoặc $\bar w_t$ riêng nếu pool đủ lượt nhắc cùng tag — vẫn theo §2.3.

---

## 3. Định nghĩa cụm (cluster taxonomy)

Mỗi cụm = 1 review tag (nguồn điểm) + tập amenity gán vào (theo từ khoá). Bảng dưới là
khung chính (có thể bổ sung khi gặp amenity mới); cụm **Tiện ích tại cơ sở lưu trú** là
catch‑all cho amenity tiện ích chung chưa rơi vào cụm nào.

| Cụm (review tag nguồn) | Amenity tiêu biểu (từ khoá nhận diện) |
| ---------------------- | ------------------------------------- |
| **Dịch vụ** | Dịch vụ phòng, Dịch vụ giặt là, Dịch vụ ủi đồ, Giặt khô, Bàn tiếp tân, Lễ tân, Dọn phòng, Giữ hành lý, Nhân viên…, Báo thức, Đổi ngoại tệ, Rút tiền |
| **Độ sạch sẽ** | Khử trùng hằng ngày, nước rửa tay, Vật dụng tắm rửa |
| **Bữa sáng** | Bữa sáng*, Nhà hàng phục vụ bữa sáng, bữa sáng kiểu lục địa/Tây/Á |
| **Nhiều lựa chọn nhà hàng** | Nhà hàng*, Quán cà phê, Quầy đồ ăn vặt, Trái cây/đồ ăn vặt |
| **Bar** | Quán bar*, Rượu |
| **Bể bơi** | Bể bơi*, Quán bar cạnh bể bơi, Tiện nghi bể bơi |
| **Bãi biển** | Bãi biển riêng, Lối ra bãi biển |
| **Spa** | Spa, Spa/xông khô, Mát-xa, Xông khô, Phòng xông ướt, Tiệm làm đẹp |
| **Phòng tập** | Phòng tập, Sân quần vợt, thể thao dưới nước, Lặn |
| **Cơ sở vật chất cho trẻ em** | CLB trẻ em, Bể bơi [trẻ em], Bữa ăn cho trẻ, Dịch vụ trông trẻ, Sân chơi, Công viên giải trí/nước, Phòng gia đình |
| **Bãi đỗ xe** | Bãi đỗ xe* |
| **Đưa đón sân bay / Di chuyển** | Đưa đón sân bay, Dịch vụ đưa đón, Dịch vụ taxi, Thuê xe đạp |
| **Điều hòa** | Điều hòa, Máy điều hòa ở khu vực chung |
| **Phòng tắm** | Bồn tắm, Vòi sen, phòng tắm riêng, Áo choàng tắm, Bồn tắm nước nóng |
| **Tiện nghi trong phòng** | Minibar/Tủ lạnh, Truyền hình, Máy sấy tóc, Két sắt, Ban công, Bàn làm việc, Ghế sofa |
| **Cách âm** | Cách âm, Phòng cách âm, Rèm che ánh sáng |
| **Nhận phòng** | Nhận phòng [24 giờ], Nhận/trả phòng [riêng] |
| **An toàn** | CCTV*, Bình chữa cháy, Bảo vệ, Đầu báo khói, Thiết bị báo cháy, Két sắt |
| **Tiện ích tại cơ sở lưu trú** *(catch‑all)* | Thang máy, Vườn, Sân hiên, Cửa hàng, Wi-Fi/Internet, Phòng họp, Máy chiếu… |

> Quy tắc gán: so khớp từ khoá (lowercase, bỏ ngoặc). Một amenity có thể vào nhiều cụm
> (vd *Quán bar cạnh bể bơi* → Bar + Bể bơi) → dùng công thức trung bình theo $m_j$ ở §2.1.

---

## 4. Pipeline xử lý dữ liệu

```text
# --- PRECOMPUTE (1 lượt qua toàn dataset) ---
R0_median = median(h.review_score/10 for h in hotels if h.review_score)   # = R̃0
# w̄_t: prior cụm shrunk theo pool toàn cục (k0=50), kéo về R̃0
num = defaultdict(float); den = defaultdict(float)
for hotel H, tag t in tất cả review:
    num[t] += t.mentioned * (t.positive_pct/100); den[t] += t.mentioned
wbar = { t: (num[t] + 50*R0_median) / (den[t] + 50) for t in den }

ALPHA = 0.5
def R0(H):                              # baseline không-bao-giờ-0
    return H.review_score/10 if H.review_score else R0_median
def prior(H, J):                        # empirical-Bayes: hotel × cụm
    g = [wbar[j] for j in J if j in wbar]   # cụm toàn cục (kể cả chưa review tại H)
    if g: return ALPHA*R0(H) + (1-ALPHA)*mean(g)
    return R0(H)                        # không thuộc cụm nào → chỉ điểm KS

for hotel H:
    # build điểm cụm từ review tags của H
    for tag t in H.reviews_detail.tags:
        m, p = t.mentioned, t.positive_pct
        c = m / (m + 20)
        w_cluster[t.tag] = c*(p/100) + (1-c)*prior(H, [t.tag])
        mentions[t.tag]  = m

    # --- HOTEL_AMENITY ---  (amenity CÓ mặt trong H.amenities)
    for amenity a in H.amenities:
        Jall = clusters_of(a)                    # tất cả cụm của a (theo bảng §3)
        J = [j for j in Jall if j in w_cluster]  # cụm CÓ review tại H
        nếu J rỗng:  w = prior(H, Jall)          # blend R0(H) × w̄ cụm → không còn = 0
        ngược lại:   w = Σ mentions[j]*w_cluster[j] / Σ mentions[j]
        w = max(w, 0.05)                         # sàn ε
        (H)-[:HAS_TAG {weight:w}]->(a)

    # --- REVIEW TAG trừu tượng ---  (§2.4: tag không phải amenity/demographic)
    for tag t in H.reviews_detail.tags if t.tag không thuộc cụm amenity nào:
        w = max(w_cluster[t.tag], 0.05)
        (H)-[:HAS_TAG {weight:w}]->(t.tag)

    # --- SUITABLE_FOR ---  (demographic CÓ mặt trong H.demographics)
    for nhóm g trong demographics (gom trùng tên):
        c_d = count/(count+50)
        w = c_d*(scorē/10) + (1-c_d)*prior(H, [g])   # g ∉ wbar → rơi về R0(H), không 0
        w = max(w, 0.05)
        (H)-[:HAS_TAG {weight:w}]->(g)
```

---

## 5. Ví dụ thực tế — Vinpearl Resort Nha Trang

`review_score = 8.7` → **`R₀ = 0.87`**, `k = 20`. Điểm từng cụm (từ review tag của Vinpearl):

| Cụm | mentioned | pos% | $c_j$ | **$w_j$** |
| --- | :-------: | :--: | :---: | :-------: |
| Dịch vụ | 184 | 69% | 0.90 | **0.71** |
| Bữa sáng | 136 | 77% | 0.87 | **0.78** |
| Bể bơi | 135 | 73% | 0.87 | **0.75** |
| Độ sạch sẽ | 122 | 62% | 0.86 | **0.66** |
| Bãi biển | 96 | 81% | 0.83 | **0.82** |
| Tiện ích cơ sở (catch‑all) | 42 | 76% | 0.68 | **0.80** |
| Cơ sở vật chất cho trẻ em | 34 | 73% | 0.63 | **0.78** |
| Nhiều lựa chọn nhà hàng | 34 | 50% | 0.63 | **0.64** |
| Phòng tắm | 29 | 41% | 0.59 | **0.60** |
| Nhận phòng | 46 | 26% | 0.70 | **0.45** |

→ Amenity thừa hưởng điểm cụm:

| Amenity | Cụm | **weight** |
| ------- | --- | :--------: |
| Dịch vụ phòng, Dọn phòng hằng ngày, Bàn tiếp tân [24 giờ] | Dịch vụ | **0.71** |
| Bữa sáng [tự chọn] | Bữa sáng | **0.78** |
| Bể bơi [ngoài trời] | Bể bơi | **0.75** |
| Bãi biển riêng | Bãi biển | **0.82** |
| CLB trẻ em, Sân chơi | Cơ sở vật chất cho trẻ em | **0.78** |
| Nhà hàng ẩm thực quốc tế | Nhiều lựa chọn nhà hàng | **0.64** |
| Vòi sen, Bồn tắm | Phòng tắm | **0.60** |
| Nhận phòng [24 giờ] | Nhận phòng | **0.45** |
| Quán bar cạnh bể bơi | Bar + Bể bơi *(trung bình theo m)* | **~0.75** |
| Thang máy, Vườn, Wi-Fi | Tiện ích cơ sở (catch‑all) | **0.80** |
| Spa, Mát-xa *(cụm Spa không được review tại Vinpearl)* | prior §2.3 = $0.5\,R_0+0.5\,\bar w_{\text{Spa}}$ | **≈0.86** |

Tính tay cụm **Dịch vụ**: `c = 184/204 = 0.902`; `w = 0.902·0.69 + 0.098·0.87 = 0.71`.

Công thức phân biệt rõ theo chủ đề: bãi biển 0.82 (khen) ≫ nhận phòng 0.45 (chê), đúng
trải nghiệm thật của khách.

**SUITABLE_FOR** (`k_d = 50`): Cặp đôi → **0.90**, Gia đình có trẻ nhỏ → **0.88**.

### Ví dụ KS không có review (sửa lỗi $w=0$)

*KS Bắc Kạn* — không review tag, không demographic, `review_score` rỗng → $R_0=\tilde R_0$.
Mọi amenity trước đây = 0; nay mỗi amenity nhận $\text{prior}=0.5\tilde R_0+0.5\bar w_{\text{cụm}}$,
phân hoá theo loại: *Phòng xông ướt* ≈ 0.87, *Bể bơi ngoài trời* ≈ 0.79, *Nhà tắm riêng*
≈ 0.72 — thay vì cùng = 0.

### Tham số

| Tham số | Ý nghĩa | Đề xuất |
| ------- | ------- | ------- |
| `k` | smoothing điểm cụm (review tag) | 20 |
| `k_d` | smoothing SUITABLE_FOR (demographics) | 50 |
| `k₀` | shrink prior cụm toàn cục $\bar w_t$ về $\tilde R_0$ (§2.3) | 50 |
| `α` | tỉ trọng hotel-vs-cụm trong prior (§2.3) | 0.5 |
| `ε` | sàn cho cạnh có mặt (§2.3) | 0.05 |

---

## 6. Kết nối User → Hotel qua Tag

```text
(User)-[:INTERESTED_IN {count, last_interaction}]->(Tag)
(Hotel)-[:HAS_TAG {weight}]->(Tag)
```

### 6.1 Công thức chấm điểm

Điểm sở thích user (time-decay, đúng §7 graph 1.md):

$$
\text{userScore}(U,t) = \text{interaction\_count}\times e^{-\lambda \Delta t}, \quad \lambda \approx 0.05
$$

$$
\text{MatchScore}(U,H) = \sum_{t \in T(U)\cap T(H)} \text{userScore}(U,t)\cdot w(H,t)
$$

Chuẩn hoá cosine:

$$
\text{Score}(U,H) = \frac{\text{MatchScore}(U,H)}
{\sqrt{\sum_t \text{userScore}^2}\;\cdot\;\sqrt{\sum_t w^2}} \in [0,1]
$$

### 6.2 Cypher

```cypher
MATCH (u:User {user_id:$uid})-[i:INTERESTED_IN]->(t:Tag)<-[h:HAS_TAG]-(hotel:Hotel)
WITH hotel, t,
     i.count * exp(-0.05 *
        duration.inDays(date(i.last_interaction), date()).days)  AS us,
     h.weight                                                    AS w
WITH hotel,
     sum(us * w)                          AS matchScore,
     sqrt(sum(us*us)) * sqrt(sum(w*w))    AS norm,
     collect(t.name)                      AS matchedTags
RETURN hotel.hotel_id, hotel.name,
       matchScore / norm AS score, matchedTags
ORDER BY score DESC
LIMIT 10
```

### 6.3 Mở rộng Room / Activity / Place

Cộng tag gián tiếp với hệ số chiết khấu theo loại quan hệ:

```cypher
MATCH (u:User {user_id:$uid})-[i:INTERESTED_IN]->(t:Tag)
MATCH (hotel:Hotel)
OPTIONAL MATCH (hotel)-[h:HAS_TAG]->(t)
OPTIONAL MATCH (hotel)-[:HAS_ROOM|OFFERS_ACTIVITY|NEAR]->()-[h2:HAS_TAG]->(t)
WITH hotel, i,
     coalesce(h.weight,0)*1.0 + coalesce(h2.weight,0)*0.5 AS edgeW
WHERE edgeW > 0
WITH hotel,
     i.count * exp(-0.05 *
        duration.inDays(date(i.last_interaction), date()).days) AS us, edgeW
RETURN hotel.hotel_id, sum(us * edgeW) AS score
ORDER BY score DESC LIMIT 10
```

### 6.4 Triển khai

| Phương án | Mô tả | Khi dùng |
| --------- | ----- | -------- |
| **On-query** | Tính điểm lúc truy vấn (time-decay tươi) | MVP — khớp §7 graph 1.md |
| **Materialized** | Job ghi `(User)-[:MATCHES {score}]->(Hotel)` | Khi traffic lớn |

`weight` precompute offline; chỉ `userScore` tính lúc query.

---

## 7. Mở rộng (ngoài MVP)

- **Độ hiếm (IDF):** nhân thêm $\ln(N/df)$ để phân biệt amenity trong cùng cụm (vd hạ
  trọng số amenity quá phổ thông như WiFi). Tuỳ chọn.
- **Cạnh Room:** áp cùng cơ chế cụm với `Room.review_score` + review tag liên quan phòng
  (Kích thước phòng, Bộ đồ giường, Thiết kế phòng…).
- **Bắc cầu ngữ nghĩa:** `(:Tag)-[:SIMILAR_TO {sim}]->(:Tag)`.

---

## 8. Tóm tắt

| Hạng mục | Kết quả |
| -------- | ------- |
| **Ý tưởng** | Gom amenity thành **cụm chủ đề**; mỗi cụm thừa hưởng điểm review tag (`positive_pct`) |
| `HAS_TAG.weight` (amenity) | $w = \max\!\big(\frac{\sum_j m_j w_j}{\sum_j m_j},\varepsilon\big)$, với $w_j = c_j\frac{p_j}{100}+(1-c_j)\,\text{prior}_j$, $c_j=\frac{m_j}{m_j+20}$ |
| `HAS_TAG.weight` (suitable_for) | $w = \max\!\big(c_d\frac{\overline{score}}{10}+(1-c_d)\,\text{prior},\varepsilon\big)$, $c_d=\frac{count}{count+50}$ |
| `prior` (§2.3) | $\alpha R_0(H)+(1-\alpha)\bar w_t$; $R_0$ rỗng → $\tilde R_0$; $\bar w_t=\frac{\sum m S+k_0\tilde R_0}{\sum m+k_0}$ |
| Vắng mặt vs thiếu review | KS không có tag → **không có cạnh** (không phải $w=0$). Tag có mặt nhưng thiếu review → prior 2 thành phần $\alpha R_0(H)+(1-\alpha)\bar w_t$, $R_0$ rỗng dùng $\tilde R_0$, sàn $\varepsilon$ → **không bao giờ 0** |
| Lỗi gốc đã sửa | 162 cạnh `HOTEL_AMENITY=0` ở 10 KS không-review (R₀=0) — nay nhận prior phân hoá theo cụm |
| Coverage | Review tag trừu tượng (Địa điểm, Đáng tiền, Không khí…) tạo cạnh trực tiếp $w=w_t$ |
| Nguồn | `reviews_detail.tags` (cụm), `reviews_detail.demographics`, `Hotel.review_score`. **Không** amenity_groups / grades |
| Tham số | `k=20`, `k_d=50`, `k₀=50`, `α=0.5`, `ε=0.05` |
| Nối User–Hotel | $\sum userScore\cdot weight$, chuẩn hoá cosine, time-decay. MVP on-query |