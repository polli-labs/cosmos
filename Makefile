SHELL := /bin/bash
UV ?= uv
VENV := .venv

.PHONY: help
help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## / — /' | sort

# ——— Environment ———
.PHONY: dev-setup
dev-setup: ## Sync project + dev dependencies into .venv
	$(UV) sync --extra dev

.PHONY: docs-setup
docs-setup: ## Sync project + dev + docs dependencies into .venv
	$(UV) sync --extra dev --extra docs

.PHONY: venv
venv: ## Create virtualenv only
	$(UV) venv $(VENV)

.PHONY: install
install: dev-setup ## Alias: sync dev dependencies

.PHONY: uv-sync
uv-sync: dev-setup ## Alias: sync dev dependencies

.PHONY: clean
clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info

# ——— Quality ———
.PHONY: check
check: ## Canonical local quality gate (format-check, lint, ty, pytest)
	$(UV) run ruff format --check .
	$(UV) run ruff check .
	$(UV) run ty check
	$(UV) run pytest -q

.PHONY: fmt
fmt: ## Auto-format (ruff)
	$(UV) run ruff format .

.PHONY: lint
lint: ## Lint (ruff)
	$(UV) run ruff check .

.PHONY: typecheck
typecheck: ## Type-check (ty)
	$(UV) run ty check

# ——— Tests ———
.PHONY: test
test: ## Run tests
	$(UV) run pytest -q

# ——— Run ———
.PHONY: cosmos
cosmos: ## Launch cosmos CLI
	$(UV) run cosmos --help

.PHONY: squarecrop
squarecrop: ## Launch squarecrop CLI
	$(UV) run squarecrop --help

# ——— Local runs (parameterized) ———
# Usage examples:
#   make run.ingest IN=/path/raw OUT=/path/out YES=1 WINDOW=10
#   make run.crop INPUT=/path/in.mp4 OUT=_work/out JOBS=_work/job.json YES=1

.PHONY: run.ingest
run.ingest: ## Run ingest: IN=/path INput dir, OUT=/path OUTput dir, optional YES=1, WINDOW=secs, CLIP=NAME (repeat via CLIPS="A B")
	$(UV) run python -m cosmos.cli.ingest_cli run \
		$$([ -n "$(IN)" ] && echo --input-dir "$(IN)") \
		$$([ -n "$(OUT)" ] && echo --output-dir "$(OUT)") \
		$$([ -n "$(YES)" ] && echo --yes) \
		$$([ -n "$(WINDOW)" ] && echo --window "$(WINDOW)") \
		$$(for c in $(CLIPS); do echo --clip $$c; done)

.PHONY: run.crop
run.crop: ## Run squarecrop: INPUT=/path/in.mp4 OUT=/path/out JOBS=/path/jobs.json optional YES=1 DRY=1
	$(UV) run python -m cosmos.cli.crop_cli \
		$$([ -n "$(INPUT)" ] && echo --input "$(INPUT)") \
		$$([ -n "$(OUT)" ] && echo --out-dir "$(OUT)") \
		$$([ -n "$(JOBS)" ] && echo --jobs-file "$(JOBS)") \
		$$([ -n "$(YES)" ] && echo --yes) \
		$$([ -n "$(DRY)" ] && echo --dry-run)

.PHONY: run.provenance
run.provenance: ## Map provenance in a dir: DIR=/path (prints sha256 -> artifact JSON)
	$(UV) run python -m cosmos.cli.provenance_cli map $$([ -n "$(DIR)" ] && echo "$(DIR)" || echo .)
.PHONY: test-e2e-local
test-e2e-local: ## Run local E2E tests (set COSMOS_ENABLE_LOCAL_TESTS=1)
	COSMOS_ENABLE_LOCAL_TESTS=1 $(UV) run pytest -q tests/e2e_local -q

.PHONY: e2e-repro-slim
e2e-repro-slim: ## Run slim ingest reproduction (4K, 10s, balanced) local E2E
	COSMOS_ENABLE_LOCAL_TESTS=1 COSMOS_RUN_INGEST=1 $(UV) run pytest -q tests/e2e_local/test_ladybird_repro.py -q

.PHONY: e2e-repro-full
e2e-repro-full: ## Run full 9.5k reproduction (very heavy) local E2E
	COSMOS_ENABLE_LOCAL_TESTS=1 COSMOS_FULL_REPRO=1 $(UV) run pytest -q tests/e2e_local/test_ladybird_repro_full.py -q

.PHONY: e2e-repro-8k
e2e-repro-8k: ## Run 8K windowed reproduction (local-only; disabled in CI by default)
	COSMOS_ENABLE_LOCAL_TESTS=1 COSMOS_RUN_8K_REPRO=1 $(UV) run pytest -q tests/e2e_local/test_ladybird_repro_8k.py -q

.PHONY: e2e-heavy
e2e-heavy: e2e-repro-slim ## Back-compat alias for slim reproduction

.PHONY: fixtures.download
fixtures.download: ## Download large fixtures via rclone into dev/fixtures/cache
	./dev/scripts/fixtures_sync.sh download

.PHONY: fixtures.unpack
fixtures.unpack: ## Unpack raw_0H.tar.zst into cache
	./dev/scripts/fixtures_sync.sh unpack

.PHONY: fixtures.pack
fixtures.pack: ## Pack local ladybird raw/0H and copy manifest/outputs into cache
	./dev/scripts/fixtures_sync.sh pack

.PHONY: fixtures.upload
fixtures.upload: ## Upload packed fixtures to Backblaze B2 (public-0-master)
	./dev/scripts/fixtures_sync.sh upload

.PHONY: fixtures.pack-outputs
fixtures.pack-outputs: ## Copy known-good outputs CLIP1/CLIP2 into cache
	./dev/scripts/fixtures_sync.sh pack-outputs

.PHONY: fixtures.upload-outputs
fixtures.upload-outputs: ## Upload known-good outputs (optional; large)
	./dev/scripts/fixtures_sync.sh upload-outputs

.PHONY: fixtures.download-outputs
fixtures.download-outputs: ## Download known-good outputs into cache (optional)
	./dev/scripts/fixtures_sync.sh download-outputs

.PHONY: fixtures.pack-crop-outputs
fixtures.pack-crop-outputs: ## Copy selected squarecrop outputs into cache (optional)
	./dev/scripts/fixtures_sync.sh pack-crop-outputs

.PHONY: fixtures.upload-crop-outputs
fixtures.upload-crop-outputs: ## Upload selected squarecrop outputs into remote (optional)
	./dev/scripts/fixtures_sync.sh upload-crop-outputs

.PHONY: fixtures.download-crop-outputs
fixtures.download-crop-outputs: ## Download selected squarecrop outputs into cache (optional)
	./dev/scripts/fixtures_sync.sh download-crop-outputs
