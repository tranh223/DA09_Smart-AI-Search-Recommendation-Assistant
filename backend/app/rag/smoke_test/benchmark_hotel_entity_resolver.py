#!/usr/bin/env python3
"""Smoke-test benchmark for `hotel_entity_resolver`.

Goals (per request):
1) Do NOT use the correct ground-truth hotel name directly.
   Instead, we perturb the name slightly to simulate user input noise.
2) Move benchmarking into smoke_test folder and write results into
   `backend/app/rag/smoke_test/results/`.

What it does:
- Load examples from backend/app/rag/data/hotels_rows.csv
- For each example:
  - Create a perturbed input name
  - Call resolver.resolve(perturbed_name, candidates=[], city=ex.city)
  - Track latency + basic match stats
- Write a JSON result file.

Env vars:
- BENCH_N (default 30)
- BENCH_SEED (default 42)
- BENCH_OUTPUT_JSON (default benchmark_hotel_entity_resolver_results.json)
- BENCH_PERTURB_MODE (default "typo")

Perturb modes:
- typo: swap/replace a character, truncate, or remove a token
- swap_word: swap first two tokens if multiple tokens exist
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure `backend/` is on sys.path so imports like `app.xxx` work when running
backend_root = Path(__file__).resolve().parents[3]  # .../backend
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.rag.tools.hotel_entity_resolver import HotelCandidate, hotel_entity_resolver


ROOT = Path(__file__).resolve().parents[1]  # backend/app/rag/smoke_test
CSV_PATH = ROOT / "data" / "hotels_rows.csv"
RESULTS_DIR = ROOT / "smoke_test" / "results"


@dataclass
class Example:
    hotel_id: int
    hotel_name: str
    city: str | None


def _require_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v:
        return v
    if default is not None:
        return default
    raise RuntimeError(f"Missing env var: {name}")


def load_examples(n: int) -> list[Example]:
    if not CSV_PATH.exists():
        raise RuntimeError(f"Missing CSV: {CSV_PATH}")

    examples: list[Example] = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = row.get("id")
            name = row.get("name")
            city = row.get("city")
            if not hid or not name:
                continue
            try:
                hid_i = int(hid)
            except Exception:
                continue
            examples.append(Example(hotel_id=hid_i, hotel_name=name, city=city or None))

    if not examples:
        raise RuntimeError("No examples loaded from CSV")

    random.seed(int(os.getenv("BENCH_SEED", "42")))
    if n >= len(examples):
        return examples
    return random.sample(examples, n)


def perturb_name(name: str, mode: str) -> str:
    """Create a noisy version of the hotel name."""
    s = (name or "").strip()
    if not s:
        return s

    tokens = s.split()
    mode = mode.lower()

    if mode == "swap_word" and len(tokens) >= 2:
        a, b = tokens[0], tokens[1]
        tokens[0], tokens[1] = b, a
        return " ".join(tokens)

    # typo mode (default)
    # Choose one simple transformation deterministically per call.
    r = random.random()

    # remove a token sometimes
    if len(tokens) >= 3 and r < 0.25:
        # remove a middle token
        idx = min(max(1, len(tokens) // 2), len(tokens) - 2)
        tokens.pop(idx)
        return " ".join(tokens)

    # truncate sometimes
    if r < 0.45:
        k = random.randint(3, max(3, min(len(s), 12)))
        return s[:k].rstrip()

    # replace/swap a character
    chars = list(s)
    if len(chars) >= 5:
        i = random.randint(1, len(chars) - 2)
        j = random.randint(1, len(chars) - 2)
        if r < 0.7:
            chars[i], chars[j] = chars[j], chars[i]
        else:
            # replace with a nearby ascii char (rough typo)
            repl = chr(((ord(chars[i].lower()) - 97 + 1) % 26) + 97) if chars[i].isalpha() else "x"
            chars[i] = repl
    return "".join(chars)


def main() -> int:
    n = int(os.getenv("BENCH_N", "30"))
    perturb_mode = os.getenv("BENCH_PERTURB_MODE", "typo")
    out_name = os.getenv("BENCH_OUTPUT_JSON", "benchmark_hotel_entity_resolver_results.json")

    examples = load_examples(n)

    # Empty candidates: resolver uses Qdrant primarily.
    candidates: list[HotelCandidate | dict[str, Any]] = []

    results: list[dict[str, Any]] = []
    latencies: list[float] = []

    for i, ex in enumerate(examples, start=1):
        input_name = perturb_name(ex.hotel_name, perturb_mode)

        t0 = time.perf_counter()
        res = hotel_entity_resolver.resolve(
            input_name,
            candidates,
            city=ex.city,
        )
        dt = time.perf_counter() - t0
        latencies.append(dt)

        results.append(
            {
                "i": i,
                "expected": {
                    "hotel_id": ex.hotel_id,
                    "hotel_name": ex.hotel_name,
                    "city": ex.city,
                },
                "input_name": input_name,
                "got": {
                    "status": res.status,
                    "hotel_id": res.hotel_id,
                    "canonical_name": res.canonical_name,
                    "confidence": res.confidence,
                    "candidates": res.candidates[:5],
                },
                "latency_ms": dt * 1000.0,
            }
        )

        if i % 10 == 0:
            avg_ms = (sum(latencies) / len(latencies)) * 1000
            print(f"[{i}/{len(examples)}] avg_ms={avg_ms:.2f} last_status={res.status}")

    avg_ms = (sum(latencies) / len(latencies)) * 1000 if latencies else 0.0

    ok = sum(1 for r in results if r["got"]["status"] == "resolved" and r["got"]["hotel_id"] == r["expected"]["hotel_id"])
    ambiguous = sum(1 for r in results if r["got"]["status"] == "ambiguous")
    not_found = sum(1 for r in results if r["got"]["status"] == "not_found")

    summary = {
        "n": len(examples),
        "perturb_mode": perturb_mode,
        "avg_latency_ms": avg_ms,
        "accuracy_resolved_and_id_match": (ok / len(examples)) if examples else 0.0,
        "resolved_ok": ok,
        "ambiguous": ambiguous,
        "not_found": not_found,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / out_name

    payload = {
        "summary": summary,
        "results": results,
        "csv_path": str(CSV_PATH),
        "qdrant_collection": os.getenv("QDRANT_COLLECTION", "hotels"),
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n=== Smoke Benchmark Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

