# Deploying Rocqet

Two pieces: the API (FastAPI + fastembed) on Railway or Render, and the UI
(Next.js) on Vercel. Vectors live in a managed Qdrant cluster, not in the API
container — keeps it small and low-RAM.

## 0. Qdrant (one-time)

Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io), then index it:

```bash
export QDRANT_URL="https://xxxx.cloud.qdrant.io:6333"
export QDRANT_API_KEY="..."
./scripts/index_cloud.sh
```

## 1. API

**Railway:** New Project → Deploy from GitHub → this repo. Reads `railway.toml`,
builds `Dockerfile.api`. Set `QDRANT_URL` / `QDRANT_API_KEY` in Variables, then
Settings → Networking → Generate Domain.

**Render:** New → Blueprint → this repo. Reads `render.yaml`. Same env vars,
set in the dashboard. Free tier sleeps after ~15 min idle.

Either way, verify with `curl https://<domain>/health`.

## 2. UI → Vercel

Import the repo, Root Directory = `web`, set:

```
NEXT_PUBLIC_API_URL = https://<your-api-domain>
```

`NEXT_PUBLIC_API_URL` is baked at build time — redeploy after changing it.

## 3. Refreshing the index

```bash
./scripts/build_dataset.sh
./scripts/index_cloud.sh
```

Point ids are deterministic, so this upserts in place with no downtime.

## Notes

- The embedder must match at index and serve time (`ROCQET_EMBEDDER=fastembed`
  in production).
- Set `CORS_ORIGINS` to your Vercel URL to stop allowing `*`.
