"""Build FAISS index for chunked_hotels_enriched.json

Embeddings are stored in FAISS.
Metadata is NOT embedded; it is stored in JSON sidecars for post-filtering.

Outputs (default under data/):
- data/faiss_hotels.index
- data/faiss_hotels_meta.json   (vector_id -> metadata dict)
- data/faiss_hotels_chunks.json (vector_id -> chunk payload)
- data/faiss_hotels_config.json

Usage:
  python scripts/build_faiss_hotels_index.py \
    --input data/chunked_hotels_enriched.json \
    --output_dir data

Notes:
- Your FAISS wheel appears to not support add_with_ids for IndexHNSWFlat.
  Therefore this builder uses IVF / IVF-PQ only (both support add_with_ids).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


def _detect_best_embedding_text(chunk: Dict[str, Any]) -> str:
    """Best-effort: choose text fields for embedding."""
    content = chunk.get("content")
    if isinstance(content, str) and content.strip():
        return content

    section = chunk.get("section")
    metadata = chunk.get("metadata")

    parts: List[str] = []
    if section:
        parts.append(f"section: {section}")

    if isinstance(metadata, dict):
        tags = metadata.get("tags")
        if isinstance(tags, list) and tags:
            parts.append("tags: " + ",".join(str(t) for t in tags))

        summary = metadata.get("summary")
        if isinstance(summary, str) and summary.strip():
            parts.append(summary)

    return "\n".join(parts).strip()


def _stable_vector_id(chunk: Dict[str, Any], fallback: int) -> int:
    cid = chunk.get("chunk_id") or chunk.get("id")
    if isinstance(cid, int):
        return cid
    if isinstance(cid, str) and cid.isdigit():
        return int(cid)
    return fallback


def _choose_index_params(n: int) -> Dict[str, Any]:
    """Heuristic to choose IVF vs IVF-PQ."""
    # Use IVF flat for most sizes, and IVF-PQ only when large.
    if n <= 50_000:
        return {
            "type": "ivf",
            "nlist": int(min(max(256, 8 * math.sqrt(n)), 2048)),
            "nprobe": 16,
        }

    # Large: IVF + PQ
    return {
        "type": "ivf_pq",
        "nlist": int(min(max(256, 8 * math.sqrt(n)), 4096)),
        "nprobe": 16,
        "m": 8,
        "nbits": 8,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default=str(
            Path(__file__).resolve().parents[1]
            / "data"
            / "chunked_hotels_enriched.json"
        ),
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data"),
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    idx_path = output_dir / "faiss_hotels.index"
    meta_path = output_dir / "faiss_hotels_meta.json"
    chunks_path = output_dir / "faiss_hotels_chunks.json"
    cfg_path = output_dir / "faiss_hotels_config.json"

    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("chunked_hotels_enriched.json must be a JSON array")

    # Lazy imports
    from sentence_transformers import SentenceTransformer
    import faiss  # type: ignore

    model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
    print(f"Loading embedding model: {model_name}")
    embedder = SentenceTransformer(model_name)

    texts: List[str] = []
    metas: Dict[str, Any] = {}
    chunks_by_vid: Dict[str, Any] = {}

    for i, chunk in enumerate(raw):
        if not isinstance(chunk, dict):
            continue

        vec_id = _stable_vector_id(chunk, i)
        text = _detect_best_embedding_text(chunk)
        if not text:
            continue

        texts.append(text)

        meta = chunk.get("metadata")
        if meta is None or not isinstance(meta, dict):
            meta = {}

        # Keep any section/hotel_id as top-level metadata for filtering convenience
        meta_out = dict(meta)
        if chunk.get("section") is not None:
            meta_out.setdefault("section", chunk.get("section"))
        if chunk.get("hotel_id") is not None:
            meta_out.setdefault("hotel_id", chunk.get("hotel_id"))

        vid_str = str(vec_id)
        metas[vid_str] = meta_out
        chunks_by_vid[vid_str] = {
            "chunk_id": chunk.get("chunk_id"),
            "section": chunk.get("section"),
            "content": chunk.get("content"),
            "metadata": meta_out,
        }

    n = len(texts)
    if n == 0:
        raise RuntimeError("No text chunks available to embed")

    print(f"Embedding {n} chunks...")
    batch_size = int(os.getenv("EMBED_BATCH_SIZE", "64"))

    vectors: List[np.ndarray] = []
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        batch_vecs = embedder.encode(
            texts[start:end],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors.append(np.array(batch_vecs, dtype=np.float32))
        if (start // batch_size) % 50 == 0:
            print(f"  embedded {end}/{n}")

    xb = np.vstack(vectors)
    dim = int(xb.shape[1])

    params = _choose_index_params(n)
    print(f"Index params: {params}")

    # Build index
    if params["type"] == "ivf":
        nlist = int(params["nlist"])
        nprobe = int(params["nprobe"])

        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(
            quantizer,
            dim,
            nlist,
            faiss.METRIC_INNER_PRODUCT,
        )
        index.nprobe = nprobe

        ids = np.array([int(k) for k in metas.keys()], dtype=np.int64)

        print("Training IVF quantizer...")
        index.train(xb)
        index.add_with_ids(xb, ids)

        cfg: Dict[str, Any] = {
            "dim": dim,
            "n": n,
            "type": "ivf",
            "nlist": nlist,
            "nprobe": nprobe,
            "metric": "ip_cosine",
            "id_mode": "external_chunk_id",
        }

    elif params["type"] == "ivf_pq":
        nlist = int(params["nlist"])
        nprobe = int(params["nprobe"])
        m = int(params["m"])
        nbits = int(params["nbits"])

        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFPQ(
            quantizer,
            dim,
            nlist,
            m,
            nbits,
            faiss.METRIC_INNER_PRODUCT,
        )
        index.nprobe = nprobe

        ids = np.array([int(k) for k in metas.keys()], dtype=np.int64)

        print("Training IVF-PQ...")
        index.train(xb)
        index.add_with_ids(xb, ids)

        cfg = {
            "dim": dim,
            "n": n,
            "type": "ivf_pq",
            "nlist": nlist,
            "nprobe": nprobe,
            "m": m,
            "nbits": nbits,
            "metric": "ip_cosine",
            "id_mode": "external_chunk_id",
        }
    else:
        raise ValueError(f"Unknown index type: {params['type']}")

    faiss.write_index(index, str(idx_path))

    # Save sidecars
    meta_path.write_text(json.dumps(metas, ensure_ascii=False), encoding="utf-8")
    chunks_path.write_text(json.dumps(chunks_by_vid, ensure_ascii=False), encoding="utf-8")

    cfg_path.write_text(
        json.dumps(
            {
                "embedding_model": model_name,
                "embed_normalized": True,
                **cfg,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Done.")
    print(f"- Index: {idx_path}")
    print(f"- Meta: {meta_path}")
    print(f"- Chunks: {chunks_path}")
    print(f"- Config: {cfg_path}")


if __name__ == "__main__":
    main()

