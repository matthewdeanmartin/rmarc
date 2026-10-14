.PHONY: dev test test-coverage lint lint-ruff lint-pylint lint-mypy lint-pyright lint-pyrefly \
        lint-rust rust-test format format-check build build-release build-wheels clean all ci check-all claude \
        fast fast-uninstall bench bench-contest bench-all perf

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
	uv run pytest

## Run tests with coverage measurement and report.
test-coverage:
	uv run coverage run -m pytest test_pymarc
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
lint: lint-ruff lint-pylint lint-mypy lint-pyright lint-pyrefly lint-rust

## ruff: fast lint (pymarc CI floor).
lint-ruff:
	uv run ruff check python/rmarc
 	# test_pymarc

## pylint: deeper static analysis.
lint-pylint:
	uv run pylint python/rmarc

## mypy: check annotated APIs and unannotated function bodies.
lint-mypy:
	uv run mypy python/rmarc

## pyright: Microsoft type checker (pymarc CI floor).
lint-pyright:
	uv run pyright python/rmarc

## Pyrefly: independent type checking.
lint-pyrefly:
	uv run pyrefly check

# ── Formatting ────────────────────────────────────────────────────────────────

## Auto-format with ruff (pymarc CI floor).
format:
	uv run ruff format python/rmarc test_pymarc

## Check formatting without modifying files (CI mode).
format-check:
	uv run ruff format --check --diff python/rmarc test_pymarc

# ── Building & packaging ──────────────────────────────────────────────────────

## Build a debug wheel.
build: check-examples
	uv run maturin build

## Build a release wheel (optimised).
build-release: check-examples
	uv run maturin build --release

## Build platform wheels for the current host via cibuildwheel.
build-wheels:
	uv run cibuildwheel --output-dir wheelhouse

# ── CI pipeline (mirrors pymarc .gitlab-ci.yml floor + extras) ────────────────

## Full CI sequence: lint → format-check → rust-test → test-coverage.
ci: check-examples lint-ruff format-check lint-mypy lint-pyrefly lint-pyright lint-rust rust-test test-coverage

## Full quality gate including pylint and mypy on top of CI floor.
all: check-examples lint format-check rust-test test-coverage

## Format everything, then run every check exactly as CI does. Run this before pushing.
check-all: check-examples
	cargo fmt
	uv run ruff format python/rmarc test_pymarc
	cargo fmt --check
	uv run ruff format --check --diff python/rmarc
	uv run ruff check python/rmarc
	uv run mypy python/rmarc
	uv run pyrefly check
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

## Run large corpus comparison benchmarks derived from contest.py.
bench-contest:
	uv run pytest bench/bench_contest.py --benchmark-only -v

## Run all benchmarks.
bench-all:
	uv run --group benchmark pytest bench/ --benchmark-only -v

## Run 3-way performance deathmatch: rmarc vs pymarc vs mrrc.
perf:
	uv run --group benchmark pytest bench/bench_deathmatch.py --benchmark-only --benchmark-group-by=group -v

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

# ── Dogfooding targets (independent, not wired into check) ───────────────────

.PHONY: version-check
version-check:
	@uv run jiggle_version check

.PHONY: dev-status
dev-status:
	@uv run troml-dev-status validate .

.PHONY: prerelease-check
prerelease-check: version-check dev-status
	@echo "Pre-release checks passed."

.PHONY: dont-be-lazy
dont-be-lazy:
	@uv run dont_be_lazy --root . --no-color summary
	@uv run dont_be_lazy --root . --no-color scan rmarc --no-config-suppressions || true

.PHONY: pydoc-docs
pydoc-docs:
	@uv run pydoc_fork rmarc -o ./pydoc/

# `bench` is also a directory in this repo; without .PHONY make can call the target up to date and skip it.
.PHONY: bench

# Local timings only: intentionally excluded from ci, all and check-all.
.PHONY: perf-baseline perf-check check-examples
PERF_OPTIONS ?=
PERF_BASELINE ?=
perf-baseline:
	uv run pytest bench/regression --benchmark-only --benchmark-storage=target/performance --benchmark-save=baseline $(PERF_OPTIONS)

perf-check:
	uv run pytest bench/regression --benchmark-only --benchmark-storage=target/performance --benchmark-compare$(if $(PERF_BASELINE),=$(PERF_BASELINE),) --benchmark-compare-fail=median:15% $(PERF_OPTIONS)

# Consumer examples are checked and executed, without launching the GUI.
check-examples:
	uv run mypy --strict --follow-imports=silent examples/book_catalog.py
	uv run pyright examples/book_catalog.py
	uv run pyrefly check examples/book_catalog.py
	uv run pytest test_pymarc/test_typed_examples.py -q

# Validate release notes without modifying the environment or checkout.
.PHONY: changelog-check
changelog-check:
	uv run --frozen --no-sync kaclm validate --strict
