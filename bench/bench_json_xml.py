"""Benchmarks for JSON and XML serialization acceleration.

Run with:
    uv run pytest bench/bench_json_xml.py --benchmark-only
    uv run pytest bench/bench_json_xml.py --benchmark-save=json_xml_baseline
    uv run pytest bench/bench_json_xml.py --benchmark-compare
"""

import io

# ── Record dict/object construction ───────────────────────────────────────────


def test_bench_as_dict(benchmark, one_record):
    """Build the JSON-compatible dict from a Record (pure Python loop)."""
    benchmark(one_record.as_dict)


# ── JSON decode ────────────────────────────────────────────────────────────────


def test_bench_json_read_one(benchmark, one_json_bytes):
    """Decode a single MARC-in-JSON record via JSONReader."""
    from rmarc import JSONReader

    def read():
        return list(JSONReader(one_json_bytes))

    result = benchmark(read)
    assert len(result) == 1


def test_bench_json_read_batch(benchmark, batch_json_bytes):
    """Decode a batch MARC-in-JSON file via JSONReader."""
    from rmarc import JSONReader

    def read():
        return list(JSONReader(batch_json_bytes))

    benchmark(read)


def test_bench_json_decode_stdlib(benchmark, batch_json_bytes):
    """Baseline: stdlib json.loads on raw JSON bytes."""
    import json

    benchmark(json.loads, batch_json_bytes)


def test_bench_json_decode_orjson(benchmark, batch_json_bytes):
    """Comparison: orjson.loads on raw JSON bytes."""
    import pytest

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
    import pytest

    try:
        import orjson
    except ImportError:
        pytest.skip("orjson not installed")

    d = one_record.as_dict()
    benchmark(orjson.dumps, d)


# ── JSON write ─────────────────────────────────────────────────────────────────


def test_bench_json_writer_batch(benchmark, batch_json_bytes):
    """Round-trip: decode batch JSON then write via JSONWriter."""
    from rmarc import JSONReader, JSONWriter

    records = list(JSONReader(batch_json_bytes))

    def write():
        buf = io.StringIO()
        w = JSONWriter(buf)
        for rec in records:
            w.write(rec)
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
    """Comparison: lxml.etree.parse on raw XML bytes."""
    import pytest

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

    import pytest

    from rmarc._compat import HAS_LXML
    from rmarc.marcxml import record_to_xml_node

    if HAS_LXML:
        pytest.skip("lxml is active; stdlib node not built by record_to_xml_node")

    node = record_to_xml_node(one_record)
    benchmark(ET.tostring, node)


def test_bench_xml_tostring_lxml(benchmark, one_record):
    """Comparison: lxml.etree.tostring on a pre-built lxml node."""
    import pytest

    try:
        import lxml.etree as lET
    except ImportError:
        pytest.skip("lxml not installed")

    from rmarc._compat import HAS_LXML
    from rmarc.marcxml import record_to_xml_node

    if not HAS_LXML:
        pytest.skip("lxml not active in record_to_xml_node")

    node = record_to_xml_node(one_record)
    benchmark(lET.tostring, node)


# ── XML write ──────────────────────────────────────────────────────────────────


def test_bench_xml_writer_batch(benchmark, batch_xml_bytes):
    """Round-trip: parse batch XML then write via XMLWriter."""
    import io as _io

    from rmarc import XMLWriter
    from rmarc.marcxml import parse_xml_to_array

    records = parse_xml_to_array(_io.BytesIO(batch_xml_bytes))

    def write():
        buf = _io.BytesIO()
        w = XMLWriter(buf)
        for rec in records:
            w.write(rec)
        w.close(close_fh=False)
        return buf.getvalue()

    benchmark(write)
