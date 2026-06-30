"""Turn the held-out mathcomp descriptions into realistic, NON-leaking search queries.

Why: evaluating with the verbatim ``informal_description`` as the query is leaky —
that exact text is embedded into the doc, so retrieval is trivial. A faithful NL
eval (the LeanSearch / Lean Finder method) uses a *different surface form*: a short
query a mathematician would actually type. This script rewrites each description
into such a query with an LLM, deliberately:

  * short (≈5–12 words), search-box style, not a full sentence;
  * NO Coq identifier names (so neither dense nor lexical can shortcut to the gold);
  * captures the concept AND its relation/role, not just the dominant noun.

Input  : data/eval/nl_queries_mathcomp.jsonl   (query=description, gold=[name], hint)
Output : data/eval/nl_queries_mathcomp_q.jsonl  (query=short paraphrase, gold, hint, source)

    GEMINI_API_KEYS=key1,key2 python scripts/make_query_eval.py
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from pathlib import Path

import httpx

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "INTEGER"}, "query": {"type": "STRING"}},
        "required": ["id", "query"],
    },
}

PROMPT_HEADER = (
    "You are generating evaluation queries for a semantic search engine over the "
    "Rocq/Coq MathComp library. For each item you are given a description of a lemma "
    "or definition. Rewrite it as ONE short search query that a mathematician would "
    "type into a search box to find this result.\n"
    "Rules:\n"
    "- 5 to 12 words, lowercase, no trailing period, not a full sentence.\n"
    "- Capture the key concept AND its relation/property (e.g. 'is associative', "
    "'is a morphism', 'divides'), not just the noun.\n"
    "- Do NOT copy the description wording verbatim; rephrase it.\n"
    "- Do NOT use any Coq/MathComp identifier names or symbols.\n"
    'Return a JSON array of {"id", "query"} for every item.\n\nItems:\n'
)


def keys() -> list[str]:
    multi = os.environ.get("GEMINI_API_KEYS", "")
    ks = [k.strip() for k in multi.split(",") if k.strip()]
    one = os.environ.get("GEMINI_API_KEY", "").strip()
    if one and one not in ks:
        ks.append(one)
    return ks


def gen_batch(batch: list[dict], key: str, timeout: float = 60.0) -> dict[int, str]:
    prompt = PROMPT_HEADER + "\n".join(f"[{i}] {b['query']}" for i, b in enumerate(batch))
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    url = ENDPOINT.format(model=MODEL, key=key)
    for attempt in range(6):
        try:
            resp = httpx.post(url, json=body, timeout=timeout)
        except httpx.RequestError:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return {int(it["id"]): str(it["query"]).strip()
                    for it in json.loads(text) if "id" in it}
        if resp.status_code in (403, 429, 500, 503):
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
    raise RuntimeError("Gemini retries exhausted")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("data/eval/nl_queries_mathcomp.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("data/eval/nl_queries_mathcomp_q.jsonl"))
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args(argv)

    ks = keys()
    if not ks:
        raise SystemExit("Set GEMINI_API_KEYS (comma-separated) or GEMINI_API_KEY.")
    key_cycle = itertools.cycle(ks)

    rows = [json.loads(line) for line in args.input.open(encoding="utf-8") if line.strip()]
    if args.limit:
        rows = rows[: args.limit]
    print(f"rewriting {len(rows)} descriptions into search queries ({len(ks)} key(s), model={MODEL})")

    out_rows: list[dict] = []
    for start in range(0, len(rows), args.batch_size):
        batch = rows[start:start + args.batch_size]
        got = gen_batch(batch, next(key_cycle))
        for i, b in enumerate(batch):
            q = got.get(i, "").strip()
            if not q:
                continue
            # safety: drop a query that still leaks the gold identifier
            if b["gold"][0].lower() in q.lower():
                continue
            out_rows.append({"query": q, "gold": b["gold"], "hint": b.get("hint", "?"),
                             "source": b["query"]})
        print(f"  {min(start + args.batch_size, len(rows))}/{len(rows)}")
        time.sleep(args.sleep)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out_rows)} query/gold pairs -> {args.out}")
    if out_rows:
        print("\nexamples (search query  <-  description):")
        for r in out_rows[:5]:
            print(f"  Q: {r['query']}")
            print(f"     gold: {r['gold'][0]}  |  src: {r['source'][:80]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
