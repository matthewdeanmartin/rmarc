.PHONY: test lint format format-check run run-gui clean

# ── Testing ──────────────────────────────────────────────────────────────────

## Run sample_app tests.
test:
	cd .. && uv run pytest sample_src/sample_app/tests -v

## Run sample_app tests with coverage.
test-coverage:
	cd .. && uv run pytest sample_src/sample_app/tests -v --cov=sample_src/sample_app/sample_app --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────────────────

## Lint sample_app source.
lint:
	cd .. && uv run ruff check sample_src/sample_app/sample_app sample_src/sample_app/tests

## Type-check sample_app source.
lint-pyright:
	cd .. && uv run pyright sample_src/sample_app/sample_app

# ── Formatting ───────────────────────────────────────────────────────────────

## Auto-format sample_app source.
format:
	cd .. && uv run ruff format sample_src/sample_app/sample_app sample_src/sample_app/tests

## Check formatting without modifying files.
format-check:
	cd .. && uv run ruff format --check --diff sample_src/sample_app/sample_app sample_src/sample_app/tests

# ── Running ──────────────────────────────────────────────────────────────────

## Run the CLI.
run:
	cd .. && uv run --package sample-app python -m sample_app $(ARGS)

## Run the tkinter GUI.
run-gui:
	cd .. && uv run --package sample-app python -m sample_app.ui

# ── Housekeeping ─────────────────────────────────────────────────────────────

## Remove build artefacts.
clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
