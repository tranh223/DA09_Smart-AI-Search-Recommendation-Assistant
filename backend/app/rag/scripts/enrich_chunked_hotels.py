import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


INPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "chunked_hotels.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "chunked_hotels_enriched.json"


def _safe_list(x):
    return x if isinstance(x, list) else []


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _extract_times_from_policy(content: str) -> Dict[str, Optional[str]]:
    # Try multiple patterns (Vietnamese)
    c = content or ""
    res = {
        "check_in": None,
        "check_out": None,
    }

    # Check-in
    m = re.search(r"Check[-\s]?in\s*[:：]?\s*([0-9]{1,2}(?::[0-9]{2})?)\s*(AM|PM|am|pm)?", c, re.IGNORECASE)
    if m:
        res["check_in"] = (m.group(1) + (" " + (m.group(2) or "")).strip()).strip()

    # Check-out
    m = re.search(r"Check[-\s]?out\s*[:：]?\s*([0-9]{1,2}(?::[0-9]{2})?)\s*(AM|PM|am|pm)?", c, re.IGNORECASE)
    if m:
        res["check_out"] = (m.group(1) + (" " + (m.group(2) or "")).strip()).strip()

    # Additional Vietnamese labels
    m = re.search(r"Nhận\s*phòng\s*[:：]?\s*([0-9]{1,2}(?::[0-9]{2})?)", c, re.IGNORECASE)
    if m and not res["check_in"]:
        res["check_in"] = m.group(1)

    m = re.search(r"Trả\s*phòng\s*[:：]?\s*([0-9]{1,2}(?::[0-9]{2})?)", c, re.IGNORECASE)
    if m and not res["check_out"]:
        res["check_out"] = m.group(1)

    return res


def _detect_pet_policy(content: str) -> Dict[str, Any]:
    c = content or ""
    lower = c.lower()
    # Common patterns
    if "không được phép" in lower and "thú nuôi" in lower:
        return {"allowed": False, "summary": "Không được phép mang thú nuôi"}
    if re.search(r"pet\s*policy\s*[:：]?\s*[^\n]*(not|no|không)", lower):
        return {"allowed": False, "summary": "Pet policy không"}
    if "cho phép" in lower and "thú nuôi" in lower:
        return {"allowed": True, "summary": "Có cho phép thú nuôi"}
    if "pet policy" in lower:
        return {"allowed": None, "summary": "Có thông tin pet policy (chưa chuẩn hoá)"}
    return {"allowed": None, "summary": None}


def _detect_deposit_required(content: str) -> Dict[str, Any]:
    c = content or ""
    lower = c.lower()
    m = re.search(r"deposit\s*required\s*[:：]?\s*([^\n]+)", lower)
    if m:
        v = m.group(1).strip()
        if "no" in v:
            return {"required": False, "summary": "Deposit Required: No"}
        if "yes" in v or re.search(r"\d", v):
            return {"required": True, "summary": "Deposit Required: Yes/amount"}
    if "tiền đặt cọc" in lower:
        if "không" in lower:
            return {"required": False, "summary": "Tiền đặt cọc: không"}
        return {"required": True, "summary": "Tiền đặt cọc: có"}
    return {"required": None, "summary": None}


def _extract_child_policy_ranges(content: str) -> List[Dict[str, Any]]:
    c = content or ""
    items: List[Dict[str, Any]] = []
    # Example: "Trẻ em 6-11 tuổi ..." or "Children 3-5 years". We'll only parse simple numeric ranges.

    # Vietnamese range patterns
    for m in re.finditer(
        r"Trẻ\s*em\s*(\d{1,2})\s*[\-–]\s*(\d{1,2})\s*tuổi[^\n]*?(miễn\s*phí|ở\s*miễn\s*phí|miễn\s*phí|phải\s*thu|thu\s*phí|ở\s*phải\s*phí|có\s*thể\s*tính\s*phụ\s*thu)?",
        c,
        flags=re.IGNORECASE,
    ):
        lo, hi, act = m.group(1), m.group(2), (m.group(3) or "").strip().lower()
        items.append({
            "age_range": f"{lo}-{hi}",
            "rule": (act if act else None),
            "raw": _norm_text(m.group(0)),
        })

    # English range patterns (best-effort)
    for m in re.finditer(r"Children\s*(\d{1,2})\s*[\-–]\s*(\d{1,2})\s*(years|yrs)[^\n]*? (free|no charge|charged|pay)", c, flags=re.IGNORECASE):
        lo, hi = m.group(1), m.group(2)
        items.append({
            "age_range": f"{lo}-{hi}",
            "rule": m.group(0),
            "raw": _norm_text(m.group(0)),
        })

    # Deduplicate by raw
    seen = set()
    uniq = []
    for it in items:
        key = it.get("raw")
        if key and key not in seen:
            seen.add(key)
            uniq.append(it)
    return uniq


def _extract_activity_names(content: str) -> List[str]:
    c = content or ""
    names = []

    # Activity:\n ... or "Activity:" lines
    for m in re.finditer(r"Activity\s*[:：]\s*(.+?)(?:\n\n|\nDescription\s*[:：]|\n\w+\s*[:：]|$)", c, flags=re.IGNORECASE | re.DOTALL):
        name = _norm_text(m.group(1))
        if name:
            names.append(name)

    # Fallback: lines starting with "Activity:" repeated
    if not names:
        for line in c.splitlines():
            if line.strip().lower().startswith("activity") and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    n = _norm_text(parts[1])
                    if n:
                        names.append(n)

    # Deduplicate preserving order
    out = []
    seen = set()
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _tag_by_keywords(content: str, section: str) -> List[str]:
    c = (content or "")
    lower = c.lower()
    tags = set()

    # Generic by section
    if section == "policy":
        tags.update(["policy", "checkin_checkout"])
    if section == "activities":
        tags.add("activities")
        tags.add("tours_excursions")
    if section == "description":
        tags.add("hotel_description")

    # Amenities
    kw_map = [
        ("pool", ["hồ bơi", "hồ bơi", "pool", "bể bơi"]),
        ("spa", ["spa", "massage", "sauna", "steamroom", "phòng xông hơi", "xông hơi"]),
        ("fitness", ["trung tâm thể dục", "phòng tập", "gym", "fitness", "yoga", "bài tập"]),
        ("restaurant_food", ["nhà hàng", "quán cà phê", "cafe", "buffet", "ẩm thực", "bbq", "bữa sáng"]),
        ("transport", ["đưa đón", "airport transfer", "taxi", "thuê xe", "limousine", "xe buýt"]),
        ("parking", ["bãi đỗ xe", "parking", "valet"]),
        ("room_amenities", ["mini bar", "tủ lạnh", "tv", "truyền hình", "wi-fi", "wifi", "máy sấy tóc", "áo choàng", "ban công", "lò sưởi"]),
        ("pets", ["thú nuôi", "pet policy"]),
        ("checkin_checkout", ["check-in", "check-out", "nhận phòng", "trả phòng"]),
        ("kids_family", ["trẻ em", "trẻ sơ sinh", "cũi", "nôi", "family", "kids"]),
    ]

    for tag, kws in kw_map:
        for kw in kws:
            if kw in lower:
                tags.add(tag)
                break

    return sorted(tags)


def enrich_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
    content = chunk.get("content") or ""
    section = chunk.get("section") or ""

    metadata = chunk.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    enriched: Dict[str, Any] = {}

    # Tags
    enriched["tags"] = _tag_by_keywords(content, section)

    # Section-specific
    if section == "policy":
        times = _extract_times_from_policy(content)
        enriched["times"] = times
        enriched["child_policy"] = _extract_child_policy_ranges(content)
        enriched["pet_policy"] = _detect_pet_policy(content)
        enriched["deposit_required"] = _detect_deposit_required(content)

    if section == "activities":
        enriched["activity_names"] = _extract_activity_names(content)

    if section == "description":
        # Add a compact summary line (first 300 chars)
        enriched["summary"] = _norm_text(content)[:300]

    # Keep existing metadata and add tags directly (không dùng field enriched)
    metadata_out = dict(metadata)

    # Optional: keep section-specific structured fields under tags metadata only
    metadata_out["tags"] = enriched.get("tags", [])

    # mutate chunk copy
    chunk_out = dict(chunk)
    chunk_out["metadata"] = metadata_out
    return chunk_out


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("chunked_hotels.json must be a JSON array")

    enriched_all = []
    for i, chunk in enumerate(raw):
        enriched_all.append(enrich_chunk(chunk))
        if (i + 1) % 5000 == 0:
            print(f"Enriched {i+1}/{len(raw)}...")

    OUTPUT_PATH.write_text(json.dumps(enriched_all, ensure_ascii=False, indent=2), encoding="utf-8")

    # sanity sample
    print(f"Wrote: {OUTPUT_PATH}")
    print("Sample enriched metadata:")
    for sample_idx in [0, min(1, len(enriched_all)-1), min(10, len(enriched_all)-1)]:
        c = enriched_all[sample_idx]
        print({
            "chunk_id": c.get("chunk_id"),
            "section": c.get("section"),
            "enriched_keys": list((c.get("metadata") or {}).get("enriched", {}).keys()),
            "tags": (c.get("metadata") or {}).get("enriched", {}).get("tags"),
        })


if __name__ == "__main__":
    main()

