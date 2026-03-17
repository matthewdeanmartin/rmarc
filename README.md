# rmarc

A pymarc-compatible MARC record library with a Rust core.

## Developer Quickstart

### Prerequisites

- Rust (stable) — `rustup` recommended
- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

### Setup

```bash
# Install dependencies including maturin
uv sync

# Build and install in editable/dev mode (rebuilds Rust on each invoke)
uv run maturin develop

# Run tests
uv run pytest tests/
```

### Build a wheel

```bash
uv run maturin build --release
```

The wheel will be in `target/wheels/`.

### Install the wheel in a clean environment

```bash
pip install target/wheels/rmarc-*.whl
python -c "import rmarc; print(rmarc.__version__)"
```

## Known Limitations (Phase 1)

- `MarcRecord` is a stub with no real parsing logic.
- Phase 2 will implement full MARC21 parsing compatible with pymarc's API.
