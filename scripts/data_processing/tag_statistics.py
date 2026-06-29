import re
import json
import codecs
from collections import Counter

SQL_PATH = 'path/to/file_dataset.sql'

def parse_values(val_str):
    tokens = []
    i = 0
    n = len(val_str)
    
    while i < n:
        while i < n and val_str[i].isspace():
            i += 1
        if i >= n:
            break
            
        if i + 1 < n and val_str[i] == 'E' and val_str[i+1] == "'":
            i += 2
            val = []
            while i < n:
                if val_str[i] == "'":
                    backslash_count = 0
                    j = len(val) - 1
                    while j >= 0 and val[j] == '\\':
                        backslash_count += 1
                        j -= 1
                    if backslash_count % 2 == 1:
                        val.append("'")
                        i += 1
                    else:
                        i += 1
                        break
                else:
                    val.append(val_str[i])
                    i += 1
            s = "".join(val)
            s_decoded = codecs.escape_decode(bytes(s, "utf-8"))[0].decode("utf-8")
            tokens.append(s_decoded)
            if i + 1 < n and val_str[i] == ':' and val_str[i+1] == ':':
                i += 2
                while i < n and (val_str[i].isalnum() or val_str[i] in ['[', ']', '_']):
                    i += 1
            
        elif val_str[i] == "'":
            i += 1
            val = []
            while i < n:
                if val_str[i] == "'":
                    backslash_count = 0
                    j = len(val) - 1
                    while j >= 0 and val[j] == '\\':
                        backslash_count += 1
                        j -= 1
                    if backslash_count % 2 == 1:
                        val.append("'")
                        i += 1
                    else:
                        i += 1
                        break
                else:
                    val.append(val_str[i])
                    i += 1
            s = "".join(val)
            tokens.append(s)
            if i + 1 < n and val_str[i] == ':' and val_str[i+1] == ':':
                i += 2
                while i < n and (val_str[i].isalnum() or val_str[i] in ['[', ']', '_']):
                    i += 1
                
        elif i + 5 < n and val_str[i:i+6] == "ARRAY[":
            i += 6
            array_str_list = []
            while i < n and val_str[i] != ']':
                while i < n and (val_str[i].isspace() or val_str[i] == ','):
                    i += 1
                if val_str[i] == ']':
                    break
                if i + 1 < n and val_str[i] == 'E' and val_str[i+1] == "'":
                    i += 2
                    val = []
                    while i < n:
                        if val_str[i] == "'":
                            backslash_count = 0
                            j = len(val) - 1
                            while j >= 0 and val[j] == '\\':
                                backslash_count += 1
                                j -= 1
                            if backslash_count % 2 == 1:
                                val.append("'")
                                i += 1
                            else:
                                i += 1
                                break
                        else:
                            val.append(val_str[i])
                            i += 1
                    s = "".join(val)
                    s_decoded = codecs.escape_decode(bytes(s, "utf-8"))[0].decode("utf-8")
                    array_str_list.append(s_decoded)
                else:
                    if val_str[i] == ']':
                        break
                    i += 1
            if i < n and val_str[i] == ']':
                i += 1
            if i + 1 < n and val_str[i] == ':' and val_str[i+1] == ':':
                i += 2
                while i < n and (val_str[i].isalnum() or val_str[i] in ['[', ']', '_']):
                    i += 1
            tokens.append(array_str_list)
            
        else:
            start = i
            while i < n and val_str[i] != ',':
                i += 1
            tok = val_str[start:i].strip()
            if tok == 'NULL':
                tokens.append(None)
            elif tok == 'TRUE':
                tokens.append(True)
            elif tok == 'FALSE':
                tokens.append(False)
            else:
                try:
                    tokens.append(int(tok))
                except ValueError:
                    try:
                        tokens.append(float(tok))
                    except ValueError:
                        tokens.append(tok)
                        
        while i < n and val_str[i].isspace():
            i += 1
        if i < n and val_str[i] == ',':
            i += 1
            
    return tokens

def main():
    print("Reading SQL file...")
    with open(SQL_PATH, 'r') as f:
        lines = f.readlines()
        
    hotels = []
    rooms = []
    nearby_places = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("INSERT INTO hotels "):
            m = re.search(r"VALUES \((.*)\);", line)
            if m:
                vals = parse_values(m.group(1))
                hotels.append({
                    'hotel_id': vals[0],
                    'name': vals[1],
                    'accommodation_type': vals[2] if len(vals) > 2 else None,
                    'amenities': vals[12] if len(vals) > 12 else [],
                    'suitable_for': vals[15] if len(vals) > 15 else [],
                    'reviews_detail': vals[16] if len(vals) > 16 else None
                })
        elif line.startswith("INSERT INTO rooms "):
            m = re.search(r"VALUES \((.*)\);", line)
            if m:
                vals = parse_values(m.group(1))
                rooms.append({
                    'room_view': vals[7] if vals[7] else "",
                    'room_amenities': vals[8] if len(vals) > 8 else []
                })
        elif line.startswith("INSERT INTO nearby_places "):
            m = re.search(r"VALUES \((.*)\);", line)
            if m:
                vals = parse_values(m.group(1))
                nearby_places.append({
                    'name': vals[1],
                    'type': vals[2]
                })

    num_hotels = len(hotels)
    num_rooms = len(rooms)
    num_places = len(nearby_places)
    print(f"Loaded: {num_hotels} hotels, {num_rooms} rooms, {num_places} nearby places.")

    # 1. suitable_for
    suitable_counter = Counter()
    for h in hotels:
        suitable_list = h['suitable_for'] or []
        for s in suitable_list:
            suitable_counter[s] += 1
    print("\n--- 2. suitable_for (Đối tượng phù hợp) ---")
    print(f"Total Unique: {len(suitable_counter)}")
    for idx, (k, v) in enumerate(suitable_counter.most_common(), 1):
        pct = (v / num_hotels) * 100
        print(f"{idx}. {k}: {v} hotels ({pct:.2f}%)")

    # 2. amenities
    amenities_counter = Counter()
    for h in hotels:
        amenities_list = h['amenities'] or []
        for a in amenities_list:
            amenities_counter[a] += 1
    print("\n--- 3. amenities (Tiện ích khách sạn - Top 30) ---")
    print(f"Total Unique: {len(amenities_counter)}")
    for idx, (k, v) in enumerate(amenities_counter.most_common(30), 1):
        pct = (v / num_hotels) * 100
        print(f"{idx}. {k}: {v} hotels ({pct:.2f}%)")

    # 3. room_view
    view_groups = {
        "Hướng Thành phố": ["Hướng Thành phố", "Hướng Đường phố", "Hướng Cảnh đêm"],
        "Hướng Biển": ["Hướng Biển", "Hướng Đại dương", "Hướng Bãi biển", "Hướng Vịnh", "Hướng Cảng", "Hướng Đầm phá", "Hướng biển (một phần)", "Hướng Đại dương (một phần)", "Hướng Vịnh biển", "Hướng Bến du thuyền"],
        "Hướng Thiên nhiên": ["Hướng Vườn", "Hướng Sân trong", "Hướng Công viên", "Hướng Thiên nhiên", "Hướng Nông thôn"],
        "Hướng Ngoài trời": ["Hướng Ngoài trời"],
        "Hướng Núi": ["Hướng Núi", "Hướng Thắng cảnh", "Hướng Thung lũng"],
        "Hướng Sông": ["Hướng Sông"],
        "Hướng Bể bơi": ["Hướng Bể bơi"],
        "Hướng Hồ": ["Hướng Hồ", "Hướng Hồ (một phần)"],
        "Không có cửa sổ": ["Không có cửa sổ"]
    }
    
    view_group_counter = Counter()
    for r in rooms:
        raw_view = r['room_view']
        if not raw_view or raw_view == "NULL":
            view_group_counter["không có thông tin"] += 1
            continue
        
        matched = False
        for g_name, patterns in view_groups.items():
            if raw_view in patterns:
                view_group_counter[g_name] += 1
                matched = True
                break
        if not matched:
            view_group_counter[raw_view] += 1

    print("\n--- 4. room_view (Cảnh quan phòng) ---")
    print(f"Total Unique Categories: {len(view_group_counter)}")
    for idx, (k, v) in enumerate(view_group_counter.most_common(), 1):
        pct = (v / num_rooms) * 100
        print(f"{idx}. {k}: {v} rooms ({pct:.2f}%)")

    # 4. room_amenities
    room_amenities_counter = Counter()
    for r in rooms:
        amenities_list = r['room_amenities'] or []
        for ra in amenities_list:
            room_amenities_counter[ra] += 1
    print("\n--- 5. room_amenities (Tiện ích phòng - Top 30) ---")
    print(f"Total Unique: {len(room_amenities_counter)}")
    for idx, (k, v) in enumerate(room_amenities_counter.most_common(30), 1):
        pct = (v / num_rooms) * 100
        print(f"{idx}. {k}: {v} rooms ({pct:.2f}%)")

    # 5. reviews_detail/tags
    review_tags_counter = Counter()
    for h in hotels:
        rd_str = h['reviews_detail']
        if not rd_str:
            continue
        try:
            rd = json.loads(rd_str)
        except Exception:
            continue
        if rd and 'tags' in rd:
            for t in rd['tags']:
                tag_name = t.get('tag', '')
                mentioned = t.get('mentioned', 0)
                if tag_name and mentioned > 4:
                    review_tags_counter[tag_name] += 1
    print("\n--- 6. reviews_detail/tags (Nhãn đánh giá mentioned > 4 - Top 30) ---")
    print(f"Total Unique: {len(review_tags_counter)}")
    for idx, (k, v) in enumerate(review_tags_counter.most_common(30), 1):
        pct = (v / num_hotels) * 100
        print(f"{idx}. {k}: {v} hotels ({pct:.2f}%)")

    # 6. PLACE_TYPE
    places_counter = Counter()
    for p in nearby_places:
        places_counter[p['type']] += 1
    print("\n--- 7. PLACE_TYPE (Loại địa điểm lân cận - Top 30) ---")
    print(f"Total Unique: {len(places_counter)}")
    for idx, (k, v) in enumerate(places_counter.most_common(30), 1):
        pct = (v / num_places) * 100
        print(f"{idx}. {k}: {v} places ({pct:.2f}%)")

    # 7. HOTEL_TYPE (Loại hình lưu trú)
    hotel_type_counter = Counter()
    # Ánh xạ chuẩn hóa từ dữ liệu thô sang 11 nhóm loại hình trong tag_statistics.md
    type_mapping = {
        "Giường và Bữa sáng": "Khách sạn",
        "Nhà dân": "Homestay",
        "Biệt thự nghỉ dưỡng": "Biệt thự",
        "Nhà khách / Nhà nghỉ B&B": "Nhà khách/Nhà nghỉ B&B",
        "Nhà khách/Nhà nghỉ B&B": "Nhà khách/Nhà nghỉ B&B"
    }
    for h in hotels:
        htype = h['accommodation_type']
        if htype:
            cleaned_type = type_mapping.get(htype, htype)
            hotel_type_counter[cleaned_type] += 1
            
    print("\n--- 8. HOTEL_TYPE (Loại hình lưu trú) ---")
    print(f"Total Unique: {len(hotel_type_counter)}")
    for idx, (k, v) in enumerate(hotel_type_counter.most_common(), 1):
        pct = (v / num_hotels) * 100
        print(f"{idx}. {k}: {v} hotels ({pct:.2f}%)")

if __name__ == "__main__":
    main()
