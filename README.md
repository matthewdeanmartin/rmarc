# rmarc

A pymarc-compatible MARC21 record library with a Rust core for high performance, roughly 2x faster.

This is a fork of [pymarc](https://pypi.org/project/pymarc). Significant use of LLMs to write the Rust speedups. License
is the same MIT.

## Installing and Using

### Install from PyPI

```bash
pip install rmarc
```

For faster JSON and XML processing, install the optional fast backends:

```bash
pip install "rmarc[fast]"        # orjson (JSON) + lxml (XML)
pip install "rmarc[fast-json]"   # orjson only
pip install "rmarc[fast-xml]"    # lxml only
```

When these libraries are installed, rmarc uses them automatically — no code
changes needed. If they are not installed, rmarc falls back to stdlib `json`
and `xml.etree`/`xml.sax`.

### Basic usage

```python
from rmarc import MARCReader, MARCWriter, Record, Field, Indicators, Subfield

# Read a MARC file
with open("records.mrc", "rb") as fh:
    for record in MARCReader(fh):
        print(record.title)

# Write a MARC file
with open("out.mrc", "wb") as fh:
    writer = MARCWriter(fh)
    writer.write(record)
    writer.close()
```

### JSON (MARC-in-JSON)

```python
from rmarc import JSONReader, JSONWriter

# Read
with open("records.json") as fh:
    for record in JSONReader(fh):
        print(record.title)

# Write
with open("out.json", "w") as fh:
    writer = JSONWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()

# Serialise a single record
json_str = record.as_json()
record_dict = record.as_dict()
```

### XML (MARCXML)

```python
from rmarc import XMLWriter
from rmarc.marcxml import parse_xml_to_array, map_xml, record_to_xml

# Parse a MARCXML file
records = parse_xml_to_array("records.xml")


# Stream-process without loading everything into memory
def handle(record):
    print(record.title)


map_xml(handle, "records.xml")

# Serialise a record to XML bytes
xml_bytes = record_to_xml(record)
xml_bytes_with_ns = record_to_xml(record, namespace=True)

# Write a MARCXML collection
with open("out.xml", "wb") as fh:
    writer = XMLWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()
```

---

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

### Fast JSON and XML backends

Installing `rmarc[fast]` enables additional acceleration for JSON and XML
operations. The speedups below are measured against the stdlib-only path.

#### JSON (`pip install "rmarc[fast-json]"` — uses [orjson](https://github.com/ijl/orjson))

| Operation            | stdlib | orjson | Speedup |
|----------------------|--------|--------|---------|
| JSON decode (batch)  | ~30 us | ~6 us  | **~5x** |
| `record.as_json()`   | ~9 us  | ~5 us  | **~2x** |
| `JSONWriter.write()` | ~9 us  | ~5 us  | **~2x** |

orjson is a Rust-backed JSON library. It is used transparently whenever
installed. If a JSON document contains MARC control characters that orjson
rejects (technically invalid JSON but tolerated by some tools), rmarc
automatically retries with stdlib `json` so nothing breaks.

#### XML (`pip install "rmarc[fast-xml]"` — uses [lxml](https://lxml.de))

| Operation                   | stdlib SAX/ET | lxml    | Speedup   |
|-----------------------------|---------------|---------|-----------|
| `parse_xml_to_array()`      | ~270 us       | ~67 us  | **~4x**   |
| `record_to_xml()`           | ~110 us       | ~80 us  | **~1.4x** |
| `XMLWriter.write()` (batch) | ~600 us       | ~500 us | **~1.2x** |

lxml uses the libxml2 C library for parsing. `parse_xml` is reimplemented
using `lxml.sax.saxify` so the existing `XmlHandler` subclass API is unchanged.
`record_to_xml_node` and `record_to_xml` use `lxml.etree` as a drop-in
replacement for `xml.etree.ElementTree`.

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
- XML parsing/serialization — accelerated by lxml when installed
- JSON handling — accelerated by orjson when installed
- Convenience properties (title, isbn, author, etc.)
- Unknown encodings (cp1251, etc.) — returned as raw bytes for Python's codec system
