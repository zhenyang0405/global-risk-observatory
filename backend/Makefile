# macOS quirk: uv marks .venv with UF_HIDDEN; CPython 3.12+ then refuses to
# process .pth files inside it, breaking editable installs. Strip the flag
# before every uv invocation.

UNHIDE := chflags -R nohidden .venv 2>/dev/null || true

API_PORT ?= 8000

.PHONY: sync api ingest brief seed geonames textures shell schema

sync:
	uv sync
	$(UNHIDE)

api:
	@$(UNHIDE)
	@uv run uvicorn risk_observatory.api.app:app --reload --reload-dir src --port $(API_PORT)

ingest:
	@$(UNHIDE)
	@uv run python -m risk_observatory.cli ingest $(if $(TEXT),"$(TEXT)",)

brief:
	@$(UNHIDE)
	@uv run python -m risk_observatory.cli brief

seed:
	@$(UNHIDE)
	@uv run python -m risk_observatory.cli seed

geonames:
	@$(UNHIDE)
	@uv run python scripts/download_geonames.py

textures:
	@mkdir -p ../data/textures ../frontend/public/textures
	@echo "Download Blue Marble: https://visibleearth.nasa.gov/images/73580/january-blue-marble-next-generation-w-topography"
	@echo "Place world.topo.bathy.200401.3x5400x2700.jpg as ../data/textures/earth-day.jpg"
	@echo "Then: cp ../data/textures/earth-day.jpg ../frontend/public/textures/"

shell:
	@$(UNHIDE)
	@uv run python

schema:
	@cat src/risk_observatory/store/schema.sql
