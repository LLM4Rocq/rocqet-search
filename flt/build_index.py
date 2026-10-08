#!/usr/bin/env python3
"""Build the FLT search artifact: title embeddings.

Reads flt/data/theorems.jsonl (see flt/extract.py), embeds every theorem's
English title (+ curated aliases), L2-normalises, and writes:

  flt/data/emb_title.npy  float32 (N, D)

The Lean statement is matched lexically by BM25 at query time, so it needs
no dense view. Takes a few minutes on a laptop CPU.

Uses fastembed (ONNX, no torch) when available, else sentence-transformers.
Same model as the main Rocqet index: sentence-transformers/all-MiniLM-L6-v2
(override with FLT_EMBED_MODEL).

Usage:
  python3 flt/build_index.py            # from the repo root
  python3 flt/build_index.py --data-dir /path/to/flt/data
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="flt/data")
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in (data_dir / "theorems.jsonl").read_text(encoding="utf-8").splitlines()]
    n = len(rows)
    print(f"theorems: {n}")

    # import the text views from the search module so build and serve agree
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rocqet.flt import FLTIndex, get_embedder

    # reuse FLTIndex text builders without loading embeddings: bind manually
    idx_texts = FLTIndex.__new__(FLTIndex)
    idx_texts.rows = rows
    title_texts = [FLTIndex.title_text(idx_texts, i) for i in range(n)]

    embed_fn, dim = get_embedder()
    print(f"embedder dim: {dim}")

    def embed_all(texts: list[str], tag: str) -> np.ndarray:
        vecs = []
        t0 = time.time()
        for s in range(0, n, args.batch_size):
            batch = embed_fn(texts[s:s + args.batch_size])
            vecs.extend(batch)
            if (s // args.batch_size) % 20 == 0:
                done = min(s + args.batch_size, n)
                rate = done / max(time.time() - t0, 1e-6)
                print(f"  {tag}: {done}/{n} ({rate:.0f}/s)", flush=True)
        mat = np.stack([np.asarray(v, dtype=np.float32) for v in vecs]).astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (mat / norms).astype(np.float32)

    print("embedding title view...")
    emb_title = embed_all(title_texts, "title")

    np.save(data_dir / "emb_title.npy", emb_title)
    print(f"saved {emb_title.shape} -> {data_dir/'emb_title.npy'}")
    print("done.")


if __name__ == "__main__":
    main()
