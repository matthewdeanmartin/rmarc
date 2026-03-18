.PHONY: dev test test-coverage lint lint-ruff lint-pylint lint-mypy lint-pyright \
        lint-rust rust-test format format-check build build-release clean all ci check-all claude \
        fast fast-uninstall bench bench-all

# ── Developer workflow ────────────────────────────────────────────────────────

## Build and install the Rust extension in-place (editable dev mode).
dev:
	uv run maturin develop

## Rebuild after Rust changes without reinstalling Python deps.
rebuild:
	uv run maturin develop --skip-install

## Install optional fast serialization backends (orjson + lxml).
fast:
	uv pip install "orjson>=3.9" "lxml>=5.0"

## Uninstall optional fast serialization backends.
fast-uninstall:
	uv pip uninstall orjson lxml

# ── Testing ───────────────────────────────────────────────────────────────────

## Run all tests (Rust + Python).
test: rust-test
	uv run python -m unittest discover -s test_pymarc -v
	uv run pytest

## Run tests with coverage measurement and report.
test-coverage:
	# This is messed up. Needs to c
	uv run coverage run -m unittest discover -s test_pymarc
	uv run coverage xml
	uv run coverage report

# ── Rust ──────────────────────────────────────────────────────────────────────

## Run Rust unit tests.
rust-test:
	cargo test

## Run Rust linting (fmt check + clippy).
lint-rust:
	cargo fmt --check
	cargo clippy -- -D warnings

# ── Linting ───────────────────────────────────────────────────────────────────

## Run all linters (Python + Rust).
lint: lint-ruff lint-pylint lint-mypy lint-pyright lint-rust

## ruff: fast lint (pymarc CI floor).
lint-ruff:
	uv run ruff check python/rmarc
 	# test_pymarc

## pylint: deeper static analysis.
lint-pylint:
	uv run pylint python/rmarc

## mypy: strict type checking.
lint-mypy:
	uv run mypy python/rmarc

## pyright: Microsoft type checker (pymarc CI floor).
lint-pyright:
	uv run pyright python/rmarc

# ── Formatting ────────────────────────────────────────────────────────────────

## Auto-format with ruff (pymarc CI floor).
format:
	uv run ruff format python/rmarc test_pymarc

## Check formatting without modifying files (CI mode).
format-check:
	uv run ruff format --check --diff python/rmarc test_pymarc

# ── Building & packaging ──────────────────────────────────────────────────────

## Build a debug wheel.
build:
	uv run maturin build

## Build a release wheel (optimised).
build-release:
	uv run maturin build --release

# ── CI pipeline (mirrors pymarc .gitlab-ci.yml floor + extras) ────────────────

## Full CI sequence: lint → format-check → rust-test → test-coverage.
ci: lint-ruff format-check lint-pyright lint-rust rust-test test-coverage

## Full quality gate including pylint and mypy on top of CI floor.
all: lint format-check rust-test test-coverage

## Format everything, then run every check exactly as CI does. Run this before pushing.
check-all:
	cargo fmt
	uv run ruff format python/rmarc test_pymarc
	cargo fmt --check
	uv run ruff format --check --diff python/rmarc
	uv run ruff check python/rmarc
	uv run pyright python/rmarc
	cargo clippy -- -D warnings
	cargo test
	uv run pytest test_pymarc/ \
		--cov=python/rmarc \
		--cov-report=xml \
		--cov-report=term-missing \
		-v

## Run JSON/XML serialization benchmarks.
bench:
	uv run pytest bench/bench_json_xml.py --benchmark-only -v

## Run all benchmarks.
bench-all:
	uv run pytest bench/ --benchmark-only -v

# ── Housekeeping ──────────────────────────────────────────────────────────────

## Remove build artefacts.
clean:
	cargo clean
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache coverage.xml .coverage

# ── Meta ──────────────────────────────────────────────────────────────────────

claude:
	claude --allow-dangerously-skip-permissions
