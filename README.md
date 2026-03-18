# rmarc

A pymarc-compatible MARC21 record library with a Rust core for high performance.

## Performance

rmarc is a drop-in replacement for [pymarc](https://gitlab.com/pymarc/pymarc)
with critical paths implemented in Rust via PyO3. Pure Python fallbacks are
included for platforms where the Rust extension can't be built.

### Benchmarks (vs pure Python baseline)

Measured on the same machine, same test data, same API. The "baseline" column is
rmarc with Rust disabled (pure Python, equivalent to pymarc performance).

| Benchmark                      | Baseline   | Rustified | Speedup   |
|--------------------------------|------------|-----------|-----------|
| Decode single record           | 239 us     | 39 us     | **6.1x**  |
| Round-trip (decode + encode)   | 258 us     | 62 us     | **4.2x**  |
| Read + iterate 10 records      | 1,795 us   | 413 us    | **4.3x**  |
| MARC-8 to Unicode (1515 lines) | 13,714 us  | 1,349 us  | **10.2x** |
| Read + iterate 1,000 records   | 266,589 us | 51,000 us | **5.2x**  |
| Bulk read 100,000 records      | 18,337 ms  | 4,279 ms  | **4.3x**  |

### What's in Rust

- **Binary MARC21 codec** (`decode_marc_raw`, `encode_marc_raw`) — parses record
  bytes, splits directory entries, extracts fields/subfields, and handles UTF-8
  and MARC-8 encoding conversion all in one Rust call.
- **MARC-8 to Unicode converter** (`marc8_to_unicode_rs`) — stateful byte-level
  conversion with escape-sequence codeset switching, multibyte CJK support,
  combining character reordering, and NFC normalization. Uses compile-time
  perfect hash maps (`phf`) for the 12 MARC-8 character sets.

### What stays in Python

- Field/Record/Subfield object construction (the API layer)
- XML parsing/serialization (dominated by `xml.etree`)
- JSON handling (already C-accelerated in CPython)
- Convenience properties (title, isbn, author, etc.)
- Unknown encodings (cp1251, etc.) — returned as raw bytes for Python's codec system

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
uv run pytest tests/
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

# Run benchmarks
uv run pytest bench/ --benchmark-only

# Save and compare
uv run pytest bench/ --benchmark-save=before
# ... make changes ...
uv run pytest bench/ --benchmark-save=after
uv run pytest bench/ --benchmark-compare
```

## Architecture

```
python/rmarc/           # Python API layer (pymarc-compatible)
├── record.py           # Record class, decode_marc, as_marc
├── field.py            # Field, Subfield, Indicators
├── reader.py           # MARCReader, JSONReader, MARCMakerReader
├── writer.py           # MARCWriter, JSONWriter, TextWriter, XMLWriter
├── marc8.py            # MARC-8 converter (dispatches to Rust)
└── _rmarc.pyd          # Rust extension

src/                    # Rust core (PyO3)
├── lib.rs              # Module definition
├── marc_codec.rs       # Binary MARC21 codec
├── marc8.rs            # MARC-8 to Unicode converter
└── marc8_mapping.rs    # MARC-8 character set tables (phf)
```

## Compatibility

rmarc aims for full API compatibility with pymarc. The test suite includes all
pymarc tests. If you find a compatibility issue, please open an issue.
