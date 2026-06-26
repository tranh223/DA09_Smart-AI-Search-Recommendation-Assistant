"""hotel_entity_intent_helper

Intent phụ trợ (phần tiền xử lý) để:
- Nhận query từ người dùng
- Tìm các thực thể khách sạn được nhắc tới
- Chuẩn hoá chúng dựa theo data hotel_sql_local_export.csv

Mục tiêu: mapping các tên/biến thể trong query -> hotel_id + hotel_name chuẩn trong export.

Cách dùng (trong pipeline planner/skill routing):
- load once (cache)
- extract_entities(query) -> danh sách thực thể chuẩn hoá

"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz


_STOPWORDS = {
    "cho", "toi", "muon", "tim", "kiem", "thong", "tin", "chi", "tiet", "ve",
    "khach", "san", "hotel", "resort", "tai", "la", "can", "xem",
    "dat", "phong", "nha", "nghi", "duong",
}

_LOCATION_HINTS = {
    "ha noi": {
        "positive": (
            "quan thanh", "truong dinh", "ba trieu", "doi can", "chau long",
            "bach mai", "lo duc", "phuong liet", "lac long quan",
        ),
        "negative": ("ha long", "da lat", "sapa", "sai gon", "hcm", "da nang"),
    },
}


RAG_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_EXPORT_CSV = Path(
    os.getenv(
        "HOTEL_SQL_EXPORT_CSV",
        str(PROJECT_ROOT / "data" / "hotel_sql_local_export.csv"),
    )
)
LEGACY_EXPORT_CSV = RAG_ROOT / "data" / "hotel_sql_local_export.csv"


def _normalize_text(s: str) -> str:
    """Normalize to increase matching robustness.

    - lower
    - collapse whitespace
    - strip
    """

    s = (s or "").lower().strip().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def _resolve_export_csv_path(export_csv_path: Path | str) -> Path:
    candidates = [Path(export_csv_path), DEFAULT_EXPORT_CSV, LEGACY_EXPORT_CSV]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _tokenize_for_match(s: str) -> List[str]:
    s = _normalize_text(s)
    # Keep letters/numbers/hyphen/underscore. Vietnamese diacritics are kept.
    toks = re.findall(r"[a-z0-9\-_.à-ỹ]+", s, flags=re.IGNORECASE)
    # filter very short tokens
    return [t for t in toks if len(t) >= 3]


@dataclass(frozen=True)
class HotelEntity:
    hotel_id: int
    hotel_name: str
    matched_text: str
    confidence: float


def _iter_ngrams(
    tokens: List[str], n_min: int = 1, n_max: int = 6
) -> Iterable[Tuple[str, int]]:
    """Generate n-grams from tokens.

    Returns tuples: (gram_text, n)
    """

    if not tokens:
        return

    max_n = min(n_max, len(tokens))
    for n in range(n_min, max_n + 1):
        for i in range(0, len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            yield gram, n



@lru_cache(maxsize=2)
def _load_hotel_catalog(export_csv_path: str) -> Tuple[Dict[str, List[Tuple[int, str]]], Dict[int, str]]:
    """Return:
    - key_to_candidates: normalized name -> list of (hotel_id, hotel_name)
    - id_to_name

    key is designed for exact match first.
    """

    path = _resolve_export_csv_path(export_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing export csv at: {path}")

    key_to_candidates: Dict[str, List[Tuple[int, str]]] = {}
    id_to_name: Dict[int, str] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid_raw = row.get("hotel_id")
            name = (row.get("hotel_name") or "").strip()
            if not hid_raw or not name:
                continue

            if not str(hid_raw).isdigit():
                continue

            hid = int(hid_raw)
            id_to_name[hid] = name

            key = _normalize_text(name)
            key_to_candidates.setdefault(key, []).append((hid, name))
            for alias in _name_aliases(name):
                alias_key = _normalize_text(alias)
                if alias_key and alias_key != key:
                    key_to_candidates.setdefault(alias_key, []).append((hid, name))

    return key_to_candidates, id_to_name


def _name_aliases(name: str) -> List[str]:
    aliases = [name]
    name_without_parentheses = re.sub(r"\([^)]*\)", "", name or "").strip()
    if name_without_parentheses:
        aliases.append(name_without_parentheses)
    aliases.extend(match.strip() for match in re.findall(r"\(([^)]+)\)", name or "") if match.strip())
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _important_query_tokens(query: str) -> set[str]:
    return {token for token in _tokenize_for_match(query) if token not in _STOPWORDS}


def _compact_text(value: str) -> str:
    return _normalize_text(value).replace(" ", "")


def _fuzzy_score(query: str, hotel_name: str) -> float:
    q_norm = _normalize_text(query)
    q_compact = _compact_text(query)
    q_tokens = _important_query_tokens(query)
    hotel_norm = _normalize_text(hotel_name)

    best = 0.0
    for alias in _name_aliases(hotel_name):
        alias_norm = _normalize_text(alias)
        alias_compact = _compact_text(alias)
        alias_tokens = set(_tokenize_for_match(alias_norm))
        alias_important_tokens = _important_query_tokens(alias_norm)
        coverage = len(q_tokens & alias_tokens) / len(q_tokens) if q_tokens else 0.0
        reverse_coverage = len(q_tokens & alias_tokens) / len(alias_tokens) if alias_tokens else 0.0
        score = (
            0.35 * fuzz.WRatio(q_norm, alias_norm)
            + 0.30 * fuzz.token_set_ratio(q_norm, alias_norm)
            + 0.15 * fuzz.partial_ratio(q_norm, alias_norm)
            + 15.0 * coverage
            + 5.0 * reverse_coverage
        )
        if alias_norm and re.search(r"\b" + re.escape(alias_norm) + r"\b", q_norm):
            score = max(score, 98.0)
        elif alias_compact and alias_compact in q_compact:
            score = max(score, 96.0)
        if alias_important_tokens and alias_important_tokens.issubset(q_tokens):
            score = max(score, 95.0)
        score += _location_score_adjustment(q_norm, hotel_norm)
        best = max(best, min(score, 100.0))
    return best


def _location_score_adjustment(query_norm: str, hotel_norm: str) -> float:
    adjustment = 0.0
    for location, hints in _LOCATION_HINTS.items():
        if location not in query_norm:
            continue
        if any(negative in hotel_norm for negative in hints["negative"]):
            adjustment -= 20.0
        if any(positive in hotel_norm for positive in hints["positive"]):
            adjustment += 10.0
    return adjustment


def _fuzzy_search_hotel_entities(
    query: str,
    export_csv_path: str,
    *,
    top_k: int,
    min_score: float,
) -> List[HotelEntity]:
    _, id_to_name = _load_hotel_catalog(export_csv_path)
    ranked: list[HotelEntity] = []
    for hotel_id, hotel_name in id_to_name.items():
        score = _fuzzy_score(query, hotel_name)
        if score < min_score:
            continue
        ranked.append(
            HotelEntity(
                hotel_id=hotel_id,
                hotel_name=hotel_name,
                matched_text=query,
                confidence=round(score / 100.0, 4),
            )
        )
    ranked.sort(key=lambda item: item.confidence, reverse=True)
    return ranked[:top_k]


@lru_cache(maxsize=2)
def _build_token_inverted_index(export_csv_path: str) -> Dict[str, List[Tuple[int, str]]]:
    """Inverted index from token -> candidate hotels.

    token: individual normalized token from hotel_name
    """

    key_to_candidates, _ = _load_hotel_catalog(export_csv_path)

    inv: Dict[str, List[Tuple[int, str]]] = {}
    for norm_name, cands in key_to_candidates.items():
        toks = _tokenize_for_match(norm_name)
        for t in toks:
            inv.setdefault(t, [])
            # maintain candidates; dedupe later
            inv[t].extend(cands)

    # dedupe candidate lists per token
    for t, lst in list(inv.items()):
        seen = set()
        out: List[Tuple[int, str]] = []
        for hid, nm in lst:
            if (hid, nm) in seen:
                continue
            seen.add((hid, nm))
            out.append((hid, nm))
        inv[t] = out

    return inv


def extract_hotel_entities(
    query: str,
    export_csv_path: Path = DEFAULT_EXPORT_CSV,
    max_entities: int = 10,
) -> List[HotelEntity]:
    """Extract and normalize hotel entities mentioned in query.

    Matching strategy (in order):
    1) Exact normalized hotel_name substring match.
    2) N-gram token matching against inverted index candidates.

    Confidence: rough score based on gram length.
    """

    if not query or not query.strip():
        return []

    export_str = str(export_csv_path)
    key_to_candidates, id_to_name = _load_hotel_catalog(export_str)
    inv_index = _build_token_inverted_index(export_str)

    q_norm = _normalize_text(query)

    matched: List[HotelEntity] = []
    used_ids: set[int] = set()

    # 1) Exact substring match on full normalized names
    for norm_name, candidates in key_to_candidates.items():
        if not norm_name:
            continue
        if norm_name in q_norm:
            for hid, nm in candidates:
                if hid in used_ids:
                    continue
                matched.append(
                    HotelEntity(
                        hotel_id=hid,
                        hotel_name=nm,
                        matched_text=nm,
                        confidence=0.98,
                    )
                )
                used_ids.add(hid)
                if len(matched) >= max_entities:
                    return matched

    # 2) Fuzzy rerank over all canonical CSV hotel names.
    fuzzy_matches = _fuzzy_search_hotel_entities(
        query,
        export_str,
        top_k=max_entities,
        min_score=float(os.getenv("HOTEL_ENTITY_FUZZY_MIN_SCORE", "78")),
    )
    for entity in fuzzy_matches:
        if entity.hotel_id in used_ids:
            continue
        matched.append(entity)
        used_ids.add(entity.hotel_id)
        if len(matched) >= max_entities:
            matched.sort(key=lambda x: x.confidence, reverse=True)
            return matched[:max_entities]
    if matched:
        matched.sort(key=lambda x: x.confidence, reverse=True)
        return matched[:max_entities]

    # 3) N-gram match
    q_toks = _tokenize_for_match(q_norm)
    if not q_toks:
        return matched

    for gram, n in _iter_ngrams(q_toks, n_min=2, n_max=6):
        if len(matched) >= max_entities:
            break

        gram_tokens = gram.split(" ")
        if not gram_tokens:
            continue
        gram_important_tokens = {token for token in gram_tokens if token not in _STOPWORDS}
        if len(gram_important_tokens) < 2:
            continue

        # Candidate pool = intersection-ish approximation by taking candidates from first token.
        first = gram_tokens[0]
        cand_list = inv_index.get(first, [])
        if not cand_list:
            continue

        gram_pat = re.escape(gram)
        # Accept if ngram literal appears in normalized query.
        if not re.search(r"\b" + gram_pat + r"\b", q_norm):
            continue

        # choose best among candidates by how many tokens of gram appear in hotel name tokens
        best: Optional[HotelEntity] = None
        for hid, nm in cand_list:
            if hid in used_ids:
                continue
            nm_toks = set(_tokenize_for_match(nm))
            nm_important_tokens = _important_query_tokens(nm)
            overlap = gram_important_tokens.intersection(nm_important_tokens or nm_toks)
            if not overlap:
                continue
            conf = min(0.9, 0.55 + 0.07 * len(gram_important_tokens) + 0.02 * len(overlap))
            if best is None or conf > best.confidence:
                best = HotelEntity(
                    hotel_id=hid,
                    hotel_name=nm,
                    matched_text=gram,
                    confidence=float(conf),
                )

        if best:
            matched.append(best)
            used_ids.add(best.hotel_id)

    # Stable sort by confidence desc
    matched.sort(key=lambda x: x.confidence, reverse=True)
    return matched[:max_entities]


def extract_hotel_ids(query: str, export_csv_path: Path = DEFAULT_EXPORT_CSV) -> List[int]:
    entities = extract_hotel_entities(query, export_csv_path=export_csv_path, max_entities=50)
    return [e.hotel_id for e in entities]

