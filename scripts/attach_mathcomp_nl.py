"""Attach mathcomp natural-language descriptions to the indexed declarations and
carve out a leakage-safe NL eval set.

Input
  data/mathcomp-natural-lang.json      22,803 mathcomp decls, each with a 100%-
                                       covered ``informal_description`` + ``informal_name``.
  data/declarations.enriched.jsonl     the 44k indexed corpus (mathcomp slice has
                                       ~no descriptions today -> this is the lift).

Join
  By ``informal_name`` == decl ``name``; when a name is ambiguous (several decls
  share it) we disambiguate by signature/statement token overlap. ~96% of the
  19,448 indexed mathcomp decls receive a description.

Leakage trap (why the eval is built here, not naively)
  The descriptions are embedded into each doc's vector (schema.declaration_text
  puts nl_description first). If we ALSO used a decl's own description as its eval
  query, the query would trivially retrieve its own doc -> fake ~95% hit@1. So we
  HOLD OUT the eval golds: those decls keep an empty description in the index,
  while every other mathcomp decl gets enriched. A hit then reflects genuine
  corpus enrichment, not a leaked gold.

Outputs
  data/eval/nl_queries_mathcomp.jsonl          {query=description, gold=[name], hint=module}
  data/declarations.enriched.mc.jsonl          full corpus, mathcomp enriched,
                                               eval golds held out (for honest eval)
  data/declarations.enriched.mc.ship.jsonl     full corpus, ALL mathcomp enriched
                                               (no holdout) -> for the production ship

    python scripts/attach_mathcomp_nl.py --eval-size 300
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

_TOK = re.compile(r"[A-Za-z0-9_]+")


def sig_overlap(a: str, b: str) -> float:
    A = set(_TOK.findall((a or "").lower()))
    B = set(_TOK.findall((b or "").lower()))
    return len(A & B) / len(A | B) if A and B else 0.0


def build_join(mc_json: list[dict], mc_decls: list[dict]) -> dict[int, str]:
    """Map id(decl) -> description. Unique-name -> direct; ambiguous -> best signature overlap."""
    by_name: dict[str, list[dict]] = collections.defaultdict(list)
    for x in mc_json:
        by_name[x["informal_name"]].append(x)

    out: dict[int, str] = {}
    for d in mc_decls:
        cands = by_name.get(d["name"])
        if not cands:
            continue
        if len(cands) == 1:
            best = cands[0]
        else:
            declsig = d.get("statement") or d.get("type_signature") or ""
            best = max(cands, key=lambda c: sig_overlap(c.get("signature", ""), declsig))
        desc = (best.get("informal_description") or "").strip()
        if desc:
            out[id(d)] = desc
    return out


def is_eval_pick(name: str, eval_frac: float) -> bool:
    """Deterministic holdout by name hash (reproducible, no RNG)."""
    h = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
    return (h % 10000) < int(eval_frac * 10000)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=Path("data/mathcomp-natural-lang.json"))
    ap.add_argument("--decls", type=Path, default=Path("data/declarations.enriched.jsonl"))
    ap.add_argument("--out-eval", type=Path, default=Path("data/eval/nl_queries_mathcomp.jsonl"))
    ap.add_argument("--out-base", type=Path, default=Path("data/declarations.mathcomp.base.jsonl"))
    ap.add_argument("--out-enriched", type=Path, default=Path("data/declarations.mathcomp.enriched.jsonl"))
    ap.add_argument("--out-ship", type=Path, default=Path("data/declarations.mathcomp.ship.jsonl"))
    ap.add_argument("--eval-size", type=int, default=300, help="approx held-out eval queries")
    args = ap.parse_args(argv)

    mc_json = json.load(args.json.open(encoding="utf-8"))
    decls = [json.loads(line) for line in args.decls.open(encoding="utf-8") if line.strip()]
    mc_decls = [d for d in decls if d.get("library") == "mathcomp"]

    desc_by_id = build_join(mc_json, mc_decls)

    # Eval candidates: unambiguous name (so gold=[name] is unique), has a description,
    # and the description does NOT mention the name (else lexical rerank would leak it).
    name_counts = collections.Counter(d["name"] for d in mc_decls)
    cand = [d for d in mc_decls
            if id(d) in desc_by_id and name_counts[d["name"]] == 1
            and d["name"].lower() not in desc_by_id[id(d)].lower()]
    eval_frac = min(0.99, args.eval_size / max(len(cand), 1))
    eval_decls = [d for d in cand if is_eval_pick(d["name"], eval_frac)]
    holdout = {d["name"] for d in eval_decls}

    # Eval set
    args.out_eval.parent.mkdir(parents=True, exist_ok=True)
    with args.out_eval.open("w", encoding="utf-8") as f:
        for d in eval_decls:
            mod = (d.get("module_path") or "mathcomp").split(".")[0]
            f.write(json.dumps({"query": desc_by_id[id(d)], "gold": [d["name"]],
                                "hint": mod}, ensure_ascii=False) + "\n")

    # Mathcomp-only corpora. All three index the SAME 19,448 decls, differing only
    # in descriptions, so an A/B is a clean test of the descriptions alone:
    #   base     -> no descriptions (the honest "before")
    #   enriched -> descriptions attached, eval golds held out (the honest "after")
    #   ship      -> every decl enriched (production)
    def write_corpus(path: Path, attach: bool, hold: set[str]) -> int:
        n = 0
        with path.open("w", encoding="utf-8") as f:
            for d in mc_decls:
                desc = desc_by_id.get(id(d))
                if attach and desc and d["name"] not in hold:
                    d = {**d, "nl_description": desc}
                    n += 1
                else:
                    d = {**d, "nl_description": ""}
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return n

    write_corpus(args.out_base, attach=False, hold=set())
    n_honest = write_corpus(args.out_enriched, attach=True, hold=holdout)
    n_ship = write_corpus(args.out_ship, attach=True, hold=set())

    print(f"mathcomp decls            : {len(mc_decls):,}")
    print(f"matched a description     : {len(desc_by_id):,} ({len(desc_by_id)/len(mc_decls):.0%})")
    print(f"unambiguous eval candidates: {len(cand):,}")
    print(f"held-out eval queries     : {len(eval_decls):,}  -> {args.out_eval}")
    print(f"base   (no desc)          : {len(mc_decls):,}  -> {args.out_base}")
    print(f"enriched (holdout)        : {n_honest:,} enriched  -> {args.out_enriched}")
    print(f"ship   (all enriched)     : {n_ship:,} enriched  -> {args.out_ship}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
