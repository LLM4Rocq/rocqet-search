#!/usr/bin/env python3
"""Extract the FLT theorem corpus from the anthropics/fermats-last-theorem html/ data.

Reads the static data files (no browser needed):
  html/data/meta.js    - theorem names, stages, aliases, tree info
  html/data/edges.js   - citation graph (CSR: off/dst = cites)
  html/data/titles.js  - English titles, parallel to names
  html/data/ddecl.js   - declaration kinds (theorem/lemma/def/...)
  html/data/shard/*.js - per-theorem records (Lean statement, English summary, ...)

Writes one JSONL row per theorem:
  {name, module, kind, title, summary, statement, context,
   stage, stage_name, aliases, cites, cited_by}

The Lean statement (dc) is authoritative; the English summary is generated.
Both are kept as separate fields, never merged.

Usage:
  python3 flt/extract.py --html-dir /path/to/html --out flt/data/theorems.jsonl
"""

from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
from pathlib import Path

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def html_to_text(s: str) -> str:
    """Strip tags, unescape entities, collapse whitespace."""
    if not s:
        return ""
    s = TAG_RE.sub(" ", s)
    s = htmlmod.unescape(s)
    return WS_RE.sub(" ", s).strip()


def load_json_after_prefix(path: Path, prefix: str):
    raw = path.read_text(encoding="utf-8")
    i = raw.index(prefix) + len(prefix)
    body = raw[i:].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def load_loose_js(path: Path, var: str):
    """Parse a JS object literal with unquoted keys (like edges.js)."""
    raw = path.read_text(encoding="utf-8")
    i = raw.index("{", raw.index(var))
    body = raw[i:].rstrip()
    if body.endswith(";"):
        body = body[:-1]
    body = re.sub(r"([{,])([A-Za-z_][A-Za-z0-9_]*):", r'\1"\2":', body)
    return json.loads(body)


def load_shard(path: Path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r'FLT_SHARD_CB\("[0-9a-f]+",(.*)\);\s*$', raw, re.S)
    if not m:
        raise ValueError(f"cannot parse shard {path}")
    return json.loads(m.group(1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-dir", required=True, help="path to the html/ folder of the FLT repo")
    ap.add_argument("--out", required=True, help="output .jsonl path")
    args = ap.parse_args()

    html_dir = Path(args.html_dir)
    data = html_dir / "data"

    meta = load_json_after_prefix(data / "meta.js", "window.FLT_META=")
    names: list[str] = meta["names"]
    n = len(names)
    print(f"theorems: {n}")

    edges = load_loose_js(data / "edges.js", "FLT_EDGES")
    off, dst = edges["off"], edges["dst"]
    assert len(off) == n + 1, (len(off), n)

    # titles.js: window.FLT_TITLES=[ ... ];
    traw = (data / "titles.js").read_text(encoding="utf-8")
    titles = json.loads(traw[traw.index("["):traw.rindex("]") + 1])
    assert len(titles) == n, (len(titles), n)

    ddecl = load_json_after_prefix(data / "ddecl.js", "window.FLT_DDECL=")
    kind_of = {rec[0]: rec[3] for rec in ddecl["ddecl"] if len(rec) > 3}

    stages = meta.get("stages", {})
    stage_of = meta.get("stage", [])
    aliases = meta.get("aliases", {})

    # cited_by: reverse the cites CSR
    cited_by: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for k in range(off[i], off[i + 1]):
            cited_by[dst[k]].append(i)

    # shard records keyed by theorem name
    records: dict[str, dict] = {}
    shard_dir = data / "shard"
    shard_files = sorted(shard_dir.glob("*.js"))
    for sf in shard_files:
        records.update(load_shard(sf))
    print(f"shard records: {len(records)} from {len(shard_files)} shards")

    missing = [nm for nm in names if nm not in records]
    print(f"names without shard record: {len(missing)}")
    if missing:
        print("  e.g.", missing[:5])

    n_with_summary = 0
    n_with_statement = 0
    rows = []
    for i, nm in enumerate(names):
        rec = records.get(nm, {})
        en = rec.get("en") or {}
        summary = html_to_text(en.get("statement_html", ""))
        context = html_to_text(en.get("context_html", ""))
        statement = rec.get("dc", "") or ""
        if summary:
            n_with_summary += 1
        if statement:
            n_with_statement += 1
        module = nm.rsplit(".", 1)[0] if "." in nm else ""
        st = stage_of[i] if i < len(stage_of) else None
        rows.append({
            "name": nm,
            "module": module,
            "kind": kind_of.get(nm, ""),
            "title": titles[i] or "",
            "summary": summary,
            "statement": statement,
            "context": context,
            "stage": st,
            "stage_name": stages.get(str(st), "") if st is not None else "",
            "aliases": [a.strip() for a in aliases.get(nm, "").split(";") if a.strip()],
            "cites": [names[d] for d in dst[off[i]:off[i + 1]]],
            "cited_by": [names[j] for j in cited_by[i]],
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_cites = sum(len(r["cites"]) for r in rows)
    n_cited_by = sum(len(r["cited_by"]) for r in rows)
    print(f"wrote {len(rows)} rows -> {out} ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"with summary: {n_with_summary}, with statement: {n_with_statement}")
    print(f"cite edges: {n_cites}, cited_by edges: {n_cited_by} (must match)")


if __name__ == "__main__":
    main()
