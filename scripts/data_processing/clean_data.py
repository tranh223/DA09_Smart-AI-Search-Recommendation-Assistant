import sys
import os
import csv
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def decode_postgres_escapes(s):
    s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\U([0-9a-fA-F]{8})', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)
    replacements = {
        '\\n': '\n',
        '\\r': '\r',
        '\\t': '\t',
        "\\'": "'",
        '\\\\': '\\'
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s

def extract_values_fields(line):
    idx = line.find("VALUES (")
    if idx == -1:
        idx = line.find("values (")
        if idx == -1:
            return None
            
    val_str = line[idx + 8:]
    
    values = []
    current = []
    in_string = False
    escape = False
    bracket_depth = 0
    paren_depth = 0
    
    i = 0
    n = len(val_str)
    while i < n:
        c = val_str[i]
        
        if escape:
            current.append(c)
            escape = False
            i += 1
            continue
            
        if in_string:
            if c == '\\':
                escape = True
                current.append(c)
            elif c == "'":
                in_string = False
                current.append(c)
            else:
                current.append(c)
            i += 1
            continue
            
        if c == "'":
            in_string = True
            current.append(c)
            i += 1
            continue
            
        if c == '[':
            bracket_depth += 1
            current.append(c)
            i += 1
            continue
            
        if c == ']':
            bracket_depth -= 1
            current.append(c)
            i += 1
            continue
            
        if c == '(':
            paren_depth += 1
            current.append(c)
            i += 1
            continue
            
        if c == ')':
            if paren_depth == 0 and bracket_depth == 0:
                values.append("".join(current).strip())
                break
            paren_depth -= 1
            current.append(c)
            i += 1
            continue
            
        if c == ',' and bracket_depth == 0 and paren_depth == 0:
            values.append("".join(current).strip())
            current = []
            i += 1
            continue
            
        current.append(c)
        i += 1
        
    return values

def parse_postgres_string(val_str):
    val_str = val_str.strip()
    if val_str.upper() == "NULL":
        return None
    is_escaped = False
    if val_str.startswith("E'"):
        is_escaped = True
        val_str = val_str[2:-1]
    elif val_str.startswith("'"):
        val_str = val_str[1:-1]
        
    if is_escaped:
        val_str = decode_postgres_escapes(val_str)
    return val_str.strip()

def clean_room_view(view):
    if not view:
        return None
    view_lower = view.lower().strip()
    
    # Mapping dictionary for similar room view tags
    mapping = {
        # Sea / Ocean views -> Hướng Biển
        "hướng đại dương": "Hướng Biển",
        "hướng bãi biển": "Hướng Biển",
        "hướng biển (hướng một phần)": "Hướng Biển",
        "hướng đại dương (một phần)": "Hướng Biển",
        "hướng vịnh": "Hướng Biển",
        "hướng vịnh biển": "Hướng Biển",
        "hướng cảng": "Hướng Biển",
        "hướng bến du thuyền": "Hướng Biển",
        "hướng đầm phá": "Hướng Biển",
        
        # Street/City views -> Hướng Thành phố
        "hướng đường phố": "Hướng Thành phố",
        "hướng cảnh đêm": "Hướng Thành phố",
        
        # Lake views -> Hướng Hồ
        "hướng hồ (một phần)": "Hướng Hồ",
        
        # Garden / Park / Courtyard views -> Hướng Thiên nhiên
        "hướng vườn": "Hướng Thiên nhiên",
        "hướng công viên": "Hướng Thiên nhiên",
        "hướng sân trong": "Hướng Thiên nhiên",
        "hướng thiên nhiên": "Hướng Thiên nhiên",
        "hướng nông thôn": "Hướng Thiên nhiên",
        
        # Mountain / Valley views -> Hướng Núi
        "hướng thắng cảnh": "Hướng Núi",
        "hướng thung lũng": "Hướng Núi",
        
        # Windowless -> Không có cửa sổ
        "hướng không có cửa sổ": "Không có cửa sổ",
        "không có cửa sổ": "Không có cửa sổ"
    }
    
    if view_lower in mapping:
        return mapping[view_lower]
    
    # Capitalize the first letter for consistency
    return view[0].upper() + view[1:] if len(view) > 1 else view.upper()

def parse_postgres_array(s, start_idx):
    idx = start_idx
    if not s[idx:].startswith("ARRAY["):
        return None, start_idx
        
    idx += len("ARRAY[")
    elements = []
    
    while idx < len(s):
        # Skip spaces/commas
        while idx < len(s) and s[idx] in " \t,":
            idx += 1
            
        if idx >= len(s):
            break
            
        if s[idx] == ']':
            idx += 1
            if s[idx:].startswith("::text[]"):
                idx += len("::text[]")
            return elements, idx
            
        # Parse a string literal
        if s[idx] == 'E':
            idx += 1
            
        if idx < len(s) and s[idx] == "'":
            idx += 1 # Consume open quote
            val_chars = []
            while idx < len(s):
                if s[idx] == "\\":
                    if idx + 1 < len(s):
                        val_chars.append(s[idx+1])
                        idx += 2
                    else:
                        val_chars.append("\\")
                        idx += 1
                elif s[idx] == "'":
                    if idx + 1 < len(s) and s[idx+1] == "'":
                        val_chars.append("'")
                        idx += 2
                    else:
                        idx += 1
                        break
                else:
                    val_chars.append(s[idx])
                    idx += 1
            elements.append("".join(val_chars))
        elif s[idx:].startswith("NULL"):
            elements.append(None)
            idx += 4
        else:
            temp = []
            while idx < len(s) and s[idx] not in ",]":
                temp.append(s[idx])
                idx += 1
            val = "".join(temp).strip()
            elements.append(val)
            
    return None, start_idx

def format_postgres_array(elements):
    if not elements:
        return "ARRAY[]::text[]"
    
    parts = []
    for el in elements:
        if el is None:
            parts.append("NULL")
        else:
            escaped = el.replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"E'{escaped}'")
            
    return f"ARRAY[{', '.join(parts)}]::text[]"

def load_allowed_amenities(csv_path):
    allowed = {}
    if not os.path.exists(csv_path):
        print(f"Warning: Allowed amenities CSV not found at {csv_path}. Skipping final filtering.")
        return None
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            next(reader) # skip header
        except StopIteration:
            pass
        for row in reader:
            if row:
                tag = row[0].strip()
                allowed[tag.lower()] = tag
    return allowed

def clean_amenities(elements, allowed_amenities=None):
    cleaned = []
    seen = set()
    
    # Precise list of Covid safety, hygiene, and trivial tags to exclude
    tags_to_remove = {
        # Nhóm 2: Quy định dịch tễ phòng chống dịch
        "nhân viên được đào tạo về giao thức an toàn",
        "phòng được vệ sinh giữa các lần ở",
        "có thể yêu cầu không khử trùng phòng",
        "giãn cách vật lý ít nhất 1 mét",
        "khử trùng hằng ngày",
        "khẩu trang miễn phí",
        "kiểm tra nhiệt độ cho khách và nhân viên",
        "nhiệt kế cơ thể",
        "băng niêm phong phòng dành cho khách sau khi vệ sinh",
        "dịch vụ khử trùng chuyên nghiệp",
        "chứng nhận vệ sinh",
        "nhân viên đeo khẩu trang",
        "thiết bị tiệt trùng",
        "sản phẩm vệ sinh",
        "các quy định giãn cách vật lý được chấp hành",
        "được khử trùng theo nguyên tắc về y tế hoặc của agoda",
        "sản phẩm làm sạch chống virus",
        "sản phẩm làm sạch được sử dụng dựa trên hướng dẫn về y tế",
        "khẩu trang được cung cấp cho khách",
        "vật dụng làm vệ sinh được cung cấp cho khách",
        "nước rửa tay và xà phòng được cung cấp",
        "giặt đồ vải lanh và quần áo bằng nước nóng",
        "được làm sạch bởi công ty làm sạch chuyên nghiệp",
        "được làm sạch theo hướng dẫn về y tế hoặc của agoda",
        "dịch vụ thanh toán không sử dụng tiền mặt",
        "nhận trả phòng không tiếp xúc",
        "nhận/trả phòng không tiếp xúc",
        "lựa chọn thức ăn bọc riêng",
        "sắp xếp bữa ăn thay thế",
        "dịch vụ bán thức ăn sáng mang về",
        "giao đồ ăn",
        "màn bảo vệ ở khu vực chung",
        
        # Nhóm 3: Tiện ích vụn vặt / Lỗi dịch thuật
        "vật dụng nhà bếp và bộ đồ ăn được vệ sinh",
        "không có văn phòng phẩm dùng chung",
        "nhận trả phòng trả phòng không tiếp xúc",
        "nhận/trả phòng trả phòng không tiếp xúc",
        "cách bày bàn ăn an toàn",
    }
    
    for el in elements:
        if el is None:
            cleaned.append(None)
            continue
            
        el_strip = el.strip()
        el_lower = el_strip.lower()
        
        # 1. Removal Check
        if el_lower in tags_to_remove:
            continue
            
        # 2. Merging Rules
        # WiFi
        if el_lower in ["wifi miễn phí", "wifi", "wifi có dây", "wifi mạng lan trong phòng miễn phí"]:
            val = "WiFi miễn phí"
        # Sauna
        elif el_lower in ["xông khô", "phòng xông khô"]:
            val = "Xông khô"
        # Balcony
        elif el_lower in ["ban công sân hiên", "ban công hoặc sân hiên"]:
            val = "Ban công sân hiên"
        # Kitchen
        elif el_lower in ["bếp", "bếp chung", "bếp nhỏ", "bếp đầy đủ"]:
            val = "Bếp"
        # Pets
        elif el_lower in ["được phép đưa thú nuôi vào", "được phép đưa thú cưng vào phòng", "cho phép đưa thú cưng vào miễn phí"]:
            val = "Được phép đưa thú nuôi vào"
        # Bathroom
        elif el_lower in ["nhà tắm chung", "phòng tắm chung"]:
            val = "Nhà tắm chung"
        # Pools
        elif el_lower in ["bể bơi riêng", "bể bơi"]:
            val = "Bể bơi"
        # Elevators
        elif el_lower in ["đi lên bằng thang máy", "thang máy"]:
            val = "Thang máy"
        # Group 4
        elif el_lower in ["bữa sáng tự chọn", "bữa sáng gọi món", "bữa sáng"]:
            val = "Bữa sáng tự chọn"
        # Group 7
        elif el_lower in ["truyền hình cáp vệ tinh", "truyền hình cáp"]:
            val = "Truyền hình cáp vệ tinh"
        # Group 11
        elif el_lower in ["tủ lạnh", "tủ đông"]:
            val = "Tủ lạnh"
        # Group 12
        elif el_lower in ["sân gôn", "sân gôn nhỏ"]:
            val = "Sân gôn"
        # Group 13
        elif el_lower in ["tiện nghi nấu nướng ngoài trời", "tiện nghi nấu nướng ngoài trời riêng"]:
            val = "Tiện nghi nấu nướng ngoài trời"
        # Group 17
        elif el_lower in ["bãi biển riêng", "lối vào bãi biển riêng"]:
            val = "Bãi biển riêng"
        # Group 20
        elif el_lower in ["sân quần vợt", "sân bóng quần"]:
            val = "Sân quần vợt"
        # Group 25
        elif el_lower in ["lò sưởi", "lò sưởi trong nhà"]:
            val = "Lò sưởi"
        # Group 26
        elif el_lower in ["lối vào hồ bơi", "lối vào hồ"]:
            val = "Lối vào hồ bơi"
        # Group 29
        elif el_lower in ["tắm suối nước nóng", "vào suối nước nóng"]:
            val = "Tắm suối nước nóng"
        # Group 30
        elif el_lower in ["phòng tắm có băng ghế tắm", "ghế tắm", "ghế ngồi bồn tắm"]:
            val = "Phòng tắm có băng ghế tắm"
        # Group 31
        elif el_lower in ["cửa sổ có thể mở ra", "cửa sổ mở"]:
            val = "Cửa sổ có thể mở ra"
            
        # 3. Location / Distance Replacements
        elif el_lower.startswith("tọa lạc tại trung tâm"):
            val = "Tọa lạc tại trung tâm thành phố"
        elif el_lower.startswith("cách phương tiện công cộng"):
            val = "gần phương tiện công cộng"
        elif el_lower.startswith("cách bãi biển"):
            val = "gần bãi biển"
        else:
            val = el_strip
            
        # 4. Filter against allowed amenities (LLM/Heuristics filtered list)
        if allowed_amenities is not None:
            val_lower = val.lower()
            if val_lower in allowed_amenities:
                val = allowed_amenities[val_lower]
            else:
                continue # Discard this amenity as it is not in the allowed list
            
        val_lower = val.lower()
        if val_lower not in seen:
            seen.add(val_lower)
            cleaned.append(val)
            
    return cleaned

def main():
    input_path = os.path.join(BASE_DIR, "data", "insert_data.sql")
    output_path = os.path.join(BASE_DIR, "data", "clean_data_ver_1.sql")
    
    total_lines = 0
    modified_lines = 0
    
    print("Starting data cleaning process...")
    
    # Load allowed amenities list for final filtering
    allowed_csv = os.path.join(BASE_DIR, "data", "amenities_statistics_llm_filtered.csv")
    allowed_amenities = load_allowed_amenities(allowed_csv)
    if allowed_amenities:
        print(f"Loaded {len(allowed_amenities)} allowed amenities for final filtering.")
        
    with open(input_path, mode="r", encoding="utf-8") as f_in, \
         open(output_path, mode="w", encoding="utf-8") as f_out:
         
        for line in f_in:
            total_lines += 1
            if total_lines % 2000 == 0:
                print(f"Processed {total_lines} lines...")
                
            # We only modify INSERT INTO statements
            if not line.startswith("INSERT INTO"):
                f_out.write(line)
                continue
                
            # Special logic for rooms table
            if line.startswith("INSERT INTO rooms "):
                fields = extract_values_fields(line)
                if fields and len(fields) >= 11:
                    room_view_raw = fields[7]
                    room_view = parse_postgres_string(room_view_raw)
                    room_view_changed = False
                    new_room_view = clean_room_view(room_view)
                    if new_room_view != room_view:
                        room_view_changed = True
                        if new_room_view is None:
                            fields[7] = "NULL"
                        else:
                            escaped = new_room_view.replace("\\", "\\\\").replace("'", "\\'")
                            fields[7] = f"E'{escaped}'"
                            
                    # Clean room amenities (fields[8])
                    room_amenities_raw = fields[8]
                    elements, _ = parse_postgres_array(room_amenities_raw, 0)
                    room_amenities_changed = False
                    if elements is not None:
                        cleaned = clean_amenities(elements, allowed_amenities)
                        formatted = format_postgres_array(cleaned)
                        if formatted != room_amenities_raw:
                            fields[8] = formatted
                            room_amenities_changed = True
                            
                    if room_view_changed or room_amenities_changed:
                        modified_lines += 1
                        val_idx = line.find("VALUES (")
                        if val_idx == -1:
                            val_idx = line.find("values (")
                        prefix = line[:val_idx + 8]
                        new_line = prefix + ", ".join(fields) + ");\n"
                        f_out.write(new_line)
                    else:
                        f_out.write(line)
                else:
                    f_out.write(line)
                continue
                
            # Original logic for hotels and other tables
            idx = 0
            new_parts = []
            last_end = 0
            has_changes = False
            
            while True:
                pos = line.find("ARRAY[", idx)
                if pos == -1:
                    new_parts.append(line[last_end:])
                    break
                    
                new_parts.append(line[last_end:pos])
                elements, end_idx = parse_postgres_array(line, pos)
                
                if elements is not None:
                    # Classify if this is the amenities array
                    is_images = any(el and el.startswith("http") for el in elements)
                    is_suitable = any(el in ['Khách đi công tác', 'Cặp đôi', 'Khách du lịch một mình', 'Gia đình có trẻ nhỏ', 'Gia đình có thanh thiếu niên', 'Nhóm du khách'] for el in elements)
                    is_policy = any(el and (len(el) > 100 or '\n' in el or 'Vingroup' in el or 'Giường phụ' in el) for el in elements)
                    
                    if not is_images and not is_suitable and not is_policy:
                        cleaned = clean_amenities(elements, allowed_amenities)
                        formatted = format_postgres_array(cleaned)
                        new_parts.append(formatted)
                        has_changes = True
                    else:
                        new_parts.append(line[pos:end_idx])
                    idx = end_idx
                    last_end = end_idx
                else:
                    new_parts.append("ARRAY[")
                    idx = pos + len("ARRAY[")
                    last_end = idx
                    
            if has_changes:
                modified_lines += 1
                f_out.write("".join(new_parts))
            else:
                f_out.write(line)
                
    print("\nCleaning completed successfully!")
    print(f"Total lines processed: {total_lines}")
    print(f"Total lines modified (with cleaned attributes): {modified_lines}")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()
