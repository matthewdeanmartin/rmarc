# rmarc API Patterns

This document catalogs every rmarc API used in BookShelf with a short
explanation of *why* you would reach for each one. It is structured as a
pattern reference for people building applications with rmarc.

---

## Imports

```python
from rmarc import (
    # Core types
    Record, Field, Subfield, Indicators, RawField, Leader,

    # Readers
    MARCReader, JSONReader, MARCMakerReader,

    # Writers
    MARCWriter, JSONWriter, TextWriter, XMLWriter,

    # XML helpers
    parse_xml_to_array, record_to_xml, record_to_xml_node,

    # JSON helpers
    parse_json_to_array,

    # MARC-8 conversion
    marc8_to_unicode, MARC8ToUnicode,

    # Constants
    LEADER_LEN, SUBFIELD_INDICATOR, END_OF_FIELD, END_OF_RECORD,

    # Exceptions
    PymarcException, FatalReaderError, WriteNeedsRecord,
)
```

Everything is available from the top-level `rmarc` package.

---

## Creating records

### Blank record

```python
record = Record()
# Leader is pre-populated with spaces; fields list is empty.
```

### Record from raw MARC21 bytes

```python
record = Record(data=marc_bytes, to_unicode=True, force_utf8=True)
```

### Setting leader positions

```python
record.leader[5] = "n"   # record status: new
record.leader[6] = "a"   # type of record: language material
record.leader[7] = "m"   # bibliographic level: monograph
record.leader[9] = "a"   # character encoding: UTF-8
```

`Leader` supports index and slice assignment. The full 24-character string is
accessible as `str(record.leader)`.

Named properties are also available:

```python
record.leader.record_status         # position 5
record.leader.type_of_record        # position 6
record.leader.bibliographic_level   # position 7
record.leader.coding_scheme         # position 9
```

---

## Creating fields

### Control field (tag < 010)

```python
Field(tag="008", data="      s2024    xxu           000 0 eng d")
```

No indicators, no subfields — just a raw string in `data`.

### Data field

```python
Field(
    tag="245",
    indicators=Indicators("1", "0"),
    subfields=[
        Subfield(code="a", value="The Title"),
        Subfield(code="c", value="Author Name"),
    ],
)
```

`Indicators` and `Subfield` are `NamedTuple`s. Use a space `" "` for a
blank/undefined indicator.

### Default indicators

If you omit `indicators`, the field defaults to `Indicators(" ", " ")`:

```python
Field(tag="500", subfields=[Subfield("a", "A note")])
```

---

## Adding fields to a record

### `add_ordered_field` — maintains ascending tag order

Use this when building a record from scratch or when field order matters
(which it does for valid MARC21 output):

```python
record.add_ordered_field(Field(tag="650", subfields=[Subfield("a", "Python")]))
```

### `add_grouped_field` — keeps same-tag fields together

Use this when adding multiple fields of the same tag and you want them
adjacent but don't need full sort order:

```python
record.add_grouped_field(Field(tag="650", subfields=[Subfield("a", "Science")]))
record.add_grouped_field(Field(tag="650", subfields=[Subfield("a", "Technology")]))
```

### `add_field` — appends without sorting

Use this when you control the order yourself or are appending to an existing
record that is already sorted:

```python
record.add_field(extra_note_field)
```

---

## Reading fields from a record

### Get first matching field

```python
f245 = record["245"]        # raises KeyError if absent
f245 = record.get("245")    # returns None if absent
f245 = record.get("245", default_field)
```

### Get all fields with a tag

```python
subjects = record.get_fields("650")          # list[Field]
title_and_author = record.get_fields("245", "100")
all_fields = record.get_fields()             # all fields
```

### Check existence

```python
"245" in record   # True if any field with tag 245 exists
```

### Iterate all fields

```python
for field in record:
    print(field.tag, field.value())
```

---

## Convenience properties

These read the correct MARC field(s) automatically:

```python
record.title          # str | None  — field 245 $a$b
record.author         # str | None  — field 100/110/111 $a
record.isbn           # str | None  — field 020 $a
record.issn           # str | None  — field 022 $a
record.publisher      # str | None  — field 260/264 $b
record.pubyear        # str | None  — field 260/264 $c
record.subjects       # list[Field] — all 6xx fields
record.notes          # list[Field] — all 5xx fields
record.addedentries   # list[Field] — fields 700–79x
record.series         # list[Field] — fields 440/490/800–830
record.location       # list[Field] — field 852
record.physicaldescription  # list[Field] — field 300
```

---

## Reading subfields from a field

### Get first value for a code

```python
value = field["a"]               # raises KeyError if absent
value = field.get("a")           # returns None if absent
value = field.get("a", "N/A")    # with default
```

### Get all values for one or more codes

```python
values = field.get_subfields("a", "b")   # list[str], in document order
```

### Check if a subfield code is present

```python
"a" in field   # True if any subfield with code "a" exists
```

### Iterate subfields

```python
for subfield in field:
    print(subfield.code, subfield.value)
```

### Dictionary view

```python
d = field.subfields_as_dict()   # dict[str, list[str]]
# e.g. {"a": ["Title"], "c": ["Author"]}
```

---

## Modifying subfields

### Append a subfield

```python
field.add_subfield("b", "new value")
field.add_subfield("b", "insert at start", pos=0)
```

### Replace a subfield value

Works only when the code appears exactly once:

```python
field["a"] = "Corrected Title"
```

### Delete a subfield

```python
old_value = field.delete_subfield("b")   # returns the removed value
```

---

## Removing fields from a record

```python
record.remove_fields("245")           # remove all 245 fields
record.remove_fields("650", "651")    # remove multiple tags at once
record.remove_field(specific_field)   # remove a specific Field object
```

---

## Field introspection

```python
field.tag             # "245"
field.control_field   # True for tags < 010
field.indicator1      # " " / "1" / "0" etc.
field.indicator2      # " " / "1" / "0" etc.
field.indicators      # Indicators(first, second) NamedTuple
field.data            # str — control fields only
field.subfields       # list[Subfield]

field.value()         # all subfield values joined with spaces
field.format_field()  # pretty-prints; handles subject subdivisions
field.is_subject_field()  # True when tag starts with "6"
```

---

## Serialising a record

### MARC21 binary

```python
marc_bytes = record.as_marc()    # bytes — for MARCWriter or network transmission
```

### Dict (MARC-in-JSON structure)

```python
d = record.as_dict()
# {"leader": "...", "fields": [...]}
```

### JSON string

```python
json_str = record.as_json()
json_str = record.as_json(indent=2)   # pretty-printed
```

### MARCMaker text

```python
text = str(record)
# =LDR  ...
# =245  10$aTitle...
```

`str(field)` works on individual fields too:

```python
print(str(field))   # =245  10$aTitle$cAuthor
```

---

## MARC21 file I/O

### Reading

```python
with open("records.mrc", "rb") as fh:
    reader = MARCReader(fh, to_unicode=True, force_utf8=False)
    for record in reader:
        if record is None:
            print(f"Parse error: {reader.current_exception}")
            continue
        process(record)
```

Key constructor options:

| Option | Default | Meaning |
|---|---|---|
| `to_unicode` | `True` | Convert MARC-8 encoded bytes to Unicode strings |
| `force_utf8` | `False` | Treat bytes as UTF-8 regardless of leader flag |
| `permissive` | `False` | Skip recoverable errors instead of raising |
| `utf8_handling` | `"strict"` | `"strict"` / `"ignore"` / `"replace"` |

### Writing

```python
with open("output.mrc", "wb") as fh:
    writer = MARCWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()
```

---

## JSON file I/O

### Reading

```python
from rmarc import JSONReader

reader = JSONReader("records.json")
for record in reader:
    process(record)
```

Also works from a string or bytes:

```python
reader = JSONReader(json_string)
```

Helper that returns a list directly:

```python
from rmarc import parse_json_to_array

records = parse_json_to_array("records.json")
```

### Writing

```python
from rmarc import JSONWriter
from io import StringIO

buf = StringIO()
writer = JSONWriter(buf)       # writes "["
writer.write(record1)
writer.write(record2)
writer.close(close_fh=False)   # writes "]"
json_str = buf.getvalue()
```

---

## MARCXML file I/O

### Reading

```python
from rmarc import parse_xml_to_array

records = parse_xml_to_array("records.xml")
# Optional: normalize_form="NFC" for Unicode normalization
```

### Writing

```python
from rmarc import XMLWriter

with open("output.xml", "wb") as fh:   # binary mode
    writer = XMLWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()
```

### Converting a single record

```python
from rmarc import record_to_xml, record_to_xml_node

xml_bytes = record_to_xml(record)              # bytes
element = record_to_xml_node(record)           # xml.etree.ElementTree.Element
```

---

## MARCMaker text I/O

### Reading

```python
from rmarc import MARCMakerReader

reader = MARCMakerReader("records.mrc.txt")
for record in reader:
    process(record)
```

### Writing

```python
from rmarc import TextWriter

with open("output.txt", "w", encoding="utf-8") as fh:
    writer = TextWriter(fh)
    for record in records:
        writer.write(record)
    writer.close()
```

---

## Applying a function to all records in a file

```python
from rmarc import map_records

def print_title(record):
    if record:
        print(record.title)

with open("file1.mrc", "rb") as f1, open("file2.mrc", "rb") as f2:
    map_records(print_title, f1, f2)
```

For XML:

```python
from rmarc import map_xml

map_xml(print_title, "file1.xml", "file2.xml")
```

---

## MARC-8 encoding

Records from older systems may use MARC-8 character encoding rather than
UTF-8. `MARCReader` converts automatically when `to_unicode=True` (the
default). For manual conversion:

```python
from rmarc import marc8_to_unicode, map_marc8_field, map_marc8_record

# Single string
unicode_str = marc8_to_unicode(marc8_bytes)

# Single field
converted_field = map_marc8_field(field)

# Whole record
converted_record = map_marc8_record(record)
```

---

## Exceptions

All rmarc exceptions inherit from `PymarcException`:

```python
from rmarc import (
    PymarcException,       # base
    FatalReaderError,      # unrecoverable read error
    RecordLengthInvalid,   # first 5 bytes are not digits
    WriteNeedsRecord,      # writer received a non-Record
    FieldNotFound,         # remove_field couldn't find the field
)

try:
    writer.write(non_record_object)
except WriteNeedsRecord:
    print("Only Record objects can be written")
```

---

## Common patterns from BookShelf

### Pattern: field replace

Remove the old field, rebuild it, re-insert in order:

```python
record.remove_fields("245")
record.add_ordered_field(
    Field(tag="245", indicators=Indicators("1", "0"),
          subfields=[Subfield("a", new_title)])
)
```

### Pattern: partial subfield update

Preserve other subfields, replace just one:

```python
f260 = record.get("260")
if f260:
    record.remove_fields("260")
    subs = [s for s in f260.subfields if s.code != "c"]
    subs.append(Subfield("c", new_year))
    record.add_ordered_field(Field(tag="260", indicators=f260.indicators, subfields=subs))
```

### Pattern: collect across all records

```python
subjects: dict[str, int] = {}
for rec in collection.records:
    for field in rec.subjects:          # convenience property
        term = field.get("a", "")
        subjects[term] = subjects.get(term, 0) + 1
```

### Pattern: read MARC from network bytes

```python
from io import BytesIO
from rmarc import MARCReader

marc_bytes = http_response.read()
reader = MARCReader(BytesIO(marc_bytes), to_unicode=True, force_utf8=True)
for record in reader:
    if record is not None:
        return record
```

### Pattern: roundtrip test

```python
original = make_record(title="Test", author="Author")
marc_bytes = original.as_marc()
restored = Record(data=marc_bytes, to_unicode=True, force_utf8=True)
assert restored.title == original.title
```

### Pattern: convert between formats

```python
# MARC21 → JSON
with open("input.mrc", "rb") as inf, open("output.json", "w") as outf:
    reader = MARCReader(inf)
    writer = JSONWriter(outf)
    for record in reader:
        if record:
            writer.write(record)
    writer.close(close_fh=False)

# MARC21 → MARCXML
with open("input.mrc", "rb") as inf, open("output.xml", "wb") as outf:
    reader = MARCReader(inf)
    writer = XMLWriter(outf)
    for record in reader:
        if record:
            writer.write(record)
    writer.close()
```
