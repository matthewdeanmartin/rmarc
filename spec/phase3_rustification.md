# Phase 3: Rustification Plan

## Current State (End of Phase 2)

We have a fully working pymarc-compatible Python library (`rmarc`) that passes all 171
pymarc tests. The architecture is:

```
python/rmarc/
├── __init__.py          # re-exports everything
├── constants.py         # LEADER_LEN, SUBFIELD_INDICATOR, etc.
├── exceptions.py        # 14 exception types
├── leader.py            # Leader class
├── field.py             # Field, Subfield, Indicators, RawField
├── record.py            # Record, decode_marc, as_marc, convenience props
├── reader.py            # MARCReader, JSONReader, MARCMakerReader
├── writer.py            # MARCWriter, JSONWriter, TextWriter, XMLWriter
├── marc8.py             # MARC8ToUnicode, marc8_to_unicode
├── marc8_mapping.py     # ~17K lines of character mapping data
├── marcxml.py           # XML parse/serialize
├── marcjson.py          # JSON parse/serialize
└── _rmarc.pyd           # Rust extension (currently: version() only)
```

Everything is pure Python except the stub `_rmarc` extension. The goal of Phase 3 is
to move performance-critical code into Rust while keeping the Python API unchanged.

---

## Guiding Principles

1. **Measure first.** Every Rust migration must show a measurable speedup in the
   benchmark suite before it replaces the Python path.
2. **Incremental.** Each Rust component is optional — the Python fallback stays until
   the Rust version is proven correct and faster.
3. **No API changes.** The Python-facing interface is frozen. Rust is an implementation
   detail invisible to users.
4. **Test parity.** All 171 existing tests must continue to pass at every step. Rust
   unit tests are additive.

---

## Where Rust Helps (and Where It Doesn't)

### High-value targets (CPU-bound, called millions of times)

| Component | Why it's hot | Expected speedup |
|---|---|---|
| `decode_marc()` | Parses binary MARC: byte slicing, directory parsing, field extraction. Called once per record, but does a lot of byte-level work. | 5-20x |
| `as_marc()` | Serializes to binary MARC: builds directory, encodes fields, computes lengths. Mirror of decode. | 5-20x |
| `marc8_to_unicode()` | Stateful byte-by-byte character conversion with codeset switching and combining character handling. | 10-50x |
| `MARC8ToUnicode.translate()` | Same as above — the inner loop is the bottleneck for MARC-8 files. | 10-50x |
| Field `as_marc()` | Encodes a single field to bytes. Called once per field per record. | 3-10x |

### Medium-value targets (worth doing after the hot paths)

| Component | Notes |
|---|---|
| `MARCReader.__next__()` | The read loop: read 5 bytes, parse length, read chunk, validate, call decode_marc. Moving the whole iterator to Rust avoids Python ↔ Rust boundary overhead per record. |
| Leader validation | Trivial but called on every record. Could be a zero-cost check in Rust. |
| `_sort_fields()` | Only matters for add_ordered_field/add_grouped_field with large record counts. |

### Low-value targets (leave in Python)

| Component | Why |
|---|---|
| XML parsing/serialization | Dominated by `xml.etree` / SAX parser — Rust won't help unless we replace the XML library entirely. Not worth the complexity. |
| JSON handling | `json.dumps`/`json.load` are already C-accelerated in CPython. |
| Writer classes | Thin wrappers around file I/O + `as_marc()`. The bottleneck is `as_marc()`, not the writer. |
| Convenience properties (title, isbn, etc.) | Called rarely, do trivial string work. |
| Exception classes | Pure data. No computation. |

---

## Rustification Sequence

### Step 1: Binary MARC Codec (decode_marc + as_marc)

This is the single biggest win. Most pymarc users read large `.dat` files and either
inspect them or round-trip them.

**Rust side (`src/lib.rs` or `src/marc_codec.rs`):**

```rust
/// Parse a raw MARC21 record (bytes) into structured components.
/// Returns: (leader_str, Vec<(tag, field_data)>)
/// where field_data is either control field data or (ind1, ind2, Vec<(code, value)>)
#[pyfunction]
fn decode_marc_raw(data: &[u8], to_unicode: bool, force_utf8: bool,
                   encoding: &str) -> PyResult<...> { ... }

/// Serialize structured components back to MARC21 bytes.
#[pyfunction]
fn encode_marc_raw(...) -> PyResult<Vec<u8>> { ... }
```

**Python side:** `record.py` calls `_rmarc.decode_marc_raw()` instead of the Python
`decode_marc()` loop. Field/Record construction stays in Python. This avoids the
hardest PyO3 problem (exposing mutable Python objects from Rust) while capturing the
byte-crunching speedup.

**Estimated effort:** 2-3 sessions.
**Estimated speedup:** 5-15x on decode, 5-15x on encode.

### Step 2: MARC-8 Converter

The `MARC8ToUnicode.translate()` method is a stateful byte-by-byte loop with hash
lookups. This is exactly what Rust excels at.

**Rust side:**

```rust
/// Convert MARC-8 bytes to a Unicode string.
#[pyfunction]
fn marc8_to_unicode_rs(data: &[u8], quiet: bool) -> PyResult<String> { ... }
```

The 17K-line mapping table becomes a Rust `phf` (perfect hash) or `HashMap` compiled
into the binary — no Python dict lookup overhead.

**Python side:** `marc8.py` calls `_rmarc.marc8_to_unicode_rs()` and falls back to
the Python implementation if the Rust module isn't available.

**Estimated effort:** 1-2 sessions.
**Estimated speedup:** 10-50x (the Python version does `ord()` + dict lookup per byte).

### Step 3: Full MARCReader in Rust

Once decode_marc and marc8 are in Rust, the next bottleneck is the Python iteration
overhead in `MARCReader.__next__()`. Moving the entire read loop to Rust means:
- Read bytes from file handle (via PyO3 `read()` call)
- Parse length, validate, call decode_marc, construct Field/Record — all in Rust
- Return a fully-formed Python `Record` object

This is the hardest step because it requires constructing Python objects from Rust.

**Alternative (simpler):** Keep `MARCReader` in Python but have it call a Rust
function that does "read next chunk + decode" in one shot, returning the structured
data that Python then wraps into objects. This avoids the PyO3 complexity of
constructing Python class instances from Rust.

**Estimated effort:** 2-4 sessions.
**Estimated speedup:** 2-5x on top of Step 1 (eliminates per-record Python overhead).

### Step 4 (Optional): Zero-Copy Mode

A separate `ZeroCopyReader` that memory-maps the file and returns lightweight views
into the mapped data. Fields would be byte slices, not owned strings. This is
incompatible with the pymarc API (which returns mutable `str` values) but could be
offered as an rmarc extension for read-only analysis workloads.

```python
from rmarc.fast import ZeroCopyReader

for record in ZeroCopyReader("huge.dat"):
    # record.fields are byte-slice views, not copied strings
    tag = record[0].tag  # still a 3-byte slice
    data = record[0].data  # bytes view into mmap
```

**Estimated effort:** 3-5 sessions.
**Estimated speedup:** 2-10x on top of Step 3 for read-only workloads (no allocation).

---

## Cargo Dependencies

Add to `Cargo.toml` as needed:

```toml
[dependencies]
pyo3 = { version = "0.25", features = ["extension-module"] }
# Step 2: perfect hash for MARC-8 mapping
phf = { version = "0.11", features = ["macros"] }
# Step 4: memory-mapped files
memmap2 = "0.9"
```

Do NOT pull in a Rust MARC library from crates.io — they don't match pymarc's API
and would create more compatibility work than they save.

---

## Fallback Strategy

Every Rust function should have a Python fallback. The pattern:

```python
# marc8.py
try:
    from rmarc._rmarc import marc8_to_unicode_rs as marc8_to_unicode
except ImportError:
    def marc8_to_unicode(marc8, hide_utf8_warnings=False):
        # ... pure Python implementation ...
```

This means:
- The package works even if the Rust extension fails to compile (e.g., on an
  unsupported platform).
- We can A/B test Rust vs Python in benchmarks.
- CI can run tests with and without the extension.

---

## File Organization

```
src/
├── lib.rs              # PyO3 module definition, version()
├── marc_codec.rs       # decode_marc_raw, encode_marc_raw (Step 1)
├── marc8.rs            # marc8_to_unicode_rs (Step 2)
├── marc8_mapping.rs    # generated MARC-8 tables (Step 2)
└── reader.rs           # Rust MARCReader internals (Step 3)
```

---

## Migration Checklist Per Component

For each Rust migration:

- [ ] Write Rust implementation with unit tests
- [ ] Expose via PyO3 as `_rmarc.function_name`
- [ ] Update Python module to call Rust version with fallback
- [ ] Run full test suite (171 tests must pass)
- [ ] Run benchmark suite (must show improvement)
- [ ] Update `_rmarc.pyi` type stubs
- [ ] Document in CHANGELOG

---

## Risk Register

| Risk | Mitigation |
|---|---|
| PyO3 boundary overhead negates Rust speedup for small records | Batch API: decode multiple records per call |
| MARC-8 mapping table is huge in Rust binary | Use `phf` for compile-time perfect hashing, or lazy_static HashMap |
| Windows/macOS/Linux cross-compilation | maturin handles this; test in CI on all three |
| Mutable Python objects from Rust are hard | Don't try — return structured data, let Python wrap it |
| Zero-copy mode breaks pymarc compatibility | Keep it as a separate opt-in API, not a replacement |
