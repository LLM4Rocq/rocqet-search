# Dataset

Rocqet searches a corpus of declarations extracted from Rocq/Coq libraries. The
indexed artifact is `deploy/declarations.enriched.jsonl` — one JSON record per
declaration (name, kind, type signature, statement, docstring, module/library,
GitHub URL, and a natural-language description). All four libraries below ship
with descriptions (~96-100% coverage per library).

The dataset embeds verbatim text from each library's own source under that
library's own license, not Rocqet's — see [../NOTICE.md](../NOTICE.md)
before redistributing it.

This file is a **build output**. It is *not* committed to git (it is large and
regenerable), so you get it one of two ways:

## Option 1 — download the prebuilt dataset (fastest)

Grab `declarations.enriched.jsonl` from the latest
[GitHub Release](../../releases/latest) and drop it in `deploy/`:

```bash
mkdir -p deploy
# e.g. with the GitHub CLI:
gh release download --pattern declarations.enriched.jsonl --dir deploy
```

No Rocq toolchain required.

## Option 2 — rebuild it from source

Regenerate the dataset from the upstream library checkouts:

```bash
./scripts/build_dataset.sh
```

This fetches the library repos, extracts declarations (GeoCoq is curated to the
geometry-relevant subdirectories and Lemma/Theorem/Definition/Corollary only),
then enriches and de-duplicates into `deploy/declarations.enriched.jsonl`.
Extraction is pure parsing — `coqc` is **not** needed. Override the library set
with `LIBS="stdlib mathcomp" ./scripts/build_dataset.sh`.

## Indexing

Once `deploy/declarations.enriched.jsonl` exists, index it into Qdrant:

- Local on-disk store: `./scripts/build_index.sh` (or `rocqet-index`)
- Managed/Cloud Qdrant: `./scripts/index_cloud.sh` (set `QDRANT_URL` / `QDRANT_API_KEY`)

## Current corpus

| Library | Source | Descriptions from |
|---|---|---|
| `stdlib` | rocq-prover/stdlib | Rocqet (`rocqet.describe`) |
| `mathcomp` | math-comp/math-comp | [LLM4Docq](https://github.com/LLM4Rocq/LLM4Docq-MathComp) — see [../NOTICE.md](../NOTICE.md) |
| `mathcomp-analysis` | math-comp/analysis | Rocqet (`rocqet.describe`) |
| `geocoq` | GeoCoq/GeoCoq (curated) | Rocqet (`rocqet.describe`) |

`build_dataset.sh` extracts and enriches all four libraries but does not
attach mathcomp's descriptions — that's a separate join step,
`scripts/attach_mathcomp_nl.py`, against the external LLM4Docq dataset.

Refresh by re-running the build (Option 2) and re-indexing; point ids are
deterministic, so re-indexing upserts in place with no downtime.
