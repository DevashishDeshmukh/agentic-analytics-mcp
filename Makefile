COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env
CONFIG ?= rag

.PHONY: help setup up down reset seed ingest bootstrap test test-unit lint check-gold eval eval-all results ask serve-warehouse serve-knowledge tool tools

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup:           ## Install deps and create .env
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env - add OPENAI_API_KEY")

up:              ## Start Postgres + pgvector
	$(COMPOSE) up -d --wait

down:            ## Stop Postgres (keeps data)
	$(COMPOSE) down

reset:           ## Stop Postgres and delete its data volume
	$(COMPOSE) down -v

seed:            ## Generate and load synthetic warehouse data
	uv run python data/seed/generate.py

ingest:          ## Embed docs into the knowledge index
	uv run python -m ingestion.ingest_docs

bootstrap: setup up seed ingest  ## Everything from a fresh clone

test:            ## All tests (needs Postgres running)
	uv run pytest -q

test-unit:       ## Tests that need no database
	uv run pytest -q -m "not db"

lint:            ## Ruff
	uv run ruff check .

check-gold:      ## Verify every gold SQL query runs
	uv run python -m evals.runners.run_eval --check-gold

eval:            ## Run eval suite: make eval CONFIG=baseline|rag
	uv run python -m evals.runners.run_eval --config $(CONFIG)
	uv run python scripts/make_results_table.py

eval-all:        ## Run every config in the ablation
	$(MAKE) eval CONFIG=baseline
	$(MAKE) eval CONFIG=rag

results:         ## Regenerate README results table
	uv run python scripts/make_results_table.py

ask:             ## Ask a question: make ask Q="What was net revenue in 2024?"
	uv run python -m agent "$(Q)" --config $(CONFIG)

serve-warehouse: ## Run warehouse-mcp over HTTP on :8001
	uv run python -m servers.warehouse_mcp --transport http --port 8001

serve-knowledge: ## Run knowledge-mcp over HTTP on :8002
	uv run python -m servers.knowledge_mcp --transport http --port 8002

tool:            ## Call an MCP tool: make tool S=warehouse T=run_query A='{"sql":"SELECT 1"}'
	uv run python scripts/mcp_call.py $(S) $(T) '$(A)'

tools:           ## List every MCP tool
	uv run python scripts/mcp_call.py --list
