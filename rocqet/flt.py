"""Fermat's Last Theorem search for Rocqet.

Hybrid dense + BM25 retrieval over the 29,511 theorems of the
anthropics/fermats-last-theorem formalisation, plus citation-graph
expansion for "where is X used" queries.

Data layout (FLT_DATA_DIR, default "flt/data"):
  theorems.jsonl - one row per theorem (see flt/extract.py)
  emb_title.npy  - float32 (N, D) L2-normalised title embeddings

Two search modes:
  what - "what is X": hybrid dense+BM25 fused with RRF, top seeds win.
  used - "where is X used": take the top seeds, walk cited_by edges
         outward up to 3 hops, rank by distance-decayed seed score,
         group by proof stage.

The Lean statement is authoritative; the English summary is generated.
Both are kept as separate fields. The dense view is the English title
(+ curated aliases) -- measured on real queries, the long summaries
dilute the embedding and rank worse than title-only. BM25 indexes
name + title + summary + statement + aliases, so exact Lean/Mathlib
terms are matched lexically.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import deque
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("FLT_DATA_DIR", "flt/data"))
EMBED_MODEL = os.environ.get("FLT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DOCS_URL = "https://tianyipeng.github.io/fermats-last-theorem"
RRF_K = 60
SEED_K = 25
MAX_HOPS = 3
HOP_DECAY = 0.5

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _get_embedder():
    """fastembed (ONNX, no torch) preferred; sentence-transformers as fallback."""
    try:
        from fastembed import TextEmbedding

        emb = TextEmbedding(EMBED_MODEL)
        dim = emb._model_dim if hasattr(emb, "_model_dim") else 384
        return lambda texts: [np.asarray(v, dtype=np.float32) for v in emb.embed(texts)], dim
    except Exception as e:  # noqa: BLE001
        logger.info("fastembed unavailable (%s), using sentence-transformers", e)
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)
        return lambda texts: [
            np.asarray(v, dtype=np.float32)
            for v in model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        ], int(model.get_sentence_embedding_dimension())


_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = _get_embedder()
    return _embedder


class FLTIndex:
    """In-memory FLT search index. 29k theorems: brute force is plenty."""

    def __init__(self, data_dir: Path = DATA_DIR):
        t0 = time.time()
        self.data_dir = Path(data_dir)
        self.rows: list[dict] = [
            json.loads(line) for line in (self.data_dir / "theorems.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.n = len(self.rows)
        self.name_to_idx = {r["name"]: i for i, r in enumerate(self.rows)}

        self.emb_title = np.load(self.data_dir / "emb_title.npy").astype(np.float32)
        assert self.emb_title.shape[0] == self.n, (self.emb_title.shape, self.n)

        # citation graph (indices)
        self.cites: list[list[int]] = []
        self.cited_by: list[list[int]] = [[] for _ in range(self.n)]
        for i, r in enumerate(self.rows):
            cs = [self.name_to_idx[c] for c in r["cites"] if c in self.name_to_idx]
            self.cites.append(cs)
            for c in cs:
                self.cited_by[c].append(i)

        # BM25 over name + title + summary + statement + aliases
        from rank_bm25 import BM25Okapi

        corpus = [self._bm25_doc(r) for r in self.rows]
        self.bm25 = BM25Okapi(corpus)
        logger.info("FLT index ready: %d theorems in %.1fs", self.n, time.time() - t0)

    @staticmethod
    def _bm25_doc(r: dict) -> list[str]:
        return tokenize(
            " ".join([
                r["name"].replace(".", " ").replace("_", " "),
                r["title"],
                r["summary"],
                r["statement"],
                " ".join(r.get("aliases", [])),
            ])
        )

    # -- texts -----------------------------------------------------------
    def title_text(self, i: int) -> str:
        # English title + curated aliases. Deliberately NOT the full summary:
        # measured on real queries, the long summaries dilute the embedding
        # and rank worse than title-only (e.g. "modularity lifting").
        # The full summary is still indexed by BM25 for term matching.
        r = self.rows[i]
        parts = [r["title"]]
        if r.get("aliases"):
            parts.append("; ".join(r["aliases"]))
        return " ".join(p for p in parts if p)

    # -- retrieval -------------------------------------------------------
    @staticmethod
    def _rrf(ranks: list[list[int]], k: int = RRF_K) -> dict[int, float]:
        scores: dict[int, float] = {}
        for ranking in ranks:
            for rank, idx in enumerate(ranking):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
        return scores

    def _hybrid_scores(self, query: str) -> dict[int, float]:
        embed_fn, _ = get_embedder()
        q = embed_fn([query])[0].astype(np.float32)
        nrm = float(np.linalg.norm(q)) or 1.0
        q = q / nrm
        dense = self.emb_title @ q
        order_dense = list(np.argsort(-dense, kind="stable"))

        bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
        order_bm25 = list(np.argsort(-bm25_scores, kind="stable"))

        return self._rrf([order_dense, order_bm25])

    def _record(self, i: int, score: float, distance: int | None = None) -> dict:
        r = self.rows[i]
        return {
            "name": r["name"],
            "module": r["module"],
            "title": r["title"],
            "summary": r["summary"],
            "statement": r["statement"],
            "stage": r["stage"],
            "stage_name": r["stage_name"],
            "aliases": r.get("aliases", []),
            "score": round(float(score), 4),
            "distance": distance,
            "n_cites": len(self.cites[i]),
            "n_cited_by": len(self.cited_by[i]),
            "url": f"{DOCS_URL}/thm.html#{r['name']}",
        }

    def search(self, query: str, mode: str = "what", limit: int = 10) -> dict:
        t0 = time.time()
        fused = self._hybrid_scores(query)
        ranked = sorted(fused.items(), key=lambda kv: -kv[1])
        seeds = ranked[:SEED_K]

        if mode == "used":
            # walk cited_by outward from the seeds; each reached theorem is
            # scored by its best seed's fused score, decayed by hop distance
            best: dict[int, tuple[int, float]] = {}
            for s_idx, s_sc in seeds:
                dq = deque([(s_idx, 0)])
                seen = {s_idx}
                while dq:
                    u, d = dq.popleft()
                    if d >= MAX_HOPS:
                        continue
                    for v in self.cited_by[u]:
                        if v in seen:
                            continue
                        seen.add(v)
                        cand = s_sc * (HOP_DECAY ** (d + 1))
                        if cand > best.get(v, (0, 0.0))[1]:
                            best[v] = (d + 1, cand)
                        dq.append((v, d + 1))
            results = [
                self._record(i, sc, distance=d) for i, (d, sc) in sorted(best.items(), key=lambda kv: -kv[1][1])
            ]
            groups: dict[str, list[str]] = {}
            for rec in results[:limit]:
                groups.setdefault(rec["stage_name"] or "Unstaged", []).append(rec["name"])
        else:
            results = [self._record(i, sc) for i, sc in ranked[:limit]]
            groups = {}

        return {
            "query": query,
            "mode": mode,
            "seeds": [self._record(i, sc) for i, sc in seeds[:5]],
            "results": results[:limit],
            "groups": groups,
            "total": self.n,
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
        }

    def get_theorem(self, name: str) -> dict | None:
        i = self.name_to_idx.get(name)
        if i is None:
            return None
        return self._record(i, 1.0)

    def stats(self) -> dict:
        from collections import Counter

        stages = Counter(r["stage_name"] or "Unstaged" for r in self.rows)
        return {
            "total_theorems": self.n,
            "total_edges": sum(len(c) for c in self.cites),
            "stages": dict(stages.most_common()),
        }


_index: FLTIndex | None = None


def get_index() -> FLTIndex:
    global _index
    if _index is None:
        _index = FLTIndex()
    return _index
