# Rocqet

[![CI](https://github.com/LLM4Rocq/rocqet-search/actions/workflows/ci.yml/badge.svg)](https://github.com/LLM4Rocq/rocqet-search/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/github/license/LLM4Rocq/rocqet-search)](LICENSE)
[![Live demo](https://img.shields.io/badge/demo-rocqet.vercel.app-4f46e5)](https://rocqet.vercel.app)

Semantic search over Rocq/Coq libraries. Describe a lemma in plain English —
Rocqet finds it, even if you don't know its name.

`.v` files → extract → enrich → embed → Qdrant → FastAPI → Next.js UI.

Covers stdlib, MathComp, MathComp-Analysis, and GeoCoq (44k+ declarations).
Search quality comes mostly from attaching a natural-language description to
each declaration before embedding — see [SEARCH.md](SEARCH.md) for how that
works.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[local,dev]"
cd web && npm install && cd ..
```

## Try it offline (no network, no API keys)

```bash
./scripts/build_index.sh
ROCQET_EMBEDDER=hash .venv/bin/uvicorn rocqet.api:app --reload --port 8000   # terminal 1
cd web && npm run dev                                                        # terminal 2
```

Open `localhost:3000` and search "commutativity of addition". This uses a
small seed corpus and a lexical hash embedder just to prove the stack works —
see [SEARCH.md](SEARCH.md) for real embedders.

## Index the real libraries

```bash
./scripts/build_dataset.sh          # fetch + extract + enrich -> deploy/declarations.enriched.jsonl
./scripts/build_index.sh            # or index_cloud.sh for managed Qdrant
```

Details, including the prebuilt dataset download, in [docs/DATA.md](docs/DATA.md).

## API

```
GET /search?q=list+append+associativity&lib=stdlib&limit=5
GET /stats
GET /health
```

Full parameters and response shape in [SEARCH.md](SEARCH.md).

## MCP server

Rocqet ships an [MCP](https://modelcontextprotocol.io) server so agents (Claude
Code, Claude Desktop, ...) can search by meaning as a tool.

```bash
pip install -e ".[mcp]"
ROCQET_API_URL=https://rocqet-api.onrender.com rocqet-mcp
```

```bash
claude mcp add rocqet --env ROCQET_API_URL=https://rocqet-api.onrender.com -- rocqet-mcp
```

## Project layout

```
rocqet/     extract, enrich, embed, serve, MCP server (rocqet/schema.py has the canonical shape)
web/        Next.js UI
scripts/    dataset build, indexing, eval helpers
fixtures/   offline demo corpus
docs/       dataset, fine-tuning
```

## More docs

- [SEARCH.md](SEARCH.md) — how retrieval works, embedders, config
- [docs/DATA.md](docs/DATA.md) — getting/building the dataset
- [DEPLOY.md](DEPLOY.md) — hosting (Railway/Render API + Vercel UI)
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, PR checklist

## License

Apache 2.0 for Rocqet's own code — see [LICENSE](LICENSE). The indexed
dataset embeds text from upstream libraries under their own licenses
(LGPL, CeCILL-B) — see [NOTICE.md](NOTICE.md) before redistributing it.
