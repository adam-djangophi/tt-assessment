.PHONY: dev setup deps uv api up hub db fix test clear

# One command: install deps, generate the API client, then run API + UI together
#
# How it chains (prerequisites run first, left to right, depth-first):
#   dev
#   └─ setup
#      ├─ deps
#      │  ├─ uv     install uv via Homebrew if missing
#      │  └─        yarn install + uv sync (apps/api)
#      └─ api       generate libs/api-client from the API's OpenAPI spec
#   then dev's own recipe runs `make -j2 up hub`, starting the long-running
#   API (docker, :8000) and UI (nx, :4200) in parallel; Ctrl-C stops both.
dev: setup
	$(MAKE) -j2 up hub

setup: deps api

deps: uv
	yarn install
	cd apps/api && uv sync

uv:
	@command -v uv >/dev/null 2>&1 || brew install uv

up:
	docker compose -f infra/docker-compose.yml up --build --watch   # API on :8000

hub:
	yarn nx serve hub                                        # UI on :4200

api:
	yarn api-client:generate

db:
	docker compose -f infra/docker-compose.yml exec postgres psql -U hub -d hub   # psql shell (\q to quit)

fix:
	cd apps/api && uv run ruff check --fix app tests && uv run ruff format app tests   # autofix lint + format

test:
	cd apps/api && uv run pytest

# Drop every table, recreate the schema and reload contracts/seed-data.json (API container must be up)
clear:
	docker compose -f infra/docker-compose.yml exec -T api python -c "\
	from app.db.base import Base, SessionLocal, engine; \
	from app.seed import seed_database; \
	Base.metadata.drop_all(engine); Base.metadata.create_all(engine); \
	db = SessionLocal(); print('reseeded' if seed_database(db) else 'seed skipped'); db.close()"
