# BookShelf Developer Guide

This document explains how the application is structured and how each Python
module maps onto rmarc concepts. The target reader is a Python developer who
wants to understand how to build applications with rmarc.

---

## Module overview

```
sample_app/
├── __init__.py       # Package marker
├── __main__.py       # Entry point for `python -m sample_app`
├── store.py          # Data model: make_record() + Collection class
├── cli.py            # Argument parsing and command handlers
├── loc.py            # Library of Congress network integration
└── tests/
    ├── test_store.py  # Unit + integration tests for store.py
    ├── test_cli.py    # End-to-end CLI tests
    └── test_loc.py    # LOC tests (mocked HTTP)
```

---

## store.py — the data layer

### `make_record()` — constructing a MARC record from scratch

```python
from rmarc import Record, Field, Subfield, Indicators

record = Record()
```

A fresh `Record()` has an empty leader and no fields. The leader is a 24-byte
string that describes the record type. We set the relevant positions directly:

```python
record.leader[5] = "n"  # record status: new
record.leader[6] = "a"  # type of record: language material
record.leader[7] = "m"  # bibliographic level: monograph
record.leader[9] = "a"  # encoding: UTF-8
```

`record.leader` is a `Leader` object that supports index and slice assignment.

#### Control fields (tags < 010)

Control fields have a `data` string but no subfields or indicators:

```python
record.add_ordered_field(Field(tag="008", data="      s1925    xx            000 0 eng d"))
```

`add_ordered_field()` inserts the field so the field list stays sorted by tag
number, which is a requirement for valid MARC21 binary output.

#### Data fields (tags >= 010)

Data fields have two indicator characters and one or more subfields:

```python
record.add_ordered_field(
    Field(
        tag="245",
        indicators=Indicators("1", "0"),
        subfields=[
            Subfield("a", "The Great Gatsby"),
            Subfield("c", "Fitzgerald, F. Scott"),
        ],
    )
)
```

`Indicators` and `Subfield` are both `NamedTuple`s — lightweight and
immutable. A space `" "` means "blank/undefined" for indicators.

#### The MARC field map used by this app

| Tag | Name              | Subfields used                               |
|-----|-------------------|----------------------------------------------|
| 008 | Fixed-length data | (control field, raw string)                  |
| 020 | ISBN              | `$a` ISBN                                    |
| 100 | Author            | `$a` personal name                           |
| 245 | Title             | `$a` title, `$c` statement of responsibility |
| 260 | Publication       | `$b` publisher, `$c` year                    |
| 500 | General note      | `$a` text                                    |
| 650 | Subject heading   | `$a` topic                                   |
| 852 | Location          | `$a` shelf location                          |

---

### `Collection` — reading and writing MARC21 files

The collection is a single `.mrc` file (raw MARC21 transmission format).

#### Loading

```python
from rmarc import MARCReader

with open("bookshelf.mrc", "rb") as fh:  # always binary mode
    reader = MARCReader(fh)
    for record in reader:
        if record is not None:  # None on parse error
            self._records.append(record)
```

`MARCReader` is an iterator. Each iteration yields one `Record` or `None` if
the record was malformed.

#### Saving

```python
from rmarc import MARCWriter

with open("bookshelf.mrc", "wb") as fh:  # always binary mode
    writer = MARCWriter(fh)
    for record in self._records:
        writer.write(record)
    writer.close(close_fh=False)  # flush JSON/XML wrappers
```

`MARCWriter` writes each record as a self-describing length-prefixed byte
sequence. `close()` is a no-op for `MARCWriter` but is required for
`JSONWriter` and `XMLWriter` which need to write closing brackets/tags.

#### Search

```python
results = []
for i, rec in enumerate(self._records):
    fields = rec.get_fields(field_tag) if field_tag else rec.get_fields()
    for f in fields:
        text = f.value().lower() if not f.control_field else (f.data or "").lower()
        if query_lower in text:
            results.append((i, rec))
            break
```

Key API used:

- `rec.get_fields()` — returns all fields as a flat list
- `rec.get_fields("650")` — only fields with that tag
- `f.value()` — concatenates all subfield values with spaces
- `f.control_field` — bool, True for tags < 010
- `f.data` — the raw string for control fields

#### Convenience properties

`Record` exposes named properties that know which MARC tag to read:

```python
record.title  # field 245, subfields a+b
record.author  # field 100/110/111, subfield a
record.isbn  # field 020, subfield a
record.publisher  # field 260/264, subfield b
record.pubyear  # field 260/264, subfield c
record.subjects  # all 6xx fields
record.notes  # all 5xx fields
record.location  # field 852
```

These are the same properties exposed by pymarc, so any MARC record — whether
hand-built or fetched from LOC — works identically.

---

### Editing a record

Records are mutable. `cmd_edit` in `cli.py` demonstrates the pattern:

```python
# Remove the old field entirely
record.remove_fields("245")

# Build the replacement
record.add_ordered_field(
    Field(
        tag="245",
        indicators=Indicators("1", "0"),
        subfields=[Subfield("a", new_title), Subfield("c", author)],
    )
)

# Persist
collection.update(index, record)
```

For subfield-level edits you can mutate the field in place:

```python
f260 = record.get("260")  # returns first matching Field or None
subs = [s for s in f260.subfields if s.code != "c"]  # drop old year
subs.append(Subfield("c", "2025"))
# rebuild field rather than mutating subfields list directly
record.remove_fields("260")
record.add_ordered_field(Field(tag="260", indicators=f260.indicators, subfields=subs))
```

Or use the dict-style setter for a single subfield:

```python
f020 = record.get("020")
f020["a"] = "978-0-new-isbn"  # raises KeyError if code absent or duplicated
```

---

## cli.py — argument parsing

The CLI is built with the standard library `argparse`. One subparser per
command keeps the namespace clean and makes help text automatic:

```python
parser = argparse.ArgumentParser(prog="bookshelf")
sub = parser.add_subparsers(dest="command", required=True)

p_add = sub.add_parser("add")
p_add.add_argument("title")
p_add.add_argument("author")
p_add.set_defaults(func=cmd_add)  # dispatch table

args = parser.parse_args(argv)
args.func(args)  # call the right handler
```

The `set_defaults(func=...)` pattern means `main()` never needs an
`if/elif` chain — the parser itself holds the dispatch.

Each command handler receives a fully-populated `argparse.Namespace` and
calls `Collection` methods directly. No global state.

---

## loc.py — Library of Congress integration

### Searching

The LOC website exposes a JSON API at `https://www.loc.gov/search/`:

```python
params = urllib.parse.urlencode({
    "q": query,
    "fo": "json",
    "c": str(max_results),
    "fa": "original-format:book",  # filter to books only
})
url = f"https://www.loc.gov/search/?{params}"
```

The response is a JSON object with a `"results"` array. Each result has
`title`, `contributor`, `date`, and `number` (which may contain an LCCN).

### Fetching a MARC record by LCCN

The LOC website provides a direct MARC21 download URL:

```
https://lccn.loc.gov/{lccn}/marc
```

The response body is raw MARC21 binary — the same format `MARCReader` consumes:

```python
from rmarc import MARCReader
from io import BytesIO

marc_bytes = response.read()
reader = MARCReader(BytesIO(marc_bytes), to_unicode=True, force_utf8=True)
for record in reader:
    if record is not None:
        return record
```

`force_utf8=True` tells the reader to treat the bytes as UTF-8 even when the
leader's encoding flag is ambiguous.

---

## Export formats

All three writers follow the same protocol: construct, `write()` once per
record, `close()`.

### JSON (`JSONWriter`)

Writes a JSON array where each element is a MARC-in-JSON object:

```python
from rmarc import JSONWriter
from io import StringIO

buf = StringIO()
writer = JSONWriter(buf)  # writes opening "["
writer.write(record)  # writes one JSON object
writer.close(close_fh=False)  # writes closing "]"
```

The JSON structure mirrors `record.as_dict()`:

```python
{
    "leader": "...",
    "fields": [
        {"008": "control data"},
        {"245": {"ind1": "1", "ind2": "0", "subfields": [{"a": "Title"}]}}
    ]
}
```

### XML (`XMLWriter`)

Writes a MARCXML collection wrapped in a `<collection>` element:

```python
from rmarc import XMLWriter

with open("output.xml", "wb") as fh:  # binary mode
    writer = XMLWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()
```

### Text (`TextWriter`)

Writes MARCMaker notation — the same text that `str(record)` and `str(field)`
produce. Human-readable and diff-friendly.

```
=LDR  00000nam a2200000   4500
=008  \\\\\\\\s1925\\\\xx\\\\\\\\\\\\\\\\\\\\000\0eng\d
=100  1\$aFitzgerald, F. Scott
=245  10$aThe Great Gatsby$cFitzgerald, F. Scott
```

### Importing from MARCXML

```python
from rmarc import parse_xml_to_array

records = parse_xml_to_array("records.xml")
for rec in records:
    collection.add(rec)
```

`parse_xml_to_array` returns a plain list — no iterator needed.

---

## Running the tests

```bash
uv run pytest sample_app/tests/ -v
```

The tests are split into three files that mirror the modules:

| File            | What it tests                                                             |
|-----------------|---------------------------------------------------------------------------|
| `test_store.py` | `make_record`, `Collection` CRUD/search/reports/export, rmarc API surface |
| `test_cli.py`   | Every CLI command end-to-end via `main(argv)`                             |
| `test_loc.py`   | LOC search and fetch with `unittest.mock.patch` on `urlopen`              |

Network calls are always mocked. There are no tests that require internet
access, so the suite runs offline and in CI without special handling.

---

## Architecture decisions

**Why a single `.mrc` file?**
MARC21 binary is the canonical, lossless format. JSON and XML are derived
exports. Keeping one authoritative file makes the "source of truth" obvious
and avoids sync issues.

**Why not a database?**
The collection is expected to be small (hundreds of books, not millions).
Iterating a list in memory is fast enough, and a plain file is easy to back
up, share, and inspect with standard library tools.

**Why `add_ordered_field` everywhere?**
MARC21 validators and many downstream tools expect fields in ascending tag
order. `add_ordered_field` maintains that invariant automatically. Using
`add_field` would produce valid but technically non-conformant records.

**Why reconstruct fields for edits rather than mutating in place?**
`Subfield` is a `NamedTuple` — immutable. The cleanest way to change a
subfield value is to rebuild the field with a new `subfields` list. The dict-
style setter (`field["a"] = value`) works only when the subfield code appears
exactly once.
