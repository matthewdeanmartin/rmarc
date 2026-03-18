"""Tests for fast JSON/XML serialization via optional orjson/lxml backends.

These tests verify that:
1. The _compat module correctly detects available libraries.
2. JSON encode/decode produces identical results regardless of backend.
3. XML parse/serialize produces identical results regardless of backend.
4. All existing public APIs still work.
"""

import io
import json
import unittest
import xml.etree.ElementTree as ET

import rmarc
from rmarc import Field, Indicators, JSONReader, JSONWriter, MARCReader, Record, Subfield, XMLWriter
from rmarc._compat import HAS_LXML, HAS_ORJSON, json_dumps, json_loads
from rmarc.marcxml import map_xml, parse_xml_to_array, record_to_xml, record_to_xml_node
from test_pymarc import fixture_path


def _make_record():
    """Build a simple Record with a control field and a data field."""
    rec = Record()
    rec.add_field(Field(tag="001", data="12345"))
    rec.add_field(
        Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="a", value="Test Title"),
                Subfield(code="c", value="Test Author"),
            ],
        )
    )
    return rec


class TestCompatModule(unittest.TestCase):
    """Tests for _compat capability detection."""

    def test_has_orjson_is_bool(self):
        self.assertIsInstance(HAS_ORJSON, bool)

    def test_has_lxml_is_bool(self):
        self.assertIsInstance(HAS_LXML, bool)

    def test_json_loads_returns_dict_for_object(self):
        result = json_loads('{"a": 1}')
        self.assertEqual(result, {"a": 1})

    def test_json_loads_returns_list_for_array(self):
        result = json_loads('[{"a": 1}, {"b": 2}]')
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_json_dumps_returns_str(self):
        result = json_dumps({"leader": "test", "fields": []})
        self.assertIsInstance(result, str)

    def test_json_dumps_roundtrip(self):
        obj = {"leader": "abc", "fields": [{"001": "xyz"}]}
        result = json.loads(json_dumps(obj))
        self.assertEqual(result, obj)

    def test_json_loads_handles_bytes(self):
        data = b'{"key": "value"}'
        result = json_loads(data)
        self.assertEqual(result["key"], "value")

    def test_json_loads_handles_str(self):
        data = '{"key": "value"}'
        result = json_loads(data)
        self.assertEqual(result["key"], "value")


class TestJsonEncodeDecodeConsistency(unittest.TestCase):
    """Verify as_json() output is valid JSON regardless of backend."""

    def setUp(self):
        self.record = _make_record()

    def test_as_json_returns_str(self):
        result = self.record.as_json()
        self.assertIsInstance(result, str)

    def test_as_json_is_valid_json(self):
        result = self.record.as_json()
        parsed = json.loads(result)
        self.assertIsInstance(parsed, dict)

    def test_as_json_has_leader(self):
        result = json.loads(self.record.as_json())
        self.assertIn("leader", result)
        self.assertIsInstance(result["leader"], str)

    def test_as_json_has_fields(self):
        result = json.loads(self.record.as_json())
        self.assertIn("fields", result)
        self.assertIsInstance(result["fields"], list)

    def test_as_json_control_field(self):
        result = json.loads(self.record.as_json())
        fields = result["fields"]
        control = next(f for f in fields if "001" in f)
        self.assertEqual(control["001"], "12345")

    def test_as_json_data_field(self):
        result = json.loads(self.record.as_json())
        fields = result["fields"]
        data = next(f for f in fields if "245" in f)
        self.assertEqual(data["245"]["ind1"], "1")
        self.assertEqual(data["245"]["ind2"], "0")
        subfields = data["245"]["subfields"]
        self.assertEqual(subfields[0]["a"], "Test Title")
        self.assertEqual(subfields[1]["c"], "Test Author")

    def test_as_json_kwargs_passthrough(self):
        """kwargs like indent= should still work (stdlib path or ignored gracefully)."""
        result = self.record.as_json(indent=2)
        self.assertIsInstance(result, str)
        parsed = json.loads(result)
        self.assertIn("leader", parsed)

    def test_as_dict_then_as_json_consistent(self):
        d = self.record.as_dict()
        j = json.loads(self.record.as_json())
        self.assertEqual(d, j)


class TestJsonReaderConsistency(unittest.TestCase):
    """Verify JSONReader produces correct Records regardless of backend."""

    def test_read_single_record(self):
        with fixture_path("one.json").open("rb") as fh:
            data = fh.read()
        records = list(JSONReader(data))
        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], Record)

    def test_read_batch_records(self):
        with fixture_path("batch.json").open("rb") as fh:
            data = fh.read()
        records = list(JSONReader(data))
        self.assertGreater(len(records), 1)

    def test_roundtrip_json_file(self):
        """Records loaded from JSON and serialized back should match the original."""
        with fixture_path("test.json").open() as fh:
            original = json.load(fh, strict=False)
        with fixture_path("test.json").open() as fh:
            records = list(JSONReader(fh.read()))
        self.assertEqual(len(original), len(records))
        for orig, rec in zip(original, records, strict=False):
            self.assertEqual(orig, json.loads(rec.as_json()))

    def test_read_from_bytes(self):
        with fixture_path("one.json").open("rb") as fh:
            data = fh.read()
        records = list(JSONReader(data))
        self.assertEqual(len(records), 1)

    def test_read_from_str(self):
        with fixture_path("one.json").open() as fh:
            data = fh.read()
        records = list(JSONReader(data))
        self.assertEqual(len(records), 1)

    def test_single_record_not_in_list(self):
        """A single JSON object (not wrapped in array) should parse as one record."""
        with fixture_path("test.json").open() as fh:
            first = json.load(fh, strict=False)[0]
        data = json.dumps(first)
        records = list(JSONReader(data))
        self.assertEqual(len(records), 1)


class TestJsonWriterConsistency(unittest.TestCase):
    """Verify JSONWriter output is valid JSON regardless of backend."""

    def setUp(self):
        self.record = _make_record()

    def test_writer_produces_valid_json(self):
        buf = io.StringIO()
        w = JSONWriter(buf)
        w.write(self.record)
        w.close(close_fh=False)
        result = json.loads(buf.getvalue())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_writer_multiple_records(self):
        buf = io.StringIO()
        w = JSONWriter(buf)
        w.write(self.record)
        w.write(self.record)
        w.close(close_fh=False)
        result = json.loads(buf.getvalue())
        self.assertEqual(len(result), 2)

    def test_writer_content_matches_as_dict(self):
        buf = io.StringIO()
        w = JSONWriter(buf)
        w.write(self.record)
        w.close(close_fh=False)
        written = json.loads(buf.getvalue())[0]
        self.assertEqual(written, self.record.as_dict())


class TestXmlParseConsistency(unittest.TestCase):
    """Verify XML parsing produces correct Records regardless of backend."""

    def test_parse_batch_count(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        self.assertEqual(len(records), 2)

    def test_parse_batch_types(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        for rec in records:
            self.assertIsInstance(rec, Record)

    def test_parse_control_field_content(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        record = records[0]
        self.assertEqual(record["008"].data, "910926s1957    nyuuun              eng  ")

    def test_parse_data_field_content(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        record = records[0]
        field = record["245"]
        self.assertEqual(field.indicator1, "0")
        self.assertEqual(field.indicator2, "4")
        self.assertEqual(field["a"], "The Great Ray Charles")

    def test_parse_from_bytes_io(self):
        with fixture_path("batch.xml").open("rb") as fh:
            data = fh.read()
        records = parse_xml_to_array(io.BytesIO(data))
        self.assertEqual(len(records), 2)

    def test_map_xml(self):
        seen = []
        map_xml(seen.append, str(fixture_path("batch.xml")))
        self.assertEqual(len(seen), 2)

    def test_parse_strict(self):
        with fixture_path("batch.xml").open() as fh:
            records = parse_xml_to_array(fh, strict=True)
        self.assertEqual(len(records), 2)

    def test_parse_utf8_xml(self):
        records = parse_xml_to_array(str(fixture_path("utf8.xml")))
        self.assertGreater(len(records), 0)


class TestXmlSerializeConsistency(unittest.TestCase):
    """Verify XML serialization produces valid parseable output regardless of backend."""

    def setUp(self):
        self.record = _make_record()

    def test_record_to_xml_returns_bytes(self):
        result = record_to_xml(self.record)
        self.assertIsInstance(result, bytes)

    def test_record_to_xml_is_parseable(self):
        xml_bytes = record_to_xml(self.record)
        records = parse_xml_to_array(io.BytesIO(xml_bytes))
        self.assertEqual(len(records), 1)

    def test_record_to_xml_roundtrip_leader(self):
        xml_bytes = record_to_xml(self.record)
        recovered = parse_xml_to_array(io.BytesIO(xml_bytes))[0]
        self.assertEqual(str(self.record.leader), str(recovered.leader))

    def test_record_to_xml_roundtrip_control_field(self):
        xml_bytes = record_to_xml(self.record)
        recovered = parse_xml_to_array(io.BytesIO(xml_bytes))[0]
        self.assertEqual(self.record["001"].data, recovered["001"].data)

    def test_record_to_xml_roundtrip_data_field(self):
        xml_bytes = record_to_xml(self.record)
        recovered = parse_xml_to_array(io.BytesIO(xml_bytes))[0]
        orig = self.record["245"]
        new = recovered["245"]
        self.assertEqual(orig.indicator1, new.indicator1)
        self.assertEqual(orig.indicator2, new.indicator2)
        self.assertEqual(orig["a"], new["a"])
        self.assertEqual(orig["c"], new["c"])

    def test_record_to_xml_namespace(self):
        xml_bytes = record_to_xml(self.record, namespace=True)
        self.assertIn(b'xmlns="http://www.loc.gov/MARC21/slim"', xml_bytes)

    def test_record_to_xml_no_namespace(self):
        xml_bytes = record_to_xml(self.record, namespace=False)
        self.assertNotIn(b'xmlns="http://www.loc.gov/MARC21/slim"', xml_bytes)

    def test_record_to_xml_node_returns_element(self):
        node = record_to_xml_node(self.record)
        # Works for both stdlib ET.Element and lxml._Element
        self.assertEqual(node.tag, "record")

    def test_full_roundtrip_batch(self):
        """Parse batch.xml, serialize each record, re-parse, compare."""
        originals = parse_xml_to_array(str(fixture_path("batch.xml")))
        for orig in originals:
            xml_bytes = record_to_xml(orig)
            recovered = parse_xml_to_array(io.BytesIO(xml_bytes))[0]
            orig_fields = orig.get_fields()
            rec_fields = recovered.get_fields()
            self.assertEqual(len(orig_fields), len(rec_fields))
            for f1, f2 in zip(orig_fields, rec_fields, strict=False):
                self.assertEqual(f1.tag, f2.tag)


class TestXmlWriterConsistency(unittest.TestCase):
    """Verify XMLWriter output is valid MARCXML regardless of backend."""

    def setUp(self):
        self.record = _make_record()

    def test_writer_produces_bytes(self):
        buf = io.BytesIO()
        w = XMLWriter(buf)
        w.write(self.record)
        w.close(close_fh=False)
        self.assertIsInstance(buf.getvalue(), bytes)

    def test_writer_output_contains_record_tag(self):
        buf = io.BytesIO()
        w = XMLWriter(buf)
        w.write(self.record)
        w.close(close_fh=False)
        self.assertIn(b"<record>", buf.getvalue())

    def test_writer_multiple_records(self):
        buf = io.BytesIO()
        w = XMLWriter(buf)
        w.write(self.record)
        w.write(self.record)
        w.close(close_fh=False)
        content = buf.getvalue()
        self.assertEqual(content.count(b"<record>"), 2)

    def test_writer_output_parseable(self):
        buf = io.BytesIO()
        w = XMLWriter(buf)
        w.write(self.record)
        w.close(close_fh=False)
        # Wrap in a root element since XMLWriter writes a <collection> wrapper
        content = buf.getvalue()
        records = parse_xml_to_array(io.BytesIO(content))
        self.assertEqual(len(records), 1)


class TestBackendReported(unittest.TestCase):
    """Smoke-test that the _compat module reports correct backend names."""

    def test_compat_importable(self):
        from rmarc import _compat

        self.assertTrue(hasattr(_compat, "HAS_ORJSON"))
        self.assertTrue(hasattr(_compat, "HAS_LXML"))

    def test_orjson_consistent_with_import(self):
        try:
            import orjson  # noqa: F401

            self.assertTrue(HAS_ORJSON)
        except ImportError:
            self.assertFalse(HAS_ORJSON)

    def test_lxml_consistent_with_import(self):
        try:
            import lxml  # noqa: F401

            self.assertTrue(HAS_LXML)
        except ImportError:
            self.assertFalse(HAS_LXML)


if __name__ == "__main__":
    unittest.main()
