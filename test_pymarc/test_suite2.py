import json
import tempfile
import unicodedata
import unittest
from io import BytesIO, StringIO
from pathlib import Path

import rmarc
from rmarc import (
    Field,
    Indicators,
    JSONReader,
    JSONWriter,
    MARCMakerReader,
    MARCReader,
    MARCWriter,
    Record,
    Subfield,
    TextWriter,
    XMLWriter,
)
from rmarc.exceptions import FieldNotFound, MissingLinkedFields, PymarcException, RecordLeaderInvalid, WriteNeedsRecord
from rmarc.marcjson import parse_json_to_array
from rmarc.marcxml import parse_xml_to_array, record_to_xml
from rmarc.record import normalize_subfield_code

TEST_DIR = Path(__file__).resolve().parent


def _fixture_path(name: str) -> Path:
    return TEST_DIR / name


def _read_fixture_bytes(name: str) -> bytes:
    return _fixture_path(name).read_bytes()


def _make_simple_record() -> Record:
    record = Record()
    record.add_field(
        Field(
            "245",
            Indicators("0", "1"),
            [Subfield("a", "Test Title /"), Subfield("c", "Test Author.")],
        )
    )
    return record


def _make_full_record() -> Record:
    record = Record()
    record.add_field(Field("001", data="ocm12345678"))
    record.add_field(Field("003", data="OCoLC"))
    record.add_field(Field("008", data="910926s1957    nyuuun              eng  "))
    record.add_field(Field("020", Indicators(" ", " "), [Subfield("a", "978-0-316-76948-8 (pbk.)")]))
    record.add_field(
        Field(
            "100",
            Indicators("1", " "),
            [Subfield("a", "Salinger, J. D."), Subfield("d", "1919-2010.")],
        )
    )
    record.add_field(
        Field(
            "245",
            Indicators("1", "4"),
            [Subfield("a", "The catcher in the rye /"), Subfield("c", "J.D. Salinger.")],
        )
    )
    record.add_field(
        Field(
            "260",
            Indicators(" ", " "),
            [Subfield("a", "Boston :"), Subfield("b", "Little, Brown,"), Subfield("c", "1951.")],
        )
    )
    record.add_field(Field("300", Indicators(" ", " "), [Subfield("a", "277 p. ;"), Subfield("c", "21 cm.")]))
    record.add_field(Field("490", Indicators(" ", " "), [Subfield("a", "Backlist classics")]))
    record.add_field(Field("650", Indicators(" ", "0"), [Subfield("a", "Teenage boys"), Subfield("v", "Fiction.")]))
    record.add_field(Field("852", Indicators("0", " "), [Subfield("a", "DLC"), Subfield("b", "Main")]))
    return record


class TempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp_path = Path(self._tmpdir.name)

    def write_text_file(self, name: str, content: str, encoding: str = "utf-8") -> Path:
        path = self.tmp_path / name
        path.write_text(content, encoding=encoding)
        return path

    def write_bytes_file(self, name: str, content: bytes) -> Path:
        path = self.tmp_path / name
        path.write_bytes(content)
        return path


class FieldSuite2Test(unittest.TestCase):
    def test_field_normalizes_numeric_tags_and_defaults_indicators(self):
        field = Field("42", subfields=[Subfield("a", "Meaning")])
        self.assertEqual(field.tag, "042")
        self.assertEqual(field.indicators, Indicators(" ", " "))
        self.assertEqual(field["a"], "Meaning")

    def test_control_field_detected_for_009_and_not_for_010(self):
        control = Field("009", data="abc")
        data = Field("010", Indicators(" ", " "), [Subfield("a", "123")])
        self.assertTrue(control.control_field)
        self.assertEqual(control.data, "abc")
        self.assertFalse(data.control_field)

    def test_convert_legacy_subfields_pairs_codes_and_values(self):
        converted = Field.convert_legacy_subfields(["a", "Title", "c", "Author"])
        self.assertEqual(converted, [Subfield("a", "Title"), Subfield("c", "Author")])

    def test_old_style_string_subfields_raise_value_error(self):
        with self.assertRaises(ValueError):
            Field("245", Indicators("0", "1"), ["a", "Title", "c", "Author"])

    def test_setitem_requires_exactly_one_matching_code(self):
        field = Field("245", Indicators("0", "1"), [Subfield("a", "Old")])
        field["a"] = "New"
        self.assertEqual(field["a"], "New")

        repeated = Field("245", Indicators("0", "1"), [Subfield("a", "One"), Subfield("a", "Two")])
        with self.assertRaises(KeyError):
            repeated["a"] = "Updated"

    def test_add_and_delete_subfields_respect_position(self):
        field = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        field.add_subfield("b", "Subtitle", pos=1)
        self.assertEqual(field.get_subfields("a", "b", "c"), ["Title", "Subtitle", "Author"])
        removed = field.delete_subfield("b")
        self.assertEqual(removed, "Subtitle")
        self.assertEqual(field.get_subfields("a", "b", "c"), ["Title", "Author"])

    def test_subfields_as_dict_and_format_field(self):
        field = Field(
            "650",
            Indicators(" ", "0"),
            [Subfield("a", "Libraries"), Subfield("x", "Automation"), Subfield("v", "Fiction.")],
        )
        self.assertEqual(
            field.subfields_as_dict(),
            {"a": ["Libraries"], "x": ["Automation"], "v": ["Fiction."]},
        )
        self.assertEqual(field.format_field(), "Libraries -- Automation -- Fiction.")

    def test_normalize_subfield_code_handles_utf8_and_latin1_diacritics(self):
        code, skip_bytes = normalize_subfield_code(b"eclair")
        self.assertEqual((code, skip_bytes), ("e", 1))

        utf8_code, utf8_skip = normalize_subfield_code("éclair".encode())
        self.assertEqual((utf8_code, utf8_skip), ("e", 2))

        latin1_code, latin1_skip = normalize_subfield_code(b"\xe9clair")
        self.assertEqual((latin1_code, latin1_skip), ("e", 1))


class RecordSuite2Test(unittest.TestCase):
    def test_add_grouped_field_sorts_by_hundreds_group(self):
        record = Record()
        record.add_grouped_field(Field("650", Indicators(" ", "0"), [Subfield("a", "Subject")]))
        record.add_grouped_field(Field("245", Indicators("1", "0"), [Subfield("a", "Title")]))
        record.add_grouped_field(Field("100", Indicators("1", " "), [Subfield("a", "Author")]))
        self.assertEqual([field.tag for field in record.get_fields()], ["100", "245", "650"])

    def test_add_ordered_field_sorts_exact_numeric_tags(self):
        record = Record()
        record.add_ordered_field(Field("650", Indicators(" ", "0"), [Subfield("a", "Subject")]))
        record.add_ordered_field(Field("100", Indicators("1", " "), [Subfield("a", "Author")]))
        record.add_ordered_field(Field("245", Indicators("1", "0"), [Subfield("a", "Title")]))
        self.assertEqual([field.tag for field in record.get_fields()], ["100", "245", "650"])

    def test_remove_field_and_remove_fields(self):
        record = _make_full_record()
        field_245 = record["245"]
        record.remove_field(field_245)
        self.assertNotIn("245", record)

        record.remove_fields("490", "852")
        self.assertEqual(record.get_fields("490"), [])
        self.assertEqual(record.get_fields("852"), [])

        with self.assertRaises(FieldNotFound):
            record.remove_field(field_245)

    def test_get_linked_fields_returns_matches_and_raises_when_missing(self):
        linked_source = Field("245", Indicators("1", "0"), [Subfield("6", "880-01"), Subfield("a", "Romanized title")])
        linked_target = Field("880", Indicators("1", "0"), [Subfield("6", "245-01"), Subfield("a", "Linked title")])
        missing_target = Field("246", Indicators("3", "0"), [Subfield("6", "880-99"), Subfield("a", "Alternate title")])

        record = Record(fields=[linked_source, linked_target, missing_target])
        self.assertEqual(record.get_linked_fields(linked_source), [linked_target])

        with self.assertRaises(MissingLinkedFields):
            record.get_linked_fields(missing_target)

    def test_record_properties_cover_title_author_ids_and_publishing(self):
        record = _make_full_record()
        self.assertEqual(record.title, "The catcher in the rye /")
        self.assertEqual(record.author, "Salinger, J. D. 1919-2010.")
        self.assertEqual(record.isbn, "9780316769488")
        self.assertEqual(record.publisher, "Little, Brown,")
        self.assertEqual(record.pubyear, "1951.")
        self.assertEqual([field.tag for field in record.series], ["490"])
        self.assertEqual([field.tag for field in record.subjects], ["650"])
        self.assertEqual([field.tag for field in record.location], ["852"])

    def test_as_dict_and_as_json_preserve_expected_shape(self):
        record = _make_full_record()
        as_dict = record.as_dict()
        self.assertIn("leader", as_dict)
        self.assertIn("fields", as_dict)
        self.assertEqual(as_dict["fields"][0], {"001": "ocm12345678"})

        as_json = json.loads(record.as_json())
        self.assertEqual(as_json["fields"][3]["020"]["subfields"][0], {"a": "978-0-316-76948-8 (pbk.)"})

    def test_as_marc_roundtrip_preserves_key_values(self):
        record = _make_full_record()
        encoded = record.as_marc()
        decoded = Record(encoded)
        self.assertEqual(decoded["001"].data, "ocm12345678")
        self.assertEqual(decoded["245"]["a"], "The catcher in the rye /")
        self.assertEqual(decoded["260"]["b"], "Little, Brown,")
        self.assertEqual(decoded.as_marc(), encoded)


class ReaderSuite2Test(TempDirTestCase):
    def test_marc_reader_from_bytes_reads_fixture_records(self):
        reader = MARCReader(_read_fixture_bytes("test.dat"))
        records = [record for record in reader if record is not None]
        self.assertEqual(len(records), 10)
        self.assertEqual(records[0]["245"]["a"], "ActivePerl with ASP and ADO /")

    def test_marc_reader_reports_truncated_chunk(self):
        reader = MARCReader(b"0012")
        records = list(reader)
        self.assertEqual(records, [None])
        self.assertEqual(reader.current_chunk, b"0012")
        self.assertIsInstance(reader.current_exception, rmarc.exceptions.TruncatedRecord)

    def test_map_records_counts_across_multiple_files(self):
        seen = []

        def capture(record):
            if record is not None:
                seen.append(record["245"]["a"])

        with _fixture_path("test.dat").open("rb") as first, _fixture_path("test.dat").open("rb") as second:
            rmarc.map_records(capture, first, second)

        self.assertEqual(len(seen), 20)

    def test_marcmaker_reader_from_temp_file_roundtrips(self):
        with _fixture_path("test.dat").open("rb") as fh:
            marcmaker_text = "\n".join(str(record) for record in MARCReader(fh) if record is not None)

        path = self.write_text_file("records.mrk", marcmaker_text)
        reader = MARCMakerReader(str(path), encoding="utf-8")
        record = next(reader)
        self.assertEqual(record["245"]["a"], "ActivePerl with ASP and ADO /")

    def test_marcmaker_reader_wraps_invalid_lines(self):
        reader = MARCMakerReader("=999")
        with self.assertRaises(PymarcException) as cm:
            next(reader)
        self.assertEqual(str(cm.exception), 'Unable to parse line "=999"')

    def test_json_reader_accepts_single_record_and_file_path(self):
        with _fixture_path("one.json").open(encoding="utf-8") as fh:
            payload = json.load(fh)

        reader = JSONReader(json.dumps(payload))
        try:
            single = list(reader)
        finally:
            reader.file_handle.close()
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0]["001"].data, payload["fields"][0]["001"])

        copied_json = self.write_text_file("one.json", json.dumps([payload]), encoding="utf-8")
        file_reader = JSONReader(str(copied_json))
        try:
            from_file = list(file_reader)
        finally:
            file_reader.file_handle.close()
        self.assertGreater(len(from_file), 0)
        self.assertEqual(from_file[0]["245"]["a"], "ActivePerl with ASP and ADO /")

    def test_parse_json_to_array_matches_dat_fixture(self):
        with _fixture_path("one.json").open(encoding="utf-8") as fh:
            json_records = parse_json_to_array(fh)
        with _fixture_path("one.dat").open("rb") as fh:
            dat_records = [record for record in MARCReader(fh) if record is not None]

        self.assertEqual(len(json_records), len(dat_records))
        for json_record, dat_record in zip(json_records, dat_records, strict=True):
            self.assertEqual(json_record.as_marc(), dat_record.as_marc())


class WriterSuite2Test(TempDirTestCase):
    def test_marc_writer_file_roundtrip(self):
        output = self.tmp_path / "record.mrc"
        with output.open("wb") as fh:
            writer = MARCWriter(fh)
            writer.write(_make_full_record())
            writer.close()

        with output.open("rb") as fh:
            record = next(MARCReader(fh))
        self.assertIsNotNone(record)
        self.assertEqual(record["245"]["a"], "The catcher in the rye /")

    def test_json_writer_to_string_and_file(self):
        handle = StringIO()
        self.addCleanup(handle.close)
        writer = JSONWriter(handle)
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        payload = json.loads(handle.getvalue())
        self.assertEqual(payload[0]["fields"][0]["245"]["subfields"][0], {"a": "Test Title /"})

        output = self.tmp_path / "records.json"
        with output.open("w", encoding="utf-8") as fh:
            writer = JSONWriter(fh)
            writer.write(_make_full_record())
            writer.close()
        written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(written[0]["fields"][0], {"001": "ocm12345678"})

    def test_text_writer_separates_multiple_records(self):
        handle = StringIO()
        self.addCleanup(handle.close)
        writer = TextWriter(handle)
        writer.write(_make_simple_record())
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        text = handle.getvalue()
        self.assertEqual(text.count("=LDR"), 2)
        self.assertIn("\n\n=LDR", text)

    def test_xml_writer_file_roundtrip(self):
        output = self.tmp_path / "records.xml"
        with output.open("wb") as fh:
            writer = XMLWriter(fh)
            writer.write(_make_full_record())
            writer.close()

        parsed = parse_xml_to_array(str(output))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["245"]["a"], "The catcher in the rye /")

    def test_writers_reject_non_record_values(self):
        for writer_class, handle in (
            (MARCWriter, BytesIO()),
            (JSONWriter, StringIO()),
            (TextWriter, StringIO()),
            (XMLWriter, BytesIO()),
        ):
            with self.subTest(writer_class=writer_class.__name__):
                writer = writer_class(handle)
                with self.assertRaises(WriteNeedsRecord):
                    writer.write("not a record")
                writer.close(close_fh=False)


class XmlSuite2Test(TempDirTestCase):
    def test_record_to_xml_honors_namespace_flag(self):
        record = _make_simple_record()
        xml_without_namespace = record_to_xml(record, namespace=False)
        xml_with_namespace = record_to_xml(record, namespace=True)
        self.assertNotIn(b'xmlns="http://www.loc.gov/MARC21/slim"', xml_without_namespace)
        self.assertIn(b'xmlns="http://www.loc.gov/MARC21/slim"', xml_with_namespace)

    def test_parse_xml_to_array_strict_and_bad_tag(self):
        strict_records = parse_xml_to_array(str(_fixture_path("batch.xml")), strict=True)
        self.assertEqual(len(strict_records), 2)

        with _fixture_path("bad_tag.xml").open(encoding="utf-8") as fh, self.assertRaises(RecordLeaderInvalid):
            parse_xml_to_array(fh)

    def test_parse_xml_to_array_can_normalize_unicode(self):
        decomposed = unicodedata.normalize("NFD", "Cafe")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<collection xmlns="http://www.loc.gov/MARC21/slim">'
            "<record>"
            "<leader>00000nam  2200000   4500</leader>"
            '<datafield tag="245" ind1="0" ind2="0">'
            f'<subfield code="a">{decomposed}</subfield>'
            "</datafield>"
            "</record>"
            "</collection>"
        )
        path = self.write_text_file("normalized.xml", xml, encoding="utf-8")
        records = parse_xml_to_array(str(path), normalize_form="NFC")
        self.assertEqual(records[0]["245"]["a"], unicodedata.normalize("NFC", decomposed))


if __name__ == "__main__":
    unittest.main()
