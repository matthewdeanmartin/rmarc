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

# Build optimized (for benchmarking)
uv run maturin develop --release

# Run tests
uv run pytest test_pymarc/
```

### Optional fast backends (dev)

```bash
make fast          # install orjson + lxml into the dev venv
make fast-uninstall  # remove them
```

### Build a wheel

```bash
uv run maturin build --release
```

The wheel will be in `target/wheels/`.

### Benchmarks

```bash
# Generate benchmark data (once)
uv run python bench/generate_data.py

# Run core MARC benchmarks
uv run pytest bench/ --benchmark-only

# Run JSON/XML serialization benchmarks
make bench

# Run all benchmarks
make bench-all

# Save and compare
uv run pytest bench/ --benchmark-save=before
# ... make changes ...
uv run pytest bench/ --benchmark-save=after
uv run pytest bench/ --benchmark-compare
```

---

## Architecture

```
python/rmarc/           # Python API layer (pymarc-compatible)
├── _compat.py          # Optional fast-backend detection (orjson, lxml)
├── record.py           # Record class, decode_marc, as_marc
├── field.py            # Field, Subfield, Indicators
├── reader.py           # MARCReader, JSONReader, MARCMakerReader
├── writer.py           # MARCWriter, JSONWriter, TextWriter, XMLWriter
├── marcjson.py         # JSONHandler, parse_json_to_array
├── marcxml.py          # XmlHandler, parse_xml_to_array, record_to_xml
├── marc8.py            # MARC-8 converter (dispatches to Rust)
└── _rmarc.pyd          # Rust extension

src/                    # Rust core (PyO3)
├── lib.rs              # Module definition
├── marc_codec.rs       # Binary MARC21 codec
├── marc8.rs            # MARC-8 to Unicode converter
└── marc8_mapping.rs    # MARC-8 character set tables (phf)
```

---

## Compatibility

rmarc aims for full API compatibility with pymarc. The test suite includes all
pymarc tests. If you find a compatibility issue, please open an issue.
