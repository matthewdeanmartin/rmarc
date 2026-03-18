# Phase 4: Performance Optimization Plan

## Current State (After Phase 3, Steps 1-2)

Steps 1 (binary MARC codec) and 2 (MARC-8 converter) are in Rust. All 181 tests
pass. Current benchmark results:

| Benchmark                    | Baseline (pure Python) | Current (Rust) | Speedup |
|------------------------------|------------------------|----------------|---------|
| decode_single                | 239 us                 | 54 us          | 4.5x    |
| roundtrip_single             | 258 us                 | 72 us          | 3.6x    |
| read_iterate_small (10 rec)  | 1,795 us               | 530 us         | 3.4x    |
| marc8_convert (1515 lines)   | 13,714 us              | 1,457 us       | 9.4x    |
| read_iterate_medium (1K rec) | 266,589 us             | 49,193 us      | 5.4x    |
| bulk_large (100K rec)        | 18,337 ms              | 4,900 ms       | 3.7x    |

---

## Where Time Goes Now (Profiled)

### Decode path breakdown (1,000 records x 10 iterations)

| Component                             | Time   | % of total |
|---------------------------------------|--------|------------|
| Rust `decode_marc_raw()`              | 0.408s | 24%        |
| Python `_decode_marc_rust()` wrapper  | 0.510s | 31%        |
| `Field.__init__()` (173K calls)       | 0.403s | 24%        |
| `Subfield()` NamedTuple creation      | 0.079s | 5%         |
| `add_field()` / list appends          | 0.083s | 5%         |
| Pre-validation (leader, base_address) | 0.003s | <1%        |
| Other (isinstance, len, etc.)         | ~0.18s | 11%        |

**Key finding:** Python object construction (Field, Subfield, Indicators) is now
**the dominant bottleneck**, taking ~48% of total decode time. The Rust codec
itself is only 24%.

### Encode path breakdown (1,000 records x 10 iterations)

| Component                      | Time   | % of total |
|--------------------------------|--------|------------|
| `field.as_marc()` (173K calls) | 0.174s | 83%        |
| Rust `encode_marc_raw()`       | 0.035s | 17%        |

**Key finding:** Field-level encoding in Python dominates. Moving field encoding
to Rust could save ~80% of encode time.

### MARCReader overhead

| Component              | Time (1K records x 10) |
|------------------------|------------------------|
| Direct `Record(chunk)` | 0.615s                 |
| Via `MARCReader`       | 0.732s                 |
| Reader overhead        | 0.118s (16%)           |

Reader overhead is moderate — worth optimizing but not the top priority.

---

## Optimization Ideas (Ranked by Impact)

### 1. Fast Field Construction (HIGH IMPACT, LOW RISK)

**Problem:** `Field.__init__()` does tag normalization (`int(tag):03`), isinstance
checks, and conditional branching on every call. With ~17 fields per record and
100K records, that's 1.7M calls.

**Fix:** Add a `Field._from_rust()` classmethod or use `Field.__new__()` to bypass
`__init__` when constructing from Rust-decoded data (tags are already normalized,
types are known).

**Measured impact:**

- `Field.__new__` + direct attribute assignment: **0.22 us/field** vs 1.09 us/field
- On wrapping 1K decoded records x 10: **0.174s vs 0.359s (2.1x faster)**
- Expected decode_single improvement: ~54 us → ~40 us (~35% faster)

**Estimated overall decode speedup:** 1.3-1.5x on top of current numbers.

**Implementation:**

```python
# In record.py _decode_marc_rust:
f = Field.__new__(Field)
f.tag = tag  # Already "245" format from Rust
f.data = None
f.control_field = False
f._indicators = Indicators(ind1, ind2)
f.subfields = subs
```

### 2. Full Encode in Rust (HIGH IMPACT, MEDIUM RISK)

**Problem:** `record.as_marc()` calls Python `field.as_marc()` per field, which
does f-string formatting and `.encode()`. The Rust `encode_marc_raw` only handles
directory+leader assembly — the actual field encoding is still Python.

**Fix:** New Rust function `encode_record_raw(leader, fields_data)` that takes
field data as `[(tag, is_control, data_or_subfields)]` and does all encoding —
subfield indicator insertion, indicator prefixing, UTF-8 encoding, directory
building, and leader patching — in one call.

**Measured impact:**

- Data extraction (Python side) takes only 0.045s vs current 0.233s total
- Expected **4-5x speedup on encode**, bringing roundtrip from 3.6x → ~5x

**Implementation:**

```rust
#[pyfunction]
fn encode_record_full(
    leader: &str,
    encoding: &str,
    fields: Vec<FieldSpec>,  // tag, is_control, data/ind1/ind2/subfields
) -> PyResult<Vec<u8>> { ... }
```

### 3. Batch Decode API (MEDIUM IMPACT, LOW RISK)

**Problem:** For bulk reading, Python calls Rust per-record. Each call crosses the
PyO3 boundary, creates Python tuples/lists, and returns. With 100K records, the
per-call overhead (argument marshaling, GIL, tuple allocation) adds up.

**Fix:** Add `decode_marc_batch(data: bytes) -> list` that splits the buffer into
records AND decodes them all in a single Rust call. Returns the same structured
tuples but amortizes call overhead.

**Measured impact:**

- Per-record Rust call overhead: ~1-2 us (argument conversion + return)
- For 100K records: saves ~100-200ms (small but free)
- Bigger win: Rust can split records without BytesIO, eliminating Python read loop

**Estimated bulk speedup:** 1.1-1.2x

**Implementation:**

```rust
#[pyfunction]
fn decode_marc_batch(data: &[u8], to_unicode: bool, ...)
    -> PyResult<Vec<(String, Vec<...>)>> { ... }
```

Python side: MARCReader detects bytes input → calls batch; file input → calls
per-record.

### 4. Lean MARCReader.__next__() (MEDIUM IMPACT, LOW RISK)

**Problem:** `MARCReader.__next__()` has 16% overhead: reading from BytesIO,
int conversion, validation, exception handling. It also constructs a full
`Record` object per iteration (including `__init__` overhead).

**Fix a (Python-only):** Skip `Record.__init__` overhead by constructing Record
with `__new__` and calling `_decode_marc_rust` directly.

**Fix b (Rust):** `read_next_record(file_handle) -> bytes` — Rust reads the next
record chunk from the file handle, validates length and end-of-record marker.
Python just wraps the result.

**Estimated speedup:** 1.1-1.2x on iterate benchmarks.

### 5. Encode Fields in Rust (MEDIUM IMPACT, MEDIUM RISK)

**Problem:** Even without full-encode (idea 2), we could move just `field.as_marc()`
to Rust. Each call does string concatenation + encode. With 17 fields/record and
100K records, that's 1.7M Python string operations.

**Fix:** Rust function `encode_field(tag, is_control, data, ind1, ind2, subfields, encoding) -> bytes`

This is a simpler version of idea 2 that doesn't change the record-level encode
flow. Could be done incrementally.

**Estimated speedup:** 2-3x on encode path.

### 6. Pre-intern Common Strings (LOW IMPACT, LOW RISK)

**Problem:** Rust creates new Python string objects for every tag ("245", "100",
etc.) and subfield code ("a", "b", etc.) on every call. Most MARC records use
the same ~50 tags and ~26 codes.

**Fix:** Use `PyString::intern()` in Rust for tags and subfield codes. This
returns the same Python string object for repeated values, reducing allocation
and enabling fast identity comparisons.

**Estimated speedup:** 5-10% on decode (reduces allocation pressure).

**Implementation:**

```rust
// Instead of: PyString::new(py, tag_str)
// Use:        PyString::intern(py, tag_str)
```

### 7. Return Fields as Flat Lists (LOW IMPACT, HIGH RISK)

**Problem:** Rust returns nested tuples: `(tag, ("data", ind1, ind2, [(code, val), ...]))`.
Python unpacks these with indexing. The nested structure requires creating many
small PyTuple objects.

**Fix:** Return flat lists or a custom struct. For example:
`[tag, "D", ind1, ind2, n_subs, code1, val1, code2, val2, ...]`

This reduces PyTuple allocation but makes the Python unpacking code uglier.

**Estimated speedup:** 5-15% on decode (fewer small allocations).

**Risk:** Makes the interface more fragile and harder to debug. Probably not
worth the maintenance cost unless we're chasing the last few percent.

### 8. Avoid Re-validation in Python (LOW IMPACT, LOW RISK)

**Problem:** `_decode_marc_rust()` does Python-side validation (leader check,
base_address parsing) before calling Rust, because Rust raises generic
`ValueError` but Python needs specific exception types.

**Fix:** Have Rust return structured error codes instead of error messages.
Python maps codes to exceptions without re-parsing the leader.

**Estimated speedup:** <1% (validation is 0.3 us/record — negligible).

**Reality check:** Not worth the code complexity.

---

## Recommended Execution Order

### Round 1: Low-hanging fruit (Python-only changes)

1. **Fast Field construction** — bypass `__init__` in `_decode_marc_rust()`.
   Modify `record.py` only. No Rust changes needed. Expected: decode 1.3-1.5x
   faster.

### Round 2: Rust encode improvements

2. **Full encode in Rust** — new `encode_record_full()` function. Expected:
   encode 4-5x faster, roundtrip approaches 5x.

### Round 3: Batch operations

3. **Batch decode** — new `decode_marc_batch()` function for bulk reads.
4. **String interning** — use `PyString::intern()` for tags and codes.

### Round 4: Optional / measure-first

5. Lean MARCReader — only if batch decode doesn't subsume it.
6. Flat return format — only if profiling shows tuple allocation is still hot.

---

## Non-Goals

These are explicitly NOT worth optimizing:

- **MARC-8 further optimization** — already 9.4x faster, and most real-world
  MARC files use UTF-8 (or unannounced mixtures of ASCII, UTF-8, and legacy
  Windows codepages). MARC-8 is a shrinking use case.

- **XML/JSON serialization** — dominated by CPython C extensions (`xml.etree`,
  `json`). Rust won't help unless we replace the XML parser entirely.

- **Convenience properties** (title, isbn, etc.) — called once per record at
  most. Total time is negligible.

- **Leader class** — construction takes 0.3 us/record. Not a bottleneck.

- **Zero-copy mode** — the complexity/API-break tradeoff isn't worth it for the
  pymarc-compatible API. Could be a separate `rmarc.fast` module later if there's
  demand.

---

## Results So Far

### Round 1: Fast Field Construction + String Interning (DONE)

Bypassed `Field.__init__()` in `_decode_marc_rust()` using `__new__` + direct
attribute assignment. Added `PyString::intern()` for tags, subfield codes, and
the "control"/"data" sentinel strings.

| Benchmark           | Before (vs baseline) | After (vs baseline) | Round improvement |
|---------------------|----------------------|---------------------|-------------------|
| decode_single       | 4.5x (54 us)         | **6.1x (39 us)**    | 1.38x faster      |
| roundtrip_single    | 3.6x (79 us)         | **4.2x (62 us)**    | 1.27x faster      |
| read_iterate_small  | 3.4x (768 us)        | **4.3x (413 us)**   | 1.86x faster      |
| read_iterate_medium | 5.4x (65 ms)         | **5.3x (51 ms)**    | 1.28x faster      |
| bulk_large          | 3.7x (5.5s)          | **4.3x (4.3s)**     | 1.28x faster      |
| marc8_convert       | 9.4x                 | 9.4x (unchanged)    | —                 |

---

## Success Criteria

| Benchmark           | Current  | Target       | How                        |
|---------------------|----------|--------------|----------------------------|
| decode_single       | **6.1x** | ~~≥6x~~ DONE | Fast Field construction    |
| roundtrip_single    | 4.2x     | ≥5x          | Full Rust encode           |
| read_iterate_small  | 4.3x     | ~~≥4x~~ DONE | Fast Field + lean reader   |
| read_iterate_medium | 5.3x     | ≥6x          | Batch decode               |
| bulk_large          | 4.3x     | ≥5x          | Batch decode + full encode |
| marc8_convert       | 9.4x     | 9.4x (hold)  | No changes planned         |

---

## Measurement Protocol

For each optimization:

1. Save current benchmark: `uv run pytest bench/ --benchmark-save=before_optN`
2. Implement the change
3. Run tests: `uv run pytest tests/` (all must pass)
4. Run benchmarks: `uv run pytest bench/ --benchmark-save=after_optN`
5. Compare: `uv run pytest bench/ --benchmark-compare`
6. If any benchmark regresses >10%, investigate before merging
7. If the target benchmark doesn't improve ≥10%, revert
