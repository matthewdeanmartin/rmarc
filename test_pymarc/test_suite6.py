import sys
import unittest
from io import StringIO

sys.path.insert(0, "python")

from rmarc.field import Field, Indicators, Subfield
from rmarc.marcxml import parse_xml_to_array
from rmarc.reader import JSONReader, MARCReader
from rmarc.record import Record, normalize_subfield_code


class TestSuite6(unittest.TestCase):
    def test_normalize_subfield_code_handles_multibyte_utf8(self):
        code, skip_bytes = normalize_subfield_code("éTitle".encode())

        self.assertEqual(code, "e")
        self.assertEqual(skip_bytes, 2)

    def test_subject_format_field_skips_linkage_and_uses_subject_separator(self):
        field = Field(
            "650",
            indicators=Indicators(" ", "0"),
            subfields=[
                Subfield("6", "880-01"),
                Subfield("a", "Cats"),
                Subfield("x", "Behavior"),
                Subfield("z", "New York"),
            ],
        )

        self.assertEqual(field.format_field(), "Cats -- Behavior -- New York")
        self.assertEqual(field.linkage_occurrence_num(), "01")

    def test_record_property_helpers_cover_common_metadata_paths(self):
        record = Record(
            fields=[
                Field("020", indicators=Indicators(" ", " "), subfields=[Subfield("a", "978-1-4028-9462-6 (pbk.)")]),
                Field("100", indicators=Indicators("1", " "), subfields=[Subfield("a", "Doe, Jane.")]),
                Field("130", indicators=Indicators(" ", "0"), subfields=[Subfield("a", "Uniform title.")]),
                Field(
                    "245",
                    indicators=Indicators("1", "0"),
                    subfields=[Subfield("a", "Main title"), Subfield("b", "subtitle")],
                ),
                Field(
                    "264",
                    indicators=Indicators(" ", "1"),
                    subfields=[Subfield("b", "Example Press"), Subfield("c", "2026")],
                ),
            ]
        )

        self.assertEqual(record.title, "Main title subtitle")
        self.assertEqual(record.isbn, "9781402894626")
        self.assertEqual(record.author, "Doe, Jane.")
        self.assertEqual(record.uniformtitle, "Uniform title.")
        self.assertEqual(record.publisher, "Example Press")
        self.assertEqual(record.pubyear, "2026")

    def test_record_get_linked_fields_matches_880_by_occurrence_number(self):
        main = Field(
            "245", indicators=Indicators("1", "0"), subfields=[Subfield("6", "880-02"), Subfield("a", "Latin")]
        )
        linked = Field(
            "880", indicators=Indicators("1", "0"), subfields=[Subfield("6", "245-02"), Subfield("a", "Linked")]
        )
        record = Record(fields=[main, linked])

        self.assertEqual(record.get_linked_fields(main), [linked])

    def test_record_as_marc_round_trip_preserves_control_and_data_fields(self):
        record = Record(
            fields=[
                Field("001", data="123456"),
                Field(
                    "245",
                    indicators=Indicators("1", "0"),
                    subfields=[Subfield("a", "Main title"), Subfield("b", "subtitle")],
                ),
            ]
        )

        encoded = record.as_marc()
        decoded = Record(encoded)

        self.assertEqual(decoded["001"].data, "123456")
        self.assertEqual(decoded["245"].indicator1, "1")
        self.assertEqual(decoded["245"].indicator2, "0")
        self.assertEqual(decoded["245"]["a"], "Main title")
        self.assertEqual(decoded["245"]["b"], "subtitle")
        self.assertEqual(decoded.leader.coding_scheme, "a")

    def test_marc_reader_sets_current_exception_for_bad_end_of_record(self):
        record = Record(fields=[Field("001", data="123")])
        broken = record.as_marc()[:-1] + b"X"

        reader = MARCReader(broken)
        item = next(reader)

        self.assertIsNone(item)
        self.assertEqual(type(reader.current_exception).__name__, "EndOfRecordNotFound")
        self.assertEqual(reader.current_chunk, broken)

    def test_json_reader_accepts_single_record_object(self):
        payload = (
            '{"leader":"00000nam a2200000   4500","fields":[{"001":"123"},'
            '{"245":{"ind1":"1","ind2":"0","subfields":[{"a":"Title"}]}}]}'
        )

        record = next(iter(JSONReader(payload)))

        self.assertEqual(record["001"].data, "123")
        self.assertEqual(record["245"]["a"], "Title")

    def test_parse_xml_to_array_applies_requested_normalization(self):
        xml = (
            '<collection xmlns="http://www.loc.gov/MARC21/slim">'
            "<record>"
            "<leader>00000nam a2200000   4500</leader>"
            '<datafield tag="245" ind1="1" ind2="0">'
            '<subfield code="a">Cafe\u0301</subfield>'
            "</datafield>"
            "</record>"
            "</collection>"
        )

        records = parse_xml_to_array(StringIO(xml), normalize_form="NFC")

        self.assertEqual(records[0]["245"]["a"], "Café")


if __name__ == "__main__":
    unittest.main()
