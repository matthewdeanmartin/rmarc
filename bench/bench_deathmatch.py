"""3-way performance deathmatch: rmarc vs pymarc vs mrrc.

Three libraries enter, one leaves as the fastest MARC processor in the world.

Run with:
    uv run pytest bench/bench_deathmatch.py --benchmark-only -v
    make perf
"""

from __future__ import annotations

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

    # mrrc uses .title() method, pymarc/rmarc use .title property
    if name == "mrrc":

        def read_and_title():  # noqa: F811
            titles = []
            for rec in marc.MARCReader(test_dat):
                if rec:
                    titles.append(rec.title())
            return titles

    benchmark.group = "deathmatch-title-access"
    benchmark.name = f"{name}"
    result = benchmark(read_and_title)
    assert len(result) == 10


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

    if name == "mrrc":

        def access():
            for field in record.get_fields():
                _ = str(field)

    else:

        def access():
            for field in record.get_fields():
                _ = field.value()

    benchmark.group = "deathmatch-field-access"
    benchmark.name = f"{name}"
    benchmark(access)


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
    result = benchmark(to_json)
    assert len(result) == 10


# ---------------------------------------------------------------------------
# XML parse (from XML bytes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "loader"), CONTENDERS, ids=[c[0] for c in CONTENDERS])
def test_deathmatch_xml_parse(benchmark, name, loader):
    """Parse MARCXML batch to record array."""
    marc = loader()
    xml_path = "test_pymarc/batch.xml"

    if name == "mrrc":
        with open(xml_path) as f:
            xml_str = f.read()

        def parse():
            return marc.xml_to_records(xml_str)

    else:

        def parse():
            return marc.parse_xml_to_array(xml_path)

    benchmark.group = "deathmatch-xml-parse"
    benchmark.name = f"{name}"
    result = benchmark(parse)
    assert len(result) > 0
