# Global Risk Observatory

A live world-risk visualization built for the **Kaggle Gemma 4 for Good** hackathon. An interactive Earth that renders as a 3D sphere and theatrically "opens up" into a flat 2D map, while continuously ingesting world news and reasoning about emerging risks.

## Two-Gemma architecture

- **Gemma 4 E4B** — *standard ingestion.* Per news article: extract title, summary, primary_location, country_iso, lat/lon, category, severity, key_entities, sentiment. Fast, parallel, JSON-schema enforced.
- **Gemma 4 26B A4B MoE** — *reasoning.* Periodically clusters related events and writes a markdown **World Risk Brief** with hotspots, escalation signals, and regions to watch.

## Stack

| Layer | Choice |
|---|---|
| LLM serving | Ollama (both models resident, `OLLAMA_MAX_LOADED_MODELS=2`) |
| Backend | FastAPI + asyncio + SSE |
| Storage | SQLite + R-tree (single file) |
| News sources | GDELT 2.0 DOC API + curated RSS (Reuters / AP / BBC / Al Jazeera) |
| Geocoding | E4B extraction → local GeoNames cities15000 (offline) |
| Frontend | Next.js 16 + react-three-fiber + drei + Zustand + Tailwind v4 |
| Globe morph | Custom GLSL vertex shader (sphere ↔ equirectangular plane lerp) |

## Quickstart

```bash
# 0. Ollama: pull both models, set keep-alive
ollama pull gemma4:e4b
ollama pull gemma4:26b-a4b
OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_KEEP_ALIVE=-1 ollama serve

# 1. Backend
cd backend
make sync                       # install Python deps (uv)
make geonames                   # download GeoNames cities15000.txt
make textures                   # download Blue Marble daymap into ../data/textures
make api                        # uvicorn on :8000

# 2. Frontend (in another terminal)
cd frontend
pnpm install
pnpm dev                        # next on :3000
```

Press **F** in the UI to peel the globe open into a flat map. Click **Run reasoning** to ask the 26B for a fresh World Brief.

## Hardware

Designed for **32 GB+ Apple Silicon**. Both models resident:
- `gemma4:e4b` Q4 ≈ 3 GB
- `gemma4:26b-a4b` Q4_K_M ≈ 15.6 GB
- KV cache @ 32K context ≈ 3-4 GB
- App + browser headroom ≈ 8-10 GB

On 24 GB, lazy-load the 26B and cap context to 8K. On 16 GB, route 26B to a remote inference endpoint.
