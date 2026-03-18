# Phase 6: Fast JSON & XML Serialization via Optional Dependencies

## Goal

Speed up JSON and XML serialization/deserialization by transparently using `orjson`
(for JSON) and `lxml` (for XML) when they are installed. Fall back to stdlib `json` and
`xml.etree`/`xml.sax` when they are not. No change to public API.

---

## Background: What Is Slow Today

### JSON

| Code path | Library | Notes |
|-----------|---------|-------|
| `JSONReader.__init__` | `json.load` | Parses full file into Python dicts |
| `JSONReader.__next__` | pure Python dict walk | Constructs Record/Field objects |
| `record.as_json()` | `json.dumps(self.as_dict())` | Two steps: build dict then serialize |
| `JSONWriter.write` | `json.dump(record.as_dict(), fh)` | Same double step, stream variant |

`json` (CPython's stdlib) is pure Python for most of its hot path. `orjson` is a Rust-backed
library that is consistently 3–10× faster for both encoding and decoding.

### XML

| Code path | Library | Notes |
|-----------|---------|-------|
| `parse_xml` | `xml.sax.make_parser` | Python SAX parser (expat under the hood) |
| `record_to_xml_node` | `xml.etree.ElementTree` | stdlib ET, written in C but limited |
| `XMLWriter.write` | `ET.tostring` | Serializes node to bytes |

`lxml` uses libxml2/libxslt under the hood. Its SAX-compatible `iterparse` and element
builders are typically 2–5× faster than stdlib ET and the Python SAX layer.

---

## Design Principles

1. **Opt-in acceleration** — the feature works without `orjson`/`lxml`; installing them
   makes it faster automatically.
2. **No API change** — all existing public functions/classes keep their signatures.
3. **Handler classes stay as-is** — `JSONHandler` and `XmlHandler` are pymarc-compatible
   extension points used by callers who subclass them. We do not touch their logic.
4. **Acceleration in helper functions** — `record_to_xml`, `record_to_xml_node`,
   `parse_xml`, `parse_xml_to_array`, `map_xml`, `record.as_json`, `JSONReader.__init__`
   are the acceleration targets.
5. **Single capability check at import time** — avoids per-call overhead.

---

## Implementation Plan

### 1. JSON acceleration (`marcjson.py` + `reader.py` + `record.py`)

#### 1a. Capability detection (top of `marcjson.py` or a new `_compat.py`)

```python
try:
    import orjson as _json_lib
    _HAS_ORJSON = True
except ImportError:
    import json as _json_lib
    _HAS_ORJSON = False
```

#### 1b. `JSONReader` — decode with orjson

In `reader.py`, replace:

```python
self.records = json.load(self.file_handle, strict=False)
```

With:

```python
if _HAS_ORJSON:
    self.records = _json_lib.loads(self.file_handle.read())
else:
    self.records = json.load(self.file_handle, strict=False)
```

Note: `orjson.loads` accepts `bytes` or `str`, returns Python objects identically to
`json.load`. The `strict=False` flag (allows NaN/Infinity) has no equivalent in orjson;
those values are not valid in MARC-in-JSON so this difference is benign.

#### 1c. `record.as_json()` — encode with orjson

In `record.py`, replace:

```python
def as_json(self, **kwargs) -> str:
    return json.dumps(self.as_dict(), **kwargs)
```

With:

```python
def as_json(self, **kwargs) -> str:
    if _HAS_ORJSON:
        # orjson returns bytes; decode to str to match existing contract
        return _orjson.dumps(self.as_dict()).decode()
    return json.dumps(self.as_dict(), **kwargs)
```

`**kwargs` passthrough is preserved for stdlib path (e.g. `indent=2`); orjson has its own
option flags but different kwargs. For now, kwargs only apply on the stdlib path — this is
acceptable because the primary use case is compact/fast output. Document this in the
function docstring.

#### 1d. `JSONWriter.write` — encode with orjson

In `writer.py`, replace:

```python
json.dump(record.as_dict(), self.file_handle, separators=(",", ":"))
```

With:

```python
if _HAS_ORJSON:
    self.file_handle.write(_orjson.dumps(record.as_dict()).decode())
else:
    json.dump(record.as_dict(), self.file_handle, separators=(",", ":"))
```

---

### 2. XML acceleration (`marcxml.py`)

#### 2a. Capability detection

```python
try:
    import lxml.etree as _lxml_ET
    _HAS_LXML = True
except ImportError:
    _HAS_LXML = False
```

#### 2b. `parse_xml` — use lxml SAX when available

lxml's SAX interface is API-compatible with stdlib `xml.sax`. We can swap the parser:

```python
def parse_xml(xml_file, handler):
    if _HAS_LXML:
        from lxml import sax as _lxml_sax
        _lxml_sax.saxify(_lxml_ET.parse(xml_file), handler)
    else:
        parser = make_parser()
        parser.setContentHandler(handler)
        parser.setFeature(feature_namespaces, 1)
        parser.parse(xml_file)
```

`lxml.sax.saxify` replays SAX events from a parsed lxml tree — the XmlHandler receives
the same `startElementNS`/`endElementNS`/`characters` calls it does today.

**Alternative (iterparse):** For large files, lxml's `iterparse` approach may be even
faster by avoiding the SAX layer entirely. This would require a rewrite of the parse
logic but could be a follow-on optimization.

#### 2c. `record_to_xml_node` — use lxml Element builder when available

The current implementation uses `xml.etree.ElementTree`. lxml's `etree` is a drop-in
replacement for most uses:

```python
def record_to_xml_node(record, quiet=False, namespace=False):
    if _HAS_LXML:
        _ET = _lxml_ET
    else:
        _ET = ET
    marc8 = MARC8ToUnicode(quiet=quiet)
    # ... rest of function unchanged, just uses _ET instead of ET
```

#### 2d. `record_to_xml` — use lxml tostring when available

```python
def record_to_xml(record, quiet=False, namespace=False):
    node = record_to_xml_node(record, quiet, namespace)
    if _HAS_LXML:
        return _lxml_ET.tostring(node)
    return ET.tostring(node)
```

#### 2e. `XMLWriter` — pass lxml nodes to tostring

`XMLWriter.write` calls `ET.tostring(node, encoding="utf-8")`. When lxml is active,
`record_to_xml_node` returns an lxml element; we need to use `_lxml_ET.tostring`.
Best handled by making `record_to_xml` return bytes in both cases (it already does),
so `XMLWriter` just calls `record_to_xml(record)` directly.

---

## Benchmark Extensions

Add a new file `bench/bench_json_xml.py` with benchmarks that cover all four scenarios:
stdlib only, orjson only, lxml only, both.

### Fixtures to add to `bench/conftest.py`

```python
@pytest.fixture(scope="session")
def one_json_bytes():
    """Single MARC-in-JSON record as bytes."""
    with open("test_pymarc/one.json", "rb") as f:
        return f.read()

@pytest.fixture(scope="session")
def batch_json_bytes():
    """Batch MARC-in-JSON (multiple records) as bytes."""
    with open("test_pymarc/batch.json", "rb") as f:
        return f.read()

@pytest.fixture(scope="session")
def batch_xml_bytes():
    """Batch MARCXML as bytes."""
    with open("test_pymarc/batch.xml", "rb") as f:
        return f.read()

@pytest.fixture(scope="session")
def one_record(one_record_bytes):
    """Pre-parsed single Record object."""
    from rmarc import Record
    return Record(one_record_bytes)
```

### New benchmark file `bench/bench_json_xml.py`

```python
"""Benchmarks for JSON and XML serialization acceleration.

Run with:
    uv run pytest bench/bench_json_xml.py --benchmark-only
    uv run pytest bench/bench_json_xml.py --benchmark-save=json_xml_baseline

Tests cover:
  - JSON decode  (JSONReader / json.load / orjson.loads)
  - JSON encode  (record.as_json / json.dumps / orjson.dumps)
  - JSON write   (JSONWriter)
  - XML parse    (parse_xml_to_array / SAX / lxml)
  - XML serialize (record_to_xml / ET.tostring / lxml.tostring)
  - XML write    (XMLWriter)
"""

import io


# ── JSON decode ────────────────────────────────────────────────────────────────

def test_bench_json_read_one(benchmark, one_json_bytes):
    """Decode a single MARC-in-JSON record."""
    from rmarc import JSONReader

    def read():
        return list(JSONReader(one_json_bytes))

    result = benchmark(read)
    assert len(result) == 1


def test_bench_json_read_batch(benchmark, batch_json_bytes):
    """Decode a batch MARC-in-JSON file (multiple records)."""
    from rmarc import JSONReader

    def read():
        return list(JSONReader(batch_json_bytes))

    benchmark(read)


def test_bench_json_decode_stdlib(benchmark, batch_json_bytes):
    """Baseline: stdlib json.loads on raw JSON bytes."""
    import json

    benchmark(json.loads, batch_json_bytes)


def test_bench_json_decode_orjson(benchmark, batch_json_bytes):
    """Comparison: orjson.loads on raw JSON bytes (skips if not installed)."""
    pytest = __import__("pytest")
    try:
        import orjson
    except ImportError:
        pytest.skip("orjson not installed")

    benchmark(orjson.loads, batch_json_bytes)


# ── JSON encode ────────────────────────────────────────────────────────────────

def test_bench_as_json(benchmark, one_record):
    """Encode a Record to JSON string via record.as_json()."""
    benchmark(one_record.as_json)


def test_bench_json_encode_stdlib(benchmark, one_record):
    """Baseline: stdlib json.dumps on record.as_dict()."""
    import json

    d = one_record.as_dict()
    benchmark(json.dumps, d)


def test_bench_json_encode_orjson(benchmark, one_record):
    """Comparison: orjson.dumps on record.as_dict()."""
    pytest = __import__("pytest")
    try:
        import orjson
    except ImportError:
        pytest.skip("orjson not installed")

    d = one_record.as_dict()
    benchmark(orjson.dumps, d)


# ── JSON write ─────────────────────────────────────────────────────────────────

def test_bench_json_writer_single(benchmark, one_record):
    """Write a single record via JSONWriter."""
    from rmarc import JSONWriter

    def write():
        buf = io.StringIO()
        w = JSONWriter(buf)
        w.write(one_record)
        w.close(close_fh=False)
        return buf.getvalue()

    benchmark(write)


# ── XML parse ──────────────────────────────────────────────────────────────────

def test_bench_xml_parse_batch(benchmark, batch_xml_bytes):
    """Parse a batch MARCXML file to Record array."""
    from rmarc.marcxml import parse_xml_to_array

    def parse():
        return parse_xml_to_array(io.BytesIO(batch_xml_bytes))

    result = benchmark(parse)
    assert len(result) > 0


def test_bench_xml_parse_stdlib_sax(benchmark, batch_xml_bytes):
    """Baseline: raw stdlib SAX parse (no record construction)."""
    from xml.sax import make_parser
    from xml.sax.handler import ContentHandler, feature_namespaces

    class NullHandler(ContentHandler):
        pass

    def parse():
        parser = make_parser()
        parser.setContentHandler(NullHandler())
        parser.setFeature(feature_namespaces, 1)
        parser.parse(io.BytesIO(batch_xml_bytes))

    benchmark(parse)


def test_bench_xml_parse_lxml(benchmark, batch_xml_bytes):
    """Comparison: lxml.etree.parse on raw XML bytes (skips if not installed)."""
    pytest = __import__("pytest")
    try:
        import lxml.etree as lET
    except ImportError:
        pytest.skip("lxml not installed")

    def parse():
        return lET.parse(io.BytesIO(batch_xml_bytes))

    benchmark(parse)


# ── XML serialize ──────────────────────────────────────────────────────────────

def test_bench_record_to_xml(benchmark, one_record):
    """Serialize a Record to XML bytes via record_to_xml()."""
    from rmarc.marcxml import record_to_xml

    benchmark(record_to_xml, one_record)


def test_bench_xml_tostring_stdlib(benchmark, one_record):
    """Baseline: stdlib ET.tostring on a pre-built node."""
    import xml.etree.ElementTree as ET
    from rmarc.marcxml import record_to_xml_node

    node = record_to_xml_node(one_record)
    benchmark(ET.tostring, node)


def test_bench_xml_tostring_lxml(benchmark, one_record):
    """Comparison: lxml.etree.tostring on a pre-built lxml node."""
    pytest = __import__("pytest")
    try:
        import lxml.etree as lET
    except ImportError:
        pytest.skip("lxml not installed")
    from rmarc.marcxml import record_to_xml_node

    # Build an lxml node (requires lxml path in record_to_xml_node)
    node = record_to_xml_node(one_record)
    if not hasattr(node, "nsmap"):
        pytest.skip("lxml not active in record_to_xml_node")
    benchmark(lET.tostring, node)


# ── XML write ──────────────────────────────────────────────────────────────────

def test_bench_xml_writer_single(benchmark, one_record):
    """Write a single record via XMLWriter."""
    from rmarc import XMLWriter

    def write():
        buf = io.BytesIO()
        w = XMLWriter(buf)
        w.write(one_record)
        w.close(close_fh=False)
        return buf.getvalue()

    benchmark(write)
```

---

## Files to Change

| File | Change |
|------|--------|
| `python/rmarc/marcjson.py` | Add `_HAS_ORJSON` detection (or import from `_compat`) |
| `python/rmarc/reader.py` | `JSONReader.__init__`: swap to `orjson.loads` when available |
| `python/rmarc/record.py` | `as_json()`: use orjson when available |
| `python/rmarc/writer.py` | `JSONWriter.write`: use orjson when available |
| `python/rmarc/marcxml.py` | `_HAS_LXML` detection; swap `parse_xml`, `record_to_xml_node`, `record_to_xml` |
| `bench/conftest.py` | Add `one_json_bytes`, `batch_json_bytes`, `batch_xml_bytes`, `one_record` fixtures |
| `bench/bench_json_xml.py` | New file — all JSON/XML benchmarks |

`JSONHandler` and `XmlHandler` are **not changed** — they operate on already-parsed
Python objects / SAX events and are subclassable by users.

---

## Optional: `_compat.py` module

If the capability-detection boilerplate grows, extract to
`python/rmarc/_compat.py`:

```python
"""Optional fast-library detection."""
try:
    import orjson as _orjson
    HAS_ORJSON = True
except ImportError:
    import json as _orjson  # type: ignore[no-redef]
    HAS_ORJSON = False

try:
    import lxml.etree as _lxml_ET
    HAS_LXML = True
except ImportError:
    _lxml_ET = None
    HAS_LXML = False
```

This keeps `reader.py`, `writer.py`, `record.py`, and `marcxml.py` clean.

---

## Correctness Considerations

| Risk | Mitigation |
|------|-----------|
| `orjson` rejects NaN/Infinity in JSON | MARC-in-JSON never contains these; existing test suite catches regressions |
| `orjson.dumps` returns `bytes`, not `str` | `.decode()` call in `as_json()`; `JSONWriter` writes to a text file handle so also `.decode()` |
| `lxml` SAX events may differ slightly from stdlib | Run existing `test_pymarc/test_xml.py` suite against both paths |
| `lxml` element vs stdlib element type mismatch in `XMLWriter` | `record_to_xml` returns `bytes` in both paths; `XMLWriter` uses `record_to_xml`, not `record_to_xml_node` directly |
| kwargs to `as_json()` ignored with orjson | Document this; stdlib kwargs are rarely used outside tests |

---

## Acceptance Criteria

1. All existing tests pass unchanged (`uv run pytest test_pymarc/`).
2. New benchmarks run without error when `orjson`/`lxml` are not installed (skip markers).
3. New benchmarks show measurable improvement when those libraries are installed.
4. `pyproject.toml` has optional dependency groups:
   ```toml
   [project.optional-dependencies]
   fast = ["orjson>=3.9", "lxml>=5.0"]
   ```
5. `README.md` documents the optional fast-path install (`pip install rmarc[fast]`).

---

## Expected Speedups (estimated, to be confirmed by benchmarks)

| Operation | Baseline | With orjson/lxml | Expected gain |
|-----------|----------|-----------------|---------------|
| `json.loads` (batch decode) | — | orjson | 3–8× |
| `record.as_json` | — | orjson | 2–5× |
| `JSONWriter.write` | — | orjson | 2–5× |
| `parse_xml_to_array` | — | lxml | 2–4× |
| `record_to_xml` | — | lxml | 1.5–3× |
| `XMLWriter.write` | — | lxml | 1.5–3× |

These are in line with published benchmarks for both libraries against their stdlib
counterparts on similar workloads.
