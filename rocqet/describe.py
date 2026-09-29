"""Generate natural-language descriptions for declarations with an LLM.

Terse formal declarations (e.g. `mulrA`, GeoCoq `OFSC`) carry almost no text for a
semantic-search embedding to match an English query against. This makes a one-time,
OFFLINE pass that writes a plain-English `nl_description` per declaration; that text
is then embedded alongside the formal content. Serving stays LLM-free — this only
touches indexing.

Two backends:
  gemini  Direct Gemini API calls. Needs GEMINI_API_KEY.
  claude  Shells out to the local `claude` CLI (Claude Code) in --print mode with
          --model haiku. No API key needed — rides your existing Claude Code auth.
          Cheap (~$0.0005/declaration) and fast with a few --workers.

Resumable: descriptions are cached by stable_id in data/descriptions_cache.jsonl,
so re-runs skip what's already done and a crash never loses work.

    GEMINI_API_KEY=... python -m rocqet.describe --library geocoq
    python -m rocqet.describe --backend claude --library stdlib --workers 6
    python -m rocqet.describe --backend claude --library stdlib --limit 24   # test slice

The Gemini API key is read from the environment and never written to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

from rocqet.schema import normalize_declaration, stable_id

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
CLAUDE_MODEL = os.environ.get("ROCQET_CLAUDE_MODEL", "haiku")

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "INTEGER"}, "description": {"type": "STRING"}},
        "required": ["id", "description"],
    },
}

PROMPT_HEADER = (
    "You are writing search descriptions for declarations from a Rocq/Coq formal "
    "library, for a semantic search engine. For each declaration, write ONE concise "
    "plain-English sentence describing what it states or defines — the way a "
    "mathematician would phrase it when searching for it. Do NOT use Coq syntax and "
    "do NOT just restate the identifier name. Return a JSON array of "
    '{"id", "description"} for every item.\n\nDeclarations:\n'
)

# Same task, phrased for a plain-text response (no responseSchema support over the
# claude CLI) — explicit about the numeric id and the "no fences" ask, since Haiku
# sometimes wraps the array in ```json fences anyway (stripped in _parse_json_array).
CLAUDE_PROMPT_HEADER = (
    "You are writing search descriptions for declarations from a Rocq/Coq formal "
    "library, for a semantic search engine. For each declaration, write ONE concise "
    "plain-English sentence describing what it states or defines — the way a "
    "mathematician would phrase it when searching for it. Do NOT use Coq syntax and "
    "do NOT just restate the identifier name. Return ONLY a raw JSON array (no "
    'markdown fences, no prose) of {"id", "description"} objects, using the exact '
    "numeric id shown in brackets for each declaration.\n\nDeclarations:\n"
)


def decl_line(i: int, d: dict) -> str:
    sig = d.get("type_signature") or ""
    stmt = (d.get("statement") or "")[:320]
    body = sig if sig else stmt
    return f"[{i}] {d.get('kind','')} {d.get('name','')} :: {body}"


def describe_batch(batch: list[dict], key: str, timeout: float = 60.0) -> dict[int, str]:
    prompt = PROMPT_HEADER + "\n".join(decl_line(i, d) for i, d in enumerate(batch))
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    url = ENDPOINT.format(model=MODEL, key=key)
    for attempt in range(6):
        try:
            resp = httpx.post(url, json=body, timeout=timeout)
        except httpx.RequestError:  # transient DNS/connection/timeout blip — back off and retry
            time.sleep(2 ** attempt * 2)
            continue
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(text)
            return {int(it["id"]): str(it["description"]).strip() for it in items if "id" in it}
        if resp.status_code in (403, 429, 500, 503):  # 403 is intermittent on these tokens
            time.sleep(2 ** attempt * 2)
            continue
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
    raise RuntimeError("Gemini retries exhausted (rate limit / server errors)")


def _parse_json_array(text: str) -> list[dict]:
    """Strip ```json fences (Haiku adds them despite instructions not to) and parse."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(text)


def describe_batch_claude(batch: list[dict], timeout: float = 90.0) -> dict[int, str]:
    prompt = CLAUDE_PROMPT_HEADER + "\n".join(decl_line(i, d) for i, d in enumerate(batch))
    for attempt in range(4):
        try:
            proc = subprocess.run(
                ["claude", "-p", "--model", CLAUDE_MODEL, "--tools", "", "--output-format", "json"],
                input=prompt, capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            time.sleep(2 ** attempt * 2)
            continue
        if proc.returncode != 0:
            time.sleep(2 ** attempt * 2)
            continue
        try:
            envelope = json.loads(proc.stdout)
            if envelope.get("is_error"):
                raise ValueError(envelope.get("result", "claude CLI reported an error"))
            items = _parse_json_array(envelope["result"])
            return {int(it["id"]): str(it["description"]).strip() for it in items if "id" in it}
        except (json.JSONDecodeError, KeyError, ValueError):
            time.sleep(2 ** attempt * 2)
            continue
    raise RuntimeError("claude CLI retries exhausted")


def load_cache(path: Path) -> dict[int, str]:
    cache: dict[int, str] = {}
    if path.exists():
        for line in path.open(encoding="utf-8"):
            if line.strip():
                rec = json.loads(line)
                cache[int(rec["id"])] = rec["nl_description"]
    return cache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/declarations.enriched.jsonl"))
    parser.add_argument("--cache", type=Path, default=Path("data/descriptions_cache.jsonl"))
    parser.add_argument("--library", help="Only describe this library (e.g. geocoq). Default: all.")
    parser.add_argument("--backend", choices=["gemini", "claude"], default="gemini",
                        help="gemini: direct API (needs GEMINI_API_KEY). "
                             "claude: local `claude` CLI, no API key needed.")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel batches in flight (claude backend only).")
    parser.add_argument("--limit", type=int, default=0, help="Describe at most N (0 = all). For test runs.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause between calls (rate-limit friendly).")
    parser.add_argument("--write-back", action="store_true",
                        help="After describing, write nl_description into --input from the cache.")
    args = parser.parse_args(argv)

    key = None
    if args.backend == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SystemExit("Set GEMINI_API_KEY in the environment.")

    records = [normalize_declaration(json.loads(line))
               for line in args.input.open(encoding="utf-8") if line.strip()]
    cache = load_cache(args.cache)
    print(f"loaded {len(records):,} records; cache has {len(cache):,} descriptions")

    targets = [r for r in records if (not args.library or r["library"] == args.library)]
    todo = [r for r in targets if stable_id(r) not in cache]
    if args.limit:
        todo = todo[: args.limit]
    print(f"describing {len(todo):,} of {len(targets):,} '{args.library or 'all'}' "
          f"declarations via {args.backend} (rest cached)")

    batches = [todo[start : start + args.batch_size] for start in range(0, len(todo), args.batch_size)]

    def run_batch(batch: list[dict]) -> tuple[list[dict], dict[int, str] | None, str | None]:
        try:
            if args.backend == "claude":
                return batch, describe_batch_claude(batch), None
            return batch, describe_batch(batch, key), None
        except Exception as exc:  # noqa: BLE001 - one bad batch must not kill the run
            return batch, None, str(exc)[:150]

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    failed = 0
    workers = max(1, args.workers if args.backend == "claude" else 1)
    with args.cache.open("a", encoding="utf-8") as cf:
        if workers == 1:
            batch_results = (run_batch(b) for b in batches)
        else:
            from concurrent.futures import ThreadPoolExecutor

            pool = ThreadPoolExecutor(max_workers=workers)
            batch_results = pool.map(run_batch, batches)
        for batch, results, error in batch_results:
            if error is not None:
                failed += len(batch)
                print(f"  [{done}/{len(todo)}] batch failed, skipping: {error}")
                continue
            for i, d in enumerate(batch):
                desc = results.get(i)
                if desc:
                    cf.write(json.dumps({"id": stable_id(d), "name": d["name"],
                                         "nl_description": desc}, ensure_ascii=False) + "\n")
                    cf.flush()
            done += len(batch)
            print(f"  [{done}/{len(todo)}] described")
            if workers == 1:
                time.sleep(args.sleep)
        if failed:
            print(f"  {failed} declarations failed this pass — re-run to retry them (cache resumes the rest).")

    if args.write_back:
        cache = load_cache(args.cache)
        out = args.input.with_suffix(".tmp")
        updated = 0
        with out.open("w", encoding="utf-8") as f:
            for r in records:
                desc = cache.get(stable_id(r))
                if desc:
                    r["nl_description"] = desc
                    updated += 1
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        out.replace(args.input)
        print(f"wrote nl_description into {args.input} for {updated:,} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
