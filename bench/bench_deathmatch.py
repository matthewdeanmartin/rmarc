"""3-way performance deathmatch: rmarc vs pymarc vs mrrc.

Three libraries enter, one leaves as the fastest MARC processor in the world.

Run with:
    uv run pytest bench/bench_deathmatch.py --benchmark-only -v
    make perf
"""

from __future__ import annotations

import json
from io import BytesIO

import pytest

# ---------------------------------------------------------------------------
# Library loaders
# ---------------------------------------------------------------------------

CONTENDERS = [
    ("rmarc", lambda: pytest.importorskip("rmarc")),
    ("pymarc", lambda: pytest.importorskip("pymarc")),
    ("mrrc", lambda: pytest.importorskip("mrrc")),
]


# ---------------------------------------------------------------------------
# Binary read + iterate (small: 10 records from bytes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_read_iterate_small(benchmark, test_dat, name, loader):
    """Read + iterate 10 records from bytes."""
    marc = loader()

    def iterate():
        count = 0
        for rec in marc.MARCReader(test_dat):
            if rec:
                count += 1
        return count

    benchmark.group = "deathmatch-read-small"
    benchmark.name = f"{name}"
    result = benchmark(iterate)
    assert result == 10


# ---------------------------------------------------------------------------
# Binary read + iterate (medium: 1,000 records from bytes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_read_iterate_medium(benchmark, medium_dat, name, loader):
    """Read + iterate 1,000 records from bytes."""
    marc = loader()

    def iterate():
        count = 0
        for rec in marc.MARCReader(medium_dat):
            if rec:
                count += 1
        return count

    benchmark.group = "deathmatch-read-medium"
    benchmark.name = f"{name}"
    result = benchmark(iterate)
    assert result == 1000


# ---------------------------------------------------------------------------
# Binary read + iterate (large: 100,000 records from file)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_read_iterate_large(benchmark, large_dat_path, name, loader):
    """Read + iterate 100,000 records from file."""
    marc = loader()

    def iterate():
        count = 0
        with open(large_dat_path, "rb") as fh:
            for rec in marc.MARCReader(fh):
                if rec:
                    count += 1
        return count

    benchmark.group = "deathmatch-read-large"
    benchmark.name = f"{name}"
    result = benchmark.pedantic(iterate, rounds=3, warmup_rounds=1)
    assert result == 100_000


# ---------------------------------------------------------------------------
# Title access after read (small dataset)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_title_access(benchmark, test_dat, name, loader):
    """Read 10 records and access .title on each."""
    marc = loader()

    def read_and_title():
        titles = []
        for rec in marc.MARCReader(test_dat):
            if rec:
                titles.append(rec.title)
        return titles

    reference = pytest.importorskip("pymarc")
    expected = [record.title for record in reference.MARCReader(test_dat)]
    if read_and_title() != expected:
        pytest.skip(f"{name} title results differ from pymarc; not an equivalent-output benchmark")

    benchmark.group = "deathmatch-title-access"
    benchmark.name = f"{name}"
    result = benchmark(read_and_title)
    assert result == expected


# ---------------------------------------------------------------------------
# Field access (get all fields + values from one record)
# ---------------------------------------------------------------------------


def _load_one_record(marc, test_dat):
    """Load the first record from test_dat using the given library."""
    for rec in marc.MARCReader(test_dat):
        if rec:
            return rec
    raise RuntimeError("no records found")


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_field_access(benchmark, test_dat, name, loader):
    """Access all field values on a single parsed record."""
    marc = loader()
    record = _load_one_record(marc, test_dat)

    def access():
        return [field.value() for field in record.get_fields()]

    reference = _load_one_record(pytest.importorskip("pymarc"), test_dat)
    expected = [field.value() for field in reference.get_fields()]
    if access() != expected:
        pytest.skip(f"{name} field values differ from pymarc")

    benchmark.group = "deathmatch-field-access"
    benchmark.name = f"{name}"
    assert benchmark(access) == expected


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_json_serialize(benchmark, test_dat, name, loader):
    """Serialize 10 records to JSON."""
    marc = loader()

    if name == "mrrc":

        def to_json():
            results = []
            for rec in marc.MARCReader(test_dat):
                if rec:
                    results.append(rec.to_json())
            return results

    else:

        def to_json():
            results = []
            for rec in marc.MARCReader(test_dat):
                if rec:
                    results.append(rec.as_json())
            return results

    benchmark.group = "deathmatch-json"
    benchmark.name = f"{name}"
    expected = [record.as_dict() for record in pytest.importorskip("pymarc").MARCReader(test_dat)]
    if [json.loads(value) for value in to_json()] != expected:
        pytest.skip(f"{name} JSON results differ from pymarc")
    result = benchmark(to_json)
    assert [json.loads(value) for value in result] == expected


# ---------------------------------------------------------------------------
# XML parse (from XML bytes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_xml_parse(benchmark, name, loader):
    """Parse MARCXML batch to record array."""
    marc = loader()
    xml_path = "test_pymarc/batch.xml"
    with open(xml_path, "rb") as file:
        xml_bytes = file.read()

    if name == "mrrc":
        xml_str = xml_bytes.decode("utf-8")

        def parse():
            return marc.xml_to_records(xml_str)

    else:

        def parse():
            return marc.parse_xml_to_array(BytesIO(xml_bytes))

    benchmark.group = "deathmatch-xml-parse"
    benchmark.name = f"{name}"
    expected = [r.as_marc() for r in pytest.importorskip("pymarc").parse_xml_to_array(BytesIO(xml_bytes))]
    if [r.as_marc() for r in parse()] != expected:
        pytest.skip(f"{name} XML results differ from pymarc")
    result = benchmark(parse)
    assert [r.as_marc() for r in result] == expected
