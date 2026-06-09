"""
Generate graph-friendly mock OTA user profiles from user-profile/schema.json.

Output:
    mock_user_profiles.json

Usage:
    python user-profile/generate_mock_user_profiles.py
"""

import json
import random
from datetime import date
from pathlib import Path


USER_COUNT = 50
RANDOM_SEED = 20260608
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "mock_user_profiles.json"
SESSION_CURRENT_DATE = date.today()

random.seed(RANDOM_SEED)


TRAVELER_TYPES = ["explorer", "comfort_seeker", "planner", "spontaneous"]
TRIP_TYPES = [
    "Nhóm du khách",
    "Cặp đôi",
    "Khách du lịch một mình",
    "Gia đình có trẻ nhỏ",
    "Gia đình có thanh thiếu niên",
    "Khách đi công tác",
]
BUDGET_LEVELS = ["low", "medium", "high"]
PREFERENCE_SIGNALS = ["luxury", "comfort", "quiet", "privacy", "unique", "safety", "vibrant"]

ROOM_VIEWS = [
    "Hướng Thành phố",
    "Hướng Biển",
    "Hướng Thiên nhiên",
    "Hướng Ngoài trời",
    "Hướng Bể bơi",
    "Hướng Núi",
    "Hướng Sông",
    "Hướng Hồ",
    "Hướng Không có cửa sổ",
]

HOTEL_TYPES = [
    "Khách sạn",
    "Nhà nghỉ",
    "Căn hộ dịch vụ",
    "Nhà dân",
    "Nhà khách / Nhà nghỉ B&B",
    "Ryokan",
    "Resort",
    "Toàn bộ căn nhà",
    "Nhà nghỉ ven đường",
    "Biệt thự nghỉ dưỡng",
    "Căn hộ",
    "Biệt thự",
]

AMENITIES = [
    "Điều hòa",
    "Giải trí",
    "Truyền hình cáp vệ tinh",
    "TV màn hình phẳng",
    "WiFi miễn phí",
    "Bếp",
    "Tủ lạnh",
    "Máy pha trà cà phê",
    "Giường cũi của em bé theo yêu cầu",
    "Ban công sân hiên",
    "Cách âm",
    "Sưởi",
    "Thang máy",
    "Phòng tắm đứng",
    "Có các phòng thông nhau",
    "Dịch vụ phát trực tuyến như netflix",
    "Điều hòa cá nhân",
    "WiFi tính phí",
    "Không gian làm việc cho máy tính xách tay",
    "Phim theo yêu cầu",
    "Tiện nghi bể bơi",
    "Nhà vệ sinh phụ",
    "Lò vi sóng",
    "Sử sụng clb thể thao",
    "Khu vực ăn uống riêng",
    "Giường gấp",
    "Máy rửa bát",
    "Lối vào hồ bơi",
    "Lối đi riêng",
    "Báo động trực quan",
    "Ít gây dị ứng",
    "Phòng thay đồ",
    "TV có phụ đề",
    "Đồ gỗ ngoài trời",
    "Tay nắm đòn bẩy trên cửa",
    "Bồn tắm tạo sóng",
    "Máy sấy quần áo",
    "Phòng tắm có băng ghế tắm",
    "Được vào phòng chờ thương gia",
    "Giường cực dài",
    "Phòng tắm có lối đi thoai thoải",
    "Nhà vệ sinh cho người khuyết tật",
    "Thanh vịn chống trượt",
    "Phòng khách riêng",
    "Tầng cao",
    "Đèn đọc sách",
    "Báo hằng ngày",
    "Trạm nối ipod",
    "Bàn trang điểm phù hợp cho người khuyết tật",
    "Đi lên bằng cầu thang",
    "Cửa sổ có thể mở ra",
    "Bể bơi",
    "Máy giặt",
    "Máy lọc không khí",
    "Tương thích với tty ttd",
    "Đồ dùng làm bếp",
    "Phòng tắm dành cho người khuyết tật",
    "Thiết bị chơi điện tử",
    "Phòng tắm phụ",
    "Cửa an toàn cho em bé",
    "Ghế cao cho trẻ con ngồi ăn",
    "Lò sưởi",
    "Bảng chỉ dẫn chữ nổi và sờ được",
    "Phòng và hoặc bộ dụng cụ phù hợp cho người khiếm thính",
    "Tiện nghi cho em bé theo yêu cầu",
    "Tầng thượng",
    "Miễn phí sử dụng khu vực dịch vụ hành chánh",
    "Báo động âm thanh",
    "Đồ uống mời khách miễn phí",
    "Căn hộ riêng trong tòa nhà",
    "Bãi biển riêng",
    "Được phép đưa thú nuôi vào",
    "Nhà tắm chung",
    "Thiết bị phát dữ liệu di động",
    "Quyền sử dụng spa miễn phí",
    "Thiết bị bảo vệ ban đêm hạ thấp trên cửa",
    "Xông khô",
    "Tầng hạn chế",
    "Trò chơi board game xếp hình",
    "Cho phép hút thuốc",
    "TV trong phòng tắm",
    "Máy tính bảng trong phòng",
    "Thiết bị điện thoại thông minh",
    "Bồn tắm lộ thiên",
    "Bộ hoạt động",
    "Máy tính",
    "Tắm suối nước nóng",
    "Bảng phi tiêu",
]

SESSION_AMENITIES = AMENITIES

LONG_TERM_ENOUGH_FIELDS = [
    "nationality",
    "age_group",
    "current_workplace",
]

SESSION_ENOUGH_FIELDS = [
    "destination",
    "current_location",
    "nearby_place",
    "number_of_guests",
    "check_in",
    "check_out",
]

AVOID_PREFERENCE_HABITS = [
    "noisy",
    "nightlife",
    "far_from_center",
    "shared_room",
    "low_rating",
    "old_facility",
    "small_room",
    "unsafe_area",
    "crowded",
    "limited_service",
    "poor_cleanliness",
]

AVOID_LOCATIONS = [
    "red_light_area",
    "crowded_center",
    "remote_area",
    "industrial_area",
    "night_market_area",
    "isolated_area",
    "far_from_airport",
]

DESTINATIONS = [
    "Phu Quoc",
    "Da Nang",
    "Nha Trang",
    "Da Lat",
    "Ha Noi",
    "Ho Chi Minh City",
    "Hoi An",
    "Hue",
    "Vung Tau",
    "Sa Pa",
    None,
]

CURRENT_LOCATIONS = [
    "Ha Noi",
    "Ho Chi Minh City",
    "Da Nang",
    "Can Tho",
    "Hai Phong",
    "Tokyo",
    "Seoul",
    "Singapore",
    "Paris",
    "London",
    "Berlin",
    "Sydney",
    "Bangkok",
    "Kuala Lumpur",
    None,
]

NEARBY_PLACES = [
    "Vịnh",
    "Công Viên Giải Trí",
    "Khu Nghỉ Trượt Tuyết",
    "Địa điểm giải trí",
    "Phố Nổi Tiếng",
    "Trung Tâm và Khu Mua Sắm",
    "Đảo",
    "Ngân Hàng và Quầy Đổi Ngoại Tệ",
    "Sân Gôn",
    "Chăm sóc Tóc và Làm Đẹp",
    "Trường Cao Đẳng và Đại Học",
    "Cửa Hiệu",
    "Bãi Biển",
    "Trung tâm Thể thao và Bể bơi",
    "Cao Ốc Văn Phòng",
    "Viện Bảo Tàng và Phòng Trưng Bày Nghệ Thuật",
    "Đồn Cảnh Sát và Dịch Vụ Khẩn Cấp",
    "Công Viên Công Cộng",
    "Suối nước nóng và thác nước tự nhiên",
    "Quán Rượu",
    "Đại Sứ Quán và Lãnh Sự Quán",
    "Sòng Bạc",
    "Nghĩa Trang",
    "Nhà máy rượu",
    "Tòa Nhà Lịch Sử",
    "Dịch Vụ Internet, Bưu Chính và Điện Thoại",
    "Ga Tàu Hoả, Ga Tàu Điện Ngầm và Bến Xe Buýt",
    "Trung tâm thể thao và Yoga",
    "Núi, đồi và hang động",
    "Bệnh Viện và Cơ Sở Y Tế",
    "Vườn Bách Thảo và Vườn Thú",
    "Siêu Thị",
    "Nơi Thờ Cúng",
    "Bến Cảng và Bến Đò",
    "Nơi Biểu Diễn Văn Nghệ",
    "Điểm Cắm Trại và Vui Chơi Ngoài Trời",
    "Cửa Hàng Đồ Cổ",
    "Bến Du Thuyền",
    "Nhà hát",
    "Spa",
    "Chợ",
    "Cây xăng",
    "Điểm Tham Quan",
    "Thư Viện",
    "Phương Tiện Vận Chuyển",
    "Sông và Hồ",
    "Nơi Biểu Diễn Âm Nhạc",
    "Công Viên Quốc Gia",
    "Đài Kỷ Niệm và Di Tích Lịch Sử",
    "Các Sân Thể Thao",
    "Thông Tin Du Lịch và Du Hành",
    "Trung Tâm Hội Nghị và Triển Lãm",
    "Bãi đỗ xe",
    "Sân Bay",
    "Cầu",
    "Tòa Nhà Nổi Tiếng",
    None,
]

VIETNAMESE_NAMES = [
    "Minh Anh Nguyen",
    "Hoang Nam Tran",
    "Thu Ha Le",
    "Gia Huy Pham",
    "Thanh Tung Do",
    "Quoc Bao Nguyen",
    "Mai Linh Hoang",
    "Duc Anh Bui",
    "Anh Khoa Vo",
    "Phuong Thao Mai",
    "Gia Bao Le",
    "Khanh Vy Nguyen",
    "Thanh Son Pham",
    "Linh Nguyen",
    "Ngoc Tran",
]

FOREIGN_NAMES = [
    "Emily Carter",
    "Michael Brown",
    "Yuki Sato",
    "Minjun Kim",
    "Claire Dubois",
    "Robert Wilson",
    "Anna Muller",
    "Sarah Johnson",
    "Thomas Lee",
    "Maria Garcia",
    "Luca Rossi",
    "Hannah Schmidt",
    "Noah Anderson",
    "Emma Taylor",
    "David Wilson",
]

HOTEL_IDS = [
    int(hotel_id)
    for hotel_id in """
1015998
10247322
1031547
1032041
1032420
104012
104013
10412
10416
10425
1062253
10626
10670772
10681
10776988
108286
108442
10911
109118
109119
72239055
10916
10940
10961
10962
10964
10976
11002
11025533
11081745
11107
11124549
1122443
1122450
11282197
1176921
1129327
11488
1156925
1157572
1157822
1157856
1158176
1165930
1179398
1187357
1189049
12132
1233488
1254360
1294417
1373800
1377626
14626926
14677144
146978
148821
149036
149160
1516
1519798
1519974
1576565
15896111
15947856
1602545
16093065
161676
1623760
1624474
16260062
16360312
16366479
165511
1657828
165827
16689505
16743950
16787998
168856
168993
17163180
173535
17526164
178195
179033
179623
18172050
181803
182167
18468242
18759561
19105827
195880
196020
197223
72270070
1973
1984611
1985160
1985188
1985199
1986410
1989653
1994212
1994625
1999073
20061348
2009
200945
30897715
20375914
205055
205473
209161
2096159
2096359
2096402
2096415
210187
2163076
23388080
2167475
2183
2190907
21971824
223488
22406185
2241482
22420717
22596876
2265300
230582
230600
23071123
2308501
72270145
237603
23910443
24112682
24247480
2430124
2448869
2450834
2451597
2455001
25455208
2455013
2455164
2457506
2458995
246183
72421975
2462129
2462240
2464163
2464815
2465074
2465242
2466674
2466865
2466930
247372
247789
251637
2543676
2544429
255050
25559635
255755
256251
2562742
263218
263516
2651688
2651835
2666672
2669080
2673008
2673101
2730316
2673631
271561
272190
272227
272316
2731031
27874314
279374
28081416
28109380
2811560
281497
28201768
287957
31070914
289726
289832
290212
292633
297705
29459054
29464613
29464681
296804
304294
297968
2985143
30154593
303011
3124532
31461091
31491037
31561179
315667
31567033
31642453
31679160
32260660
32879699
32914376
33425968
334589
33499898
3356949
33589745
3359566
3365294
336669
3367487
33815684
33907335
339080
33941236
339975
34047130
34054260
34118773
34309695
344435
34513919
34513922
34513923
34995846
35243975
35308672
35351745
35444743
35750047
36219875
36224135
3664358
36919571
36962500
36975063
37697306
39532985
37710972
37718747
37817493
37890562
38002254
3849621
38583105
38591390
38684158
39786122
39900379
399935
400013
400829
401199
40355370
410128
411089
411887
4125675
4125682
4125695
412707
4128513
4139218
41926154
42154394
42817
428973
433003
4332
43499
488143
43573013
43602
43797
44205914
443116
444892
4459783
446043
44605
488373
44608
44777877
4518434
45688641
4593719
4594028
4594031
460438
46045575
488398
4612442
462535
462536
46265
75690457
4638608
465187
4663
46698614
79830374
46718
46763704
46778460
46874
46886612
46992320
47101
47212
47218637
547010
47843559
48029813
48041432
48041444
48363
48364
48484
48699
4898044
4898290
49072
49165
548000
49385769
4942635
4947690
49682296
80578160
4974064
49743
49851722
50046430
50046456
5006
502099
5030530
5101943
51060966
51568479
51620224
51816062
52287699
523102
529354
5305073
5314071
535532
5368161
542
544328
548302
5500799
55268476
55335029
565102
555388
55544473
55745075
55835384
63699798
5663774
5663879
5663891
567771
5685860
5686721
569205
5743855
63725005
5780775
5796589
5797972
5825399
58354137
5873574
5877654
58875018
58908257
5905722
5920941
59351136
59457554
5946705
60903194
617191
6185262
62114174
62125328
621752
623424
624034
6251087
625168
6255260
625890
625947
625950
63083771
63273468
63302
63314499
63347126
6357553
63695627
6377313
6377853
63898213
6393486
64058128
64197763
6421211
6428322
64328099
6907350
64504871
64524752
64560122
64586328
64906867
6492371
65153
652133
65275240
65276989
65343180
6542427
65540
6578534
65822922
65868132
66106
661189
66525
70417406
6663
6757
67791043
68691582
6906462
69251
69253318
69352
70071649
70410096
70462775
70467573
706023
70980621
72136942
7292110
73359010
73383102
736941
7380
73809693
73884743
73890573
74073
75646574
74077
74356775
745965
746244
746744
746782
75207
75244511
75824399
75897171
75935367
76127170
76161592
7621610
76408187
76585258
766807
76814402
76868357
77605
78077622
78139
782765
78340310
78947444
7911593
79143883
80237852
80378
80497
805030
80669
81115
82014402
8213119
831854
83464707
83464709
83499580
84488355
8883
84613403
84901473
84960
85302956
85303708
85304405
85304449
85304732
85305028
85723058
85952752
859981
86658383
87142652
87252891
87262559
87288230
87755467
88056589
894894
90355
91750
9195
9258
926899
926909
9372539
93823
9516359
97518
9755468
9776735
98168
983538
98432
""".split()
]


def maybe_null(value, probability=0.06):
    return None if random.random() < probability else value


def signal_count(min_count=1, max_count=30):
    return random.randint(min_count, max_count)


def signal(count=None):
    count = count if count is not None else signal_count()
    return {
        "count": count,
        "last_interaction": SESSION_CURRENT_DATE.isoformat(),
    }


def weighted_map(items, min_n=1, max_n=4, null_p=0.07, empty_p=0.08):
    roll = random.random()
    if roll < null_p:
        return None
    if roll < null_p + empty_p:
        return {}

    count = random.randint(min_n, min(max_n, len(items)))
    return {item: signal() for item in random.sample(items, count)}


def negative_weighted_map(items, min_n=0, max_n=3, empty_p=0.35):
    if random.random() < empty_p:
        return {}

    count = random.randint(min_n, min(max_n, len(items)))
    if count == 0:
        return {}

    return {item: signal() for item in random.sample(items, count)}


def signal_rank(value):
    return value["count"]


def has_enough_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def fields_are_enough(container, required_fields):
    return all(has_enough_value(container.get(field)) for field in required_fields)


def refresh_is_enough(profile):
    long_term = profile["long_term_profile"]
    session = profile["session_context"]
    long_term["is_enough"] = fields_are_enough(long_term, LONG_TERM_ENOUGH_FIELDS)
    session["is_enough"] = fields_are_enough(session, SESSION_ENOUGH_FIELDS)


def price_range(budget_levels):
    if not budget_levels:
        return {"min": None, "max": None, "currency": None}

    top_level = max(budget_levels, key=lambda key: signal_rank(budget_levels[key]))
    ranges = {
        "low": [(300000, 1500000), (500000, 1800000), (None, 2000000)],
        "medium": [(1500000, 3500000), (2000000, 5000000), (None, 4500000)],
        "high": [(4000000, 9000000), (5000000, 12000000), (7000000, 15000000)],
    }
    min_price, max_price = random.choice(ranges[top_level])
    return {
        "min": min_price,
        "max": max_price,
        "currency": "VND" if min_price is not None or max_price is not None else None,
    }


def date_pair():
    if random.random() < 0.4:
        return None, None

    month = random.choice([7, 8, 9, 10, 11, 12])
    day = random.randint(1, 23)
    stay = random.randint(1, 5)
    return f"2026-{month:02d}-{day:02d}T14:00:00", f"2026-{month:02d}-{day + stay:02d}T12:00:00"


def recommendation_clicks(empty_p=0.18, null_p=0.06):
    roll = random.random()
    if roll < null_p:
        return None
    if roll < null_p + empty_p:
        return {"hotel": []}

    count = random.randint(1, 5)
    return {"hotel": random.sample(HOTEL_IDS, count)}


def guest_count(trip_types):
    if not trip_types:
        return None

    top_trip = max(trip_types, key=lambda key: signal_rank(trip_types[key]))
    if top_trip == "Khách du lịch một mình":
        return 1
    if top_trip == "Cặp đôi":
        return 2
    if top_trip == "Khách đi công tác":
        return random.choice([1, 2])
    if top_trip == "Gia đình có trẻ nhỏ":
        return random.choice([3, 4, 5, 6])
    if top_trip == "Gia đình có thanh thiếu niên":
        return random.choice([3, 4, 5])
    if top_trip == "Nhóm du khách":
        return random.choice([4, 5, 6, 8])
    return random.choice([1, 2, 3])


def negative_preferences(amenities):
    nearby_places = [place for place in NEARBY_PLACES if place is not None]
    return {
        "avoid_hotel_types": negative_weighted_map(HOTEL_TYPES, 0, 2),
        "avoid_amenities": negative_weighted_map(amenities, 0, 2),
        "avoid_preference_habits": negative_weighted_map(AVOID_PREFERENCE_HABITS, 1, 3, empty_p=0.22),
        "avoid_nearby_places": negative_weighted_map(nearby_places, 0, 2, empty_p=0.5),
        "avoid_locations": negative_weighted_map(AVOID_LOCATIONS, 0, 2, empty_p=0.45),
    }


def cold_start_profile(index, name, nationality):
    profile = {
        "user_id": f"user_{index:03d}",
        "name": maybe_null(name, 0.35),
        "long_term_profile": {
            "nationality": maybe_null(nationality, 0.45),
            "age_group": None,
            "current_workplace": None,
            "is_enough": random.choice([False, False, None]),
            "traveler_type": {},
            "long_term_trip_types": {},
            "long_term_budget_levels": {},
            "long_term_price_range": {"min": None, "max": None, "currency": None},
            "long_term_preference_habits": {},
            "long_term_hotel_types": {},
            "long_term_room_views": {},
            "long_term_amenities": {},
            "recommendation_clicks": recommendation_clicks(empty_p=0.7, null_p=0.1),
            "long_term_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_preference_habits": {},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
        },
        "session_context": {
            "destination": random.choice(DESTINATIONS),
            "current_location": None,
            "nearby_place": None,
            "number_of_guests": None,
            "has_pet": None,
            "has_children": None,
            "check_in": None,
            "check_out": None,
            "is_enough": False,
            "session_trip_types": {},
            "session_budget_levels": {},
            "session_price_range": {"min": None, "max": None, "currency": None},
            "session_preference_habits": {},
            "session_hotel_types": {},
            "session_room_views": {},
            "session_amenities": {},
            "session_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_preference_habits": {},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
        },
    }
    refresh_is_enough(profile)
    return profile


def standard_profile(index, name, nationality):
    age_group = maybe_null(random.choice(["under_25", "25_35", "over_35"]), 0.08)
    long_nationality = maybe_null(nationality, 0.05)
    traveler_type = weighted_map(TRAVELER_TYPES, 1, 2, null_p=0.06, empty_p=0.08)
    long_trip_types = weighted_map(TRIP_TYPES, 1, 2, null_p=0.05, empty_p=0.06)
    long_budget_levels = weighted_map(BUDGET_LEVELS, 1, 2, null_p=0.06, empty_p=0.05)
    long_preference_habits = weighted_map(PREFERENCE_SIGNALS, 1, 3)
    long_hotel_types = weighted_map(HOTEL_TYPES, 1, 4)
    long_room_views = weighted_map(ROOM_VIEWS, 1, 3)
    long_amenities = weighted_map(AMENITIES, 1, 5)
    session_budget_levels = weighted_map(BUDGET_LEVELS, 1, 2, null_p=0.08, empty_p=0.08)
    session_trip_types = weighted_map(TRIP_TYPES, 1, 2, null_p=0.05, empty_p=0.08)
    check_in, check_out = date_pair()
    guests = guest_count(session_trip_types)
    top_session_trip = (
        max(session_trip_types, key=lambda key: signal_rank(session_trip_types[key])) if session_trip_types else None
    )
    long_term_profile = {
        "nationality": long_nationality,
        "age_group": age_group,
        "current_workplace": random.choice(CURRENT_LOCATIONS),
        "is_enough": None,
        "traveler_type": traveler_type,
        "long_term_trip_types": long_trip_types,
        "long_term_budget_levels": long_budget_levels,
        "long_term_price_range": price_range(long_budget_levels),
        "long_term_preference_habits": long_preference_habits,
        "long_term_hotel_types": long_hotel_types,
        "long_term_room_views": long_room_views,
        "long_term_amenities": long_amenities,
        "recommendation_clicks": recommendation_clicks(),
        "long_term_negative_preferences": negative_preferences(AMENITIES),
    }
    session_context = {
        "destination": random.choice(DESTINATIONS),
        "current_location": random.choice(CURRENT_LOCATIONS),
        "nearby_place": random.choice(NEARBY_PLACES),
        "number_of_guests": guests,
        "has_pet": True if random.random() < 0.12 else random.choice([False, False, None]),
        "has_children": (
            True
            if top_session_trip in {"Gia đình có trẻ nhỏ", "Gia đình có thanh thiếu niên"} and random.random() < 0.7
            else random.choice([False, False, None])
        ),
        "check_in": check_in,
        "check_out": check_out,
        "is_enough": False,
        "session_trip_types": session_trip_types,
        "session_budget_levels": session_budget_levels,
        "session_price_range": price_range(session_budget_levels),
        "session_preference_habits": weighted_map(PREFERENCE_SIGNALS, 1, 4),
        "session_hotel_types": weighted_map(HOTEL_TYPES, 1, 3),
        "session_room_views": weighted_map(ROOM_VIEWS, 1, 3),
        "session_amenities": weighted_map(SESSION_AMENITIES, 1, 5),
        "session_negative_preferences": negative_preferences(SESSION_AMENITIES),
    }
    profile = {
        "user_id": f"user_{index:03d}",
        "name": maybe_null(name, 0.04),
        "long_term_profile": long_term_profile,
        "session_context": session_context,
    }
    refresh_is_enough(profile)
    return profile


def apply_demo_overrides(profiles):
    if len(profiles) < 15:
        return

    profiles[0] = {
        "user_id": "user_001",
        "name": "Minh Anh Nguyen",
        "long_term_profile": {
            "nationality": "vietnamese",
            "age_group": "under_25",
            "current_workplace": "Ho Chi Minh City",
            "is_enough": True,
            "traveler_type": {"explorer": signal(28)},
            "long_term_trip_types": {"Khách du lịch một mình": signal(29)},
            "long_term_budget_levels": {"low": signal(27)},
            "long_term_price_range": {"min": 500000, "max": 1800000, "currency": "VND"},
            "long_term_preference_habits": {"unique": signal(27), "vibrant": signal(21), "safety": signal(17)},
            "long_term_hotel_types": {"Nhà dân": signal(26), "Nhà nghỉ": signal(22), "Nhà khách / Nhà nghỉ B&B": signal(18)},
            "long_term_room_views": {"Hướng Biển": signal(26), "Hướng Thành phố": signal(18)},
            "long_term_amenities": {"WiFi miễn phí": signal(27), "Máy pha trà cà phê": signal(15)},
            "recommendation_clicks": {"hotel": [104013, 72239055]},
            "long_term_negative_preferences": {
                "avoid_hotel_types": {"Biệt thự nghỉ dưỡng": signal(12)},
                "avoid_amenities": {},
                "avoid_preference_habits": {"low_rating": signal(29), "unsafe_area": signal(27)},
                "avoid_nearby_places": {},
                "avoid_locations": {"crowded_center": signal(14)},
            },
        },
        "session_context": {
            "destination": "Da Nang",
            "current_location": "Ho Chi Minh City",
            "nearby_place": "Bãi Biển",
            "number_of_guests": 2,
            "has_pet": False,
            "has_children": False,
            "check_in": None,
            "check_out": None,
            "is_enough": False,
            "session_trip_types": {"Cặp đôi": signal(27)},
            "session_budget_levels": {"low": signal(26)},
            "session_price_range": {"min": 500000, "max": 1500000, "currency": "VND"},
            "session_preference_habits": {"unique": signal(24), "vibrant": signal(18), "safety": signal(22)},
            "session_hotel_types": {"Nhà dân": signal(25), "Nhà nghỉ ven đường": signal(21)},
            "session_room_views": {"Hướng Biển": signal(25)},
            "session_amenities": {"WiFi miễn phí": signal(29)},
            "session_negative_preferences": {
                "avoid_hotel_types": {},
                "avoid_amenities": {},
                "avoid_preference_habits": {"low_rating": signal(27)},
                "avoid_nearby_places": {},
                "avoid_locations": {},
            },
        },
    }

    profiles[4]["long_term_profile"].update(
        {
            "traveler_type": {"comfort_seeker": signal(26), "planner": signal(17)},
            "long_term_trip_types": {"Khách đi công tác": signal(27)},
            "long_term_budget_levels": {"high": signal(27)},
            "is_enough": True,
            "long_term_hotel_types": {"Khách sạn": signal(27), "Biệt thự nghỉ dưỡng": signal(23), "Resort": signal(14)},
            "long_term_room_views": {"Hướng Thành phố": signal(28), "Hướng Không có cửa sổ": signal(8)},
            "long_term_amenities": {
                "WiFi miễn phí": signal(29),
                "Quyền sử dụng spa miễn phí": signal(20),
                "Máy pha trà cà phê": signal(21),
                "Cách âm": signal(26),
            },
            "recommendation_clicks": {"hotel": [19105827]},
        }
    )
    profiles[4]["session_context"].update(
        {
            "session_trip_types": {"Khách đi công tác": signal(28)},
            "destination": "Ho Chi Minh City",
            "nearby_place": "Cao Ốc Văn Phòng",
            "number_of_guests": 1,
            "session_room_views": {"Hướng Thành phố": signal(28)},
            "session_amenities": {"WiFi miễn phí": signal(29), "Thiết bị phát dữ liệu di động": signal(24), "Cách âm": signal(26)},
            "session_negative_preferences": {
                "avoid_hotel_types": {"Nhà nghỉ": signal(27), "Nhà khách / Nhà nghỉ B&B": signal(18)},
                "avoid_amenities": {"Cho phép hút thuốc": signal(15)},
                "avoid_preference_habits": {"noisy": signal(29), "old_facility": signal(24), "low_rating": signal(27)},
                "avoid_nearby_places": {"Chợ": signal(14)},
                "avoid_locations": {"crowded_center": signal(20)},
            },
        }
    )

    profiles[14]["session_context"].update(
        {
            "session_trip_types": {"Gia đình có trẻ nhỏ": signal(29)},
            "destination": "Phu Quoc",
            "nearby_place": "Công Viên Giải Trí",
            "number_of_guests": 4,
            "has_children": True,
            "has_pet": False,
            "session_budget_levels": {"medium": signal(25)},
            "session_price_range": {"min": 2000000, "max": 5000000, "currency": "VND"},
            "session_preference_habits": {"comfort": signal(24), "safety": signal(27), "unique": signal(20)},
            "session_hotel_types": {"Resort": signal(26), "Khách sạn": signal(15)},
            "session_room_views": {"Hướng Bể bơi": signal(27), "Hướng Biển": signal(22)},
            "session_amenities": {
                "Bể bơi": signal(23),
                "Tiện nghi cho em bé theo yêu cầu": signal(29),
                "Máy pha trà cà phê": signal(20),
            },
        }
    )


def generate_profiles(user_count=USER_COUNT):
    profiles = []
    cold_start_indexes = {8, 19, 31, 45}
    for index in range(1, user_count + 1):
        if index <= user_count // 2:
            name = VIETNAMESE_NAMES[(index - 1) % len(VIETNAMESE_NAMES)]
            nationality = "vietnamese"
        else:
            name = FOREIGN_NAMES[(index - 1 - user_count // 2) % len(FOREIGN_NAMES)]
            nationality = "foreign"

        if index in cold_start_indexes:
            profiles.append(cold_start_profile(index, name, nationality))
        else:
            profiles.append(standard_profile(index, name, nationality))

    apply_demo_overrides(profiles)
    for profile in profiles:
        refresh_is_enough(profile)
    return profiles


def validate_signal_map(name, value, allowed_keys=None):
    if value is None:
        return
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be object or null")
    if allowed_keys is not None:
        unknown_keys = sorted(set(value) - set(allowed_keys))
        if unknown_keys:
            raise ValueError(f"{name} has unknown keys: {unknown_keys}")
    for key, item in value.items():
        if not isinstance(item, dict):
            raise TypeError(f"{name}.{key} must be an object")
        if sorted(item) != ["count", "last_interaction"]:
            raise ValueError(f"{name}.{key} must contain only count and last_interaction")

        count = item["count"]
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise TypeError(f"{name}.{key}.count must be a positive integer")

        last_interaction = item["last_interaction"]
        if not isinstance(last_interaction, str):
            raise TypeError(f"{name}.{key}.last_interaction must be a string")

        expected_last_interaction = SESSION_CURRENT_DATE.isoformat()
        if last_interaction != expected_last_interaction:
            raise ValueError(f"{name}.{key}.last_interaction must equal session current date: {expected_last_interaction}")


def validate_profile(profile):
    long_term = profile["long_term_profile"]
    session = profile["session_context"]

    if "is_enough" not in long_term:
        raise ValueError("long_term_profile.is_enough is required")
    if not isinstance(long_term["is_enough"], bool):
        raise TypeError("long_term_profile.is_enough must be boolean")
    expected_long_term_is_enough = fields_are_enough(long_term, LONG_TERM_ENOUGH_FIELDS)
    if long_term["is_enough"] != expected_long_term_is_enough:
        raise ValueError("long_term_profile.is_enough does not match LONG_TERM_ENOUGH_FIELDS")

    if "is_enough" not in session:
        raise ValueError("session_context.is_enough is required")
    if not isinstance(session["is_enough"], bool):
        raise TypeError("session_context.is_enough must be boolean")
    expected_session_is_enough = fields_are_enough(session, SESSION_ENOUGH_FIELDS)
    if session["is_enough"] != expected_session_is_enough:
        raise ValueError("session_context.is_enough does not match SESSION_ENOUGH_FIELDS")

    validate_signal_map("traveler_type", long_term["traveler_type"], TRAVELER_TYPES)
    validate_signal_map("long_term_trip_types", long_term["long_term_trip_types"], TRIP_TYPES)
    validate_signal_map("long_term_budget_levels", long_term["long_term_budget_levels"], BUDGET_LEVELS)
    validate_signal_map("long_term_preference_habits", long_term["long_term_preference_habits"], PREFERENCE_SIGNALS)
    validate_signal_map("long_term_hotel_types", long_term["long_term_hotel_types"], HOTEL_TYPES)
    validate_signal_map("long_term_room_views", long_term["long_term_room_views"], ROOM_VIEWS)
    validate_signal_map("long_term_amenities", long_term["long_term_amenities"], AMENITIES)

    validate_signal_map("session_trip_types", session["session_trip_types"], TRIP_TYPES)
    validate_signal_map("session_budget_levels", session["session_budget_levels"], BUDGET_LEVELS)
    validate_signal_map("session_preference_habits", session["session_preference_habits"], PREFERENCE_SIGNALS)
    validate_signal_map("session_hotel_types", session["session_hotel_types"], HOTEL_TYPES)
    validate_signal_map("session_room_views", session["session_room_views"], ROOM_VIEWS)
    validate_signal_map("session_amenities", session["session_amenities"], SESSION_AMENITIES)

    for container_name, container in [
        ("long_term_negative_preferences", long_term["long_term_negative_preferences"]),
        ("session_negative_preferences", session["session_negative_preferences"]),
    ]:
        for field_name, value in container.items():
            validate_signal_map(f"{container_name}.{field_name}", value)

    clicks = long_term["recommendation_clicks"]
    if clicks is not None:
        if not isinstance(clicks, dict) or not isinstance(clicks.get("hotel"), list):
            raise TypeError("recommendation_clicks must be null or contain hotel list")
        for hotel_id in clicks["hotel"]:
            if hotel_id not in HOTEL_IDS:
                raise ValueError(f"Unknown hotel id in recommendation_clicks: {hotel_id}")


def validate_profiles(profiles):
    for profile in profiles:
        validate_profile(profile)


def validate_ascii_only(path):
    raw = Path(path).read_text(encoding="utf-8")
    non_ascii = sorted(set(ch for ch in raw if ord(ch) > 127))
    if non_ascii:
        raise ValueError(f"Generated file contains non-ASCII characters: {non_ascii[:10]}")


def main():
    profiles = generate_profiles(USER_COUNT)
    validate_profiles(profiles)

    output = {
        "schema_version": "count_expiry_user_profile_mock",
        "language": "en",
        "count": len(profiles),
        "users": profiles,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    validate_ascii_only(OUTPUT_FILE)

    print(f"Created {OUTPUT_FILE.resolve()}")
    print(f"Users: {len(profiles)}")
    print("Schema alignment: passed")
    print("ASCII validation: passed")


if __name__ == "__main__":
    main()
