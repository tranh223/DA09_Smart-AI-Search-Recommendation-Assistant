"""
Tính trọng số cạnh HAS_TAG theo phương án §2.3 (graph_edge_weighting.md):
prior trộn theo độ tin cậy  prior = α(H)·R0(H) + (1-α(H))·w̄_cụm,  α(H)=n_H/(n_H+kα).

Đọc dump Postgres (data.sql), xuất CSV cùng schema với dump Neo4j:
cityName, hotelId, hotelName, tagName, tagCategory, weight.

Mục tiêu: KHÔNG còn cạnh nào weight = 0.
"""
import csv
import statistics
import sys
from collections import defaultdict

SQL_PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\Project\Vin AI\VSF\local\data\data.sql"
OUT_CSV = sys.argv[2] if len(sys.argv) > 2 else r"C:\Project\Vin AI\VSF\local\data\tag_weights.csv"

# Tham số (graph_edge_weighting.md §5)
K = 20          # smoothing điểm cụm cục bộ
K_D = 50        # smoothing SUITABLE_FOR
K0 = 50         # shrink prior cụm toàn cục về R̃0
K_ALPHA = 50    # smoothing độ tin cậy α(H)
ALPHA_MIN = 0.0
EPS = 0.05      # sàn
MENTION_MIN = 4 # ngưỡng nhãn đánh giá (như tag_statistics)

NULL = "\\N"
END = "\\."


def read_copy(path, header):
    rows, cap = [], False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not cap:
                if line.startswith(header):
                    cap = True
                continue
            if line.startswith(END):
                break
            rows.append(line.rstrip("\n").split("\t"))
    return rows


# --- Gán amenity -> cụm chủ đề (= aspect review). Theo bảng taxonomy §3, khớp từ khoá.
#     Một amenity có thể vào nhiều cụm; không khớp gì -> catch-all.
CATCHALL = "Tiện ích tại cơ sở lưu trú"
CLUSTER_KEYWORDS = {
    "Dịch vụ": ["dịch vụ phòng", "giặt là", "ủi đồ", "giặt khô", "tiếp tân", "lễ tân",
                "dọn phòng", "giữ hành lý", "nhân viên", "báo thức", "đổi ngoại tệ", "rút tiền"],
    "Độ sạch sẽ": ["khử trùng", "rửa tay", "vật dụng tắm rửa", "vệ sinh"],
    "Bữa sáng": ["bữa sáng"],
    "Nhiều lựa chọn nhà hàng": ["nhà hàng", "quán cà phê", "đồ ăn vặt", "trái cây"],
    "Bar": ["quán bar", "rượu", "bar"],
    "Bể bơi": ["bể bơi", "hồ bơi"],
    "Bãi biển": ["bãi biển"],
    "Spa": ["spa", "mát-xa", "xông khô", "xông ướt", "làm đẹp"],
    "Phòng tập": ["phòng tập", "quần vợt", "thể thao", "lặn", "bóng bàn", "phi tiêu", "cầu lông"],
    "Cơ sở vật chất cho trẻ em": ["trẻ em", "trông trẻ", "sân chơi", "công viên",
                                   "gia đình", "em bé"],
    "Bãi đỗ xe": ["đỗ xe", "bãi đỗ"],
    "Đưa đón sân bay": ["đưa đón sân bay", "dịch vụ đưa đón", "taxi", "thuê xe đạp", "xe đạp"],
    "Điều hòa": ["điều hòa"],
    "Phòng tắm": ["bồn tắm", "vòi sen", "phòng tắm", "áo choàng tắm", "nhà tắm"],
    "Tiện nghi trong phòng": ["minibar", "tủ lạnh", "truyền hình", "máy sấy", "két sắt",
                               "ban công", "bàn làm việc", "ghế sofa", "tivi", "tv"],
    "Cách âm": ["cách âm", "rèm che"],
    "Nhận phòng": ["nhận phòng", "nhận/trả phòng", "nhận trả phòng"],
    "An toàn": ["cctv", "chữa cháy", "bảo vệ", "báo khói", "báo cháy"],
    "Bếp": ["bếp", "nấu nướng", "lò vi sóng", "đồ dùng làm bếp", "máy rửa bát"],
    "Wi-Fi": ["wifi", "wi-fi", "internet"],
}


def clusters_of(name):
    low = name.lower()
    hit = [c for c, kws in CLUSTER_KEYWORDS.items() if any(k in low for k in kws)]
    return hit if hit else [CATCHALL]


def main():
    hotels = read_copy(SQL_PATH, "COPY public.hotels ")
    amenities = read_copy(SQL_PATH, "COPY public.amenities ")
    hotel_amen = read_copy(SQL_PATH, "COPY public.hotel_amenities ")
    suit = read_copy(SQL_PATH, "COPY public.hotel_suitability ")
    aspects = read_copy(SQL_PATH, "COPY public.review_aspects ")

    # hotels: id,name,property_type,accommodation_type,star_rating,is_luxury,
    #         review_score,review_count,address,city,...
    H = {}
    for r in hotels:
        H[r[0]] = {
            "name": r[1],
            "acc_type": None if r[3] == NULL else r[3],
            "score": None if r[6] == NULL else float(r[6]),
            "count": 0 if r[7] == NULL else int(r[7]),
            "city": None if r[9] == NULL else r[9],
        }

    # R̃0 = trung vị review_score/10
    R_TIL = statistics.median([h["score"] / 10 for h in H.values() if h["score"]])

    # w̄_t: prior cụm toàn cục (shrunk k0) — chỉ tính aspect mentioned > MENTION_MIN
    g_num, g_den = defaultdict(float), defaultdict(float)
    for r in aspects:
        m, p = float(r[3]), float(r[4])
        if m > MENTION_MIN:
            g_num[r[2]] += m * (p / 100)
            g_den[r[2]] += m
    wbar = {t: (g_num[t] + K0 * R_TIL) / (g_den[t] + K0) for t in g_den}

    def R0(h):
        return h["score"] / 10 if h["score"] else R_TIL

    def alpha(h):
        n = h["count"]
        return max(ALPHA_MIN, n / (n + K_ALPHA))

    def prior(h, J):
        gl = [wbar[j] for j in J if j in wbar]
        a = alpha(h)
        glob = statistics.mean(gl) if gl else R_TIL
        return a * R0(h) + (1 - a) * glob

    amen_name = {r[0]: r[1] for r in amenities}
    amen_by_hotel = defaultdict(list)
    for hid, aid in hotel_amen:
        amen_by_hotel[hid].append(aid)
    suit_by_hotel = defaultdict(list)
    for r in suit:  # id,hotel_id,suitable_for_tag,mention_count,score
        suit_by_hotel[r[1]].append(r)
    asp_by_hotel = defaultdict(list)
    for r in aspects:  # id,hotel_id,aspect_name,mentioned,positive_pct
        if float(r[3]) > MENTION_MIN:
            asp_by_hotel[r[1]].append(r)

    out = []

    def emit(h, hid, tag, cat, w):
        out.append({
            "cityName": h["city"] or "",
            "hotelId": hid,
            "hotelName": h["name"],
            "tagName": tag,
            "tagCategory": cat,
            "weight": round(max(w, EPS), 4),
        })

    for hid, h in H.items():
        # điểm cụm cục bộ từ review aspect của KS này
        w_cluster, mentions = {}, {}
        for r in asp_by_hotel[hid]:
            name, m, p = r[2], float(r[3]), float(r[4])
            c = m / (m + K)
            w_cluster[name] = c * (p / 100) + (1 - c) * prior(h, [name])
            mentions[name] = m

        # HOTEL_TYPE — hằng số 1.0 (như dump)
        if h["acc_type"]:
            emit(h, hid, h["acc_type"], "HOTEL_TYPE", 1.0)

        # HOTEL_AMENITY
        for aid in amen_by_hotel[hid]:
            nm = amen_name.get(aid)
            if not nm:
                continue
            Jall = clusters_of(nm)
            J = [j for j in Jall if j in w_cluster]   # cụm CÓ review tại KS
            if J:
                w = sum(mentions[j] * w_cluster[j] for j in J) / sum(mentions[j] for j in J)
            else:
                w = prior(h, Jall)
            emit(h, hid, nm, "HOTEL_AMENITY", w)

        # REVIEW_TAG — cạnh trực tiếp (§2.4)
        for name, w in w_cluster.items():
            emit(h, hid, name, "REVIEW_TAG", w)

        # SUITABLE_FOR
        for r in suit_by_hotel[hid]:
            tag = r[2]
            count = 0 if r[3] == NULL else int(r[3])
            score = None if r[4] == NULL else float(r[4])
            c_d = count / (count + K_D)
            base = (score / 10) if score else prior(h, [tag])
            w = c_d * base + (1 - c_d) * prior(h, [tag])
            emit(h, hid, tag, "SUITABLE_FOR", w)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=["cityName", "hotelId", "hotelName",
                                           "tagName", "tagCategory", "weight"])
        wr.writeheader()
        wr.writerows(out)

    # --- Kiểm tra zero ---
    zeros = [e for e in out if e["weight"] == 0]
    by_cat = defaultdict(int)
    for e in out:
        by_cat[e["tagCategory"]] += 1
    print(f"R̃0 = {R_TIL:.4f} | aspect có w̄: {len(wbar)}")
    print(f"Tổng cạnh: {len(out)} | theo loại: {dict(by_cat)}")
    print(f"Cạnh weight == 0: {len(zeros)}")
    nonzero = [e['weight'] for e in out]
    print(f"min weight = {min(nonzero)} | max = {max(nonzero)}")
    print(f"→ CSV: {OUT_CSV}")
    if zeros:
        print("CÒN ZERO:", zeros[:10])


if __name__ == "__main__":
    main()
