# Global Risk Observatory — Project Notes

Live world-risk Earth visualization for the **Kaggle Gemma 4 for Good** hackathon. A 3D Earth sphere that theatrically "opens up" into a flat 2D map, while continuously ingesting world news and reasoning about emerging risks.

## Architecture (one screen)

```
┌─────────────────────────── Backend (FastAPI) ───────────────────────────┐
│                                                                          │
│  ┌── ingestion loop (every 15min / 30min) ────────────────────────────┐  │
│  │   GDELT 2.0 DOC API ──┐                                            │  │
│  │   curated RSS    ─────┴── classify_many(articles)                  │  │
│  │                                ├── Semaphore(4) ──▶ gemma4:e4b     │  │
│  │                                │   IngestedEvent (JSON-schema)     │  │
│  │                                ├── geocode gap-fill (GeoNames)     │  │
│  │                                └── insert + SSE.publish(event)     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌── reasoning loop (every 10min OR POST /brief/run) ──────────────────┐ │
│  │   recent_events(120, 6h)                                            │ │
│  │     ├── clusterer.cluster()   ▶ gemma4:26b-a4b  think=True          │ │
│  │     └── briefer.write()       ▶ gemma4:26b-a4b  think=True          │ │
│  │     └── insert_brief + SSE.publish(brief)                           │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  SQLite + R-tree (data/observatory.db) — single file, no Docker dep.    │
└──────────────────────────────────────────────────────────────────────────┘
                            │
                            │  SSE: /events/stream  /brief/stream
                            ▼
┌────────────────────── Frontend (Next.js + R3F) ─────────────────────────┐
│                                                                          │
│  GlobeCanvas (R3F)                       Sidebar                        │
│    EarthMesh   ── morph shader            ModelStatusChips              │
│    Atmosphere  ── fades with morph        BriefCard (markdown)          │
│    EventMarkers — instanced, CPU-morphed  EventFeed (SSE)               │
│    EventArcs   — great-circle ↔ bezier                                  │
│    CameraRig   — orbit ↔ ortho-feel       TopBar                        │
│    Stars                                    Globe/Flat (F)              │
│                                             Category filters            │
│                                             "Run reasoning" → POST      │
└──────────────────────────────────────────────────────────────────────────┘
```

## Two-model topology

- `gemma4:e4b` (4.5B effective, 128K ctx, text+image+audio) — per-article extraction.
  `temperature=0`, JSON-schema enforced. Concurrency=4.
- `gemma4:26b-a4b` (25.2B total / 3.8B active, 256K ctx, text+image, `<|think|>`) —
  clustering + World Risk Brief. `temperature=1.0, top_p=0.95, top_k=64`, think=True.

Both kept resident: `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE=-1`.
Tested target: 32 GB unified-memory Apple Silicon. See README.md for sub-32GB paths.

## The morph (the visual centerpiece)

The user pitch: **the Earth opens up to flat.** This is a single GLSL vertex
shader (`frontend/src/components/globe/shaders.ts`) lerping each sphere vertex
toward its equirectangular plane position, controlled by uniform `uMorph ∈ [0,1]`.
A transient z-displacement "peel wave" makes the unfolding feel organic and
vanishes by `t = 0.65` so the final plane is flat.

**Critical: every layer on the surface uses the SAME morph formula.**
`frontend/src/lib/morph.ts` is the JS port; markers, arcs, and any future
overlays must read from it. If it drifts from the shader, dots float off the
surface.

## Schema lockstep (the #1 bug source)

`backend/src/risk_observatory/schemas.py` ⇔ `frontend/src/lib/types.ts`.
When you change one, change BOTH in the same commit. The `IngestedEvent`
shape is also the JSON-schema fed to Ollama's `format` parameter; mismatch
between Python and TS surfaces as silent SSE-payload-shape drift.

## Gotchas

### macOS + uv hidden venv

`uv sync` flags `.venv` with `UF_HIDDEN`; CPython 3.12+ then refuses to process
`.pth` inside hidden dirs, breaking editable installs. Always invoke via
`make` — the Makefile wraps every command with `chflags -R nohidden .venv`.

### Gemma 4 thinking mode

- `<|think|>...<|/think|>` blocks must be stripped from history on multi-turn
  re-sends. `ollama_client.strip_think()` handles this defensively even though
  Ollama's `think=True` flag normally consumes them.
- Some E4B routes that should NOT think: extractor uses `think=False` (default)
  to keep latency low. Reasoning routes use `think=True`.

### Frontend HMR + Three

`@react-three/fiber` doesn't always recover cleanly from HMR — if shader uniforms
behave weirdly after a save, hard-reload (Cmd-Shift-R). Layout changes touching
`GlobeCanvas` always need a hard reload.

### SQLite + R-tree

The R-tree virtual table requires SQLite compiled with the rtree extension —
this is included in stock CPython sqlite3 on macOS/Linux. If `events_rtree`
inserts fail, check `sqlite3.sqlite_version_info >= (3, 8, 0)`.

### GDELT polling

Public DOC API has no daily cap but throttle to ~1 req / 5s. The default
ingestion loop runs every 15 minutes (well under the soft limit). User-Agent
must be set or GDELT may return empty results.

### Memory budget (32GB M-series)

| Item | Approx |
|---|---|
| gemma4:e4b Q4 | 3.0 GB |
| gemma4:26b-a4b Q4_K_M | 15.6 GB |
| KV cache @ 32K ctx (both) | 3-4 GB |
| App + browser | 4 GB |
| **Total resident** | **~26 GB** |

On 24GB: lower context to 8K and drop one of the models when idle.

## Development quickstart

```bash
# Terminal 0 — Ollama (once)
OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_KEEP_ALIVE=-1 ollama serve
ollama pull gemma4:e4b
ollama pull gemma4:26b-a4b

# Terminal 1 — Backend
cd backend
make sync
make geonames                # one-time download of cities15000.txt
make api                     # uvicorn :8000

# Terminal 2 — Frontend
cd frontend
pnpm install                 # or npm/yarn
pnpm dev                     # next :3000

# Terminal 3 — Demo seed (when offline / no GDELT)
cd backend
make seed                    # loads scenarios/gdelt_fixture.json via E4B
```

Then open http://localhost:3000 and press **F**.

## Demo flow (90 s pitch)

1. **0:00-0:15** — Slow-rotating sphere; markers populating from seed/live.
2. **0:15-0:30** — New dot pulses; sidebar logs the classification + latency.
3. **0:30-0:50** — Click a marker → popup with summary + entities.
4. **0:50-1:10** — Press **F**. Sphere peels open into flat map in 1.5 s.
5. **1:10-1:25** — Click "Run reasoning". Violet pulse → 26B brief streams in.
6. **1:25-1:30** — Press **F** again — flat folds back into sphere.

## Stretch (skip if cutting scope)

- Audio ingestion (E4B audio modality + BBC World Service snippets)
- Historical playback slider (24 h replay at 60×)
- Region-zoom mode (continent-scale flat sub-views)

## Repo map

```
backend/
  src/risk_observatory/
    config.py              env-driven Settings
    schemas.py             Pydantic; ⇔ frontend/src/lib/types.ts
    models.py              role → model id registry
    ollama_client.py       JSON-schema chat wrapper, Gemma-4 tweaks
    geocoding/gazetteer.py GeoNames cities15000 in-memory + fuzzy
    sources/
      gdelt.py             DOC API + CAMEO theme filter
      rss.py               feedparser, curated feeds
    ingestion/
      extractor.py         E4B per-article, Semaphore-bounded
      loop.py              15-min / 30-min schedulers
    reasoning/
      clusterer.py         26B cluster pass
      briefer.py           26B World Risk Brief
      loop.py              10-min + on-demand
    store/
      schema.sql           sqlite + r-tree
      connection.py        lazy-init connection
      repository.py        all SQL lives here
    api/
      app.py               FastAPI factory + lifespan
      events.py            SSE pub/sub
      routes_events.py     /events, /events/stream
      routes_brief.py      /brief/latest, /brief/run, /brief/stream
      routes_meta.py       /healthz, /models, /stats
    cli.py                 make ingest / brief / seed
  prompts/
    ingest.md  cluster.md  brief.md
  scripts/download_geonames.py
  Makefile  pyproject.toml  .env.example

frontend/
  src/
    app/page.tsx           composition root
    lib/
      types.ts             ⇔ backend schemas.py
      morph.ts             CPU port of GLSL vertex shader
      projection.ts        great-circle samplers
      sse.ts  api.ts
    store/useObservatoryStore.ts
    hooks/
      useEventsStream.ts  useBriefStream.ts
    components/
      globe/
        shaders.ts         vertex + fragment for earth + atmosphere
        EarthMesh.tsx      sphere↔plane morph mesh
        EventMarkers.tsx   instanced; CPU-morphed positions
        EventArcs.tsx      morphed line segments
        Atmosphere.tsx     back-faced fresnel glow
        CameraRig.tsx      orbit→ortho tween
        Stars.tsx
        GlobeCanvas.tsx
      ui/
        TopBar.tsx         globe/flat, filters, run reasoning
        Sidebar.tsx        feed + brief + model chips
        EventFeed.tsx
        BriefCard.tsx
        ModelStatusChip.tsx
        EventDetail.tsx
  package.json  tsconfig.json  next.config.ts
```
