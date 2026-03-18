import unittest
from io import BytesIO

from rmarc.field import Field, Indicators, Subfield
from rmarc.leader import Leader
from rmarc.record import Record


class TestSuite3(unittest.TestCase):
    def test_field_creation_and_attributes(self):
        # Test control field
        f001 = Field(tag="001", data="12345")
        self.assertTrue(f001.is_control_field())
        self.assertEqual(f001.tag, "001")
        self.assertEqual(f001.data, "12345")
        self.assertEqual(str(f001), "=001  12345")

        # Test data field
        f245 = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[Subfield("a", "The title :"), Subfield("b", "the subtitle /"), Subfield("c", "by Author.")],
        )
        self.assertFalse(f245.is_control_field())
        self.assertEqual(f245.tag, "245")
        self.assertEqual(f245.indicator1, "1")
        self.assertEqual(f245.indicator2, "0")
        self.assertEqual(len(f245.subfields), 3)
        self.assertEqual(f245["a"], "The title :")
        self.assertEqual(f245.value(), "The title : the subtitle / by Author.")

    def test_field_modification(self):
        f = Field(tag="650", indicators=[" ", "0"], subfields=[Subfield("a", "History")])
        f.add_subfield("z", "United States")
        self.assertEqual(len(f.subfields), 2)
        self.assertEqual(f.subfields[1], Subfield("z", "United States"))

        f.indicator1 = "1"
        self.assertEqual(f.indicator1, "1")

        # Test __setitem__
        f["a"] = "Modern History"
        self.assertEqual(f["a"], "Modern History")

        # Test delete_subfield
        val = f.delete_subfield("z")
        self.assertEqual(val, "United States")
        self.assertEqual(len(f.subfields), 1)
        self.assertNotIn("z", f)

    def test_record_basic_operations(self):
        record = Record()
        self.assertEqual(len(record.fields), 0)

        f001 = Field(tag="001", data="abc123")
        record.add_field(f001)
        self.assertEqual(len(record.fields), 1)
        self.assertIn("001", record)
        self.assertEqual(record["001"].data, "abc123")

        f245 = Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "Test Record")])
        record.add_field(f245)
        self.assertEqual(record.title, "Test Record")

    def test_record_field_ordering(self):
        record = Record()
        f245 = Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "Title")])
        f001 = Field(tag="001", data="1")
        f100 = Field(tag="100", indicators=["1", " "], subfields=[Subfield("a", "Author")])

        record.add_ordered_field(f245)
        record.add_ordered_field(f001)
        record.add_ordered_field(f100)

        # Should be ordered by tag: 001, 100, 245
        tags = [f.tag for f in record.fields]
        self.assertEqual(tags, ["001", "100", "245"])

    def test_record_get_fields(self):
        record = Record()
        record.add_field(Field(tag="650", indicators=[" ", "0"], subfields=[Subfield("a", "Topic 1")]))
        record.add_field(Field(tag="650", indicators=[" ", "0"], subfields=[Subfield("a", "Topic 2")]))
        record.add_field(Field(tag="700", indicators=["1", " "], subfields=[Subfield("a", "Added Author")]))

        fields_650 = record.get_fields("650")
        self.assertEqual(len(fields_650), 2)
        self.assertEqual(fields_650[0]["a"], "Topic 1")
        self.assertEqual(fields_650[1]["a"], "Topic 2")

        all_6xx_7xx = record.get_fields("650", "700")
        self.assertEqual(len(all_6xx_7xx), 3)

    def test_isbn_property(self):
        record = Record()
        # ISBN-10
        record.add_field(Field(tag="020", subfields=[Subfield("a", "0596515050 (pbk.)")]))
        self.assertEqual(record.isbn, "0596515050")

        # ISBN-13 with dashes
        record.remove_fields("020")
        record.add_field(Field(tag="020", subfields=[Subfield("a", "978-0-596-51505-8")]))
        self.assertEqual(record.isbn, "9780596515058")

    def test_record_as_dict_and_json(self):
        record = Record()
        record.add_field(Field(tag="001", data="123"))
        record.add_field(Field(tag="245", indicators=["1", "0"], subfields=[Subfield("a", "Title")]))

        d = record.as_dict()
        self.assertEqual(d["leader"], str(record.leader))
        self.assertEqual(len(d["fields"]), 2)
        self.assertEqual(d["fields"][0], {"001": "123"})
        self.assertEqual(d["fields"][1]["245"]["ind1"], "1")

        import json

        j = record.as_json()
        self.assertEqual(json.loads(j), d)

    def test_marc_roundtrip(self):
        record = Record()
        record.add_field(Field(tag="001", data="12345"))
        record.add_field(Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "Roundtrip test")]))

        marc_data = record.as_marc()

        new_record = Record(data=marc_data)
        self.assertEqual(new_record["001"].data, "12345")
        self.assertEqual(new_record["245"]["a"], "Roundtrip test")

        # Compare leaders, but ignore record length and base address if they were empty in original
        self.assertEqual(new_record.leader.coding_scheme, record.leader.coding_scheme)
        self.assertEqual(new_record.leader.record_status, record.leader.record_status)
        self.assertEqual(new_record.leader.implementation_defined_length, record.leader.implementation_defined_length)

    def test_field_format_field(self):
        # Subject field (6xx)
        f650 = Field(
            tag="650",
            indicators=[" ", "0"],
            subfields=[Subfield("a", "History"), Subfield("x", "20th century"), Subfield("v", "Biography")],
        )
        # is_subject_field() returns True if tag starts with 6
        # format_field() for subject fields adds -- before v, x, y, z
        self.assertEqual(f650.format_field(), "History -- 20th century -- Biography")

        # Non-subject field
        f100 = Field(
            tag="100", indicators=["1", " "], subfields=[Subfield("a", "Author, A."), Subfield("d", "1900-1950")]
        )
        self.assertEqual(f100.format_field(), "Author, A. 1900-1950")

    def test_reader_writer_multi(self):
        from rmarc.reader import MARCReader
        from rmarc.writer import MARCWriter

        recs = []
        for i in range(5):
            r = Record()
            r.add_field(Field(tag="001", data=str(i)))
            r.add_field(Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", f"Title {i}")]))
            recs.append(r)

        out = BytesIO()
        writer = MARCWriter(out)
        for r in recs:
            writer.write(r)

        out.seek(0)
        reader = MARCReader(out)
        count = 0
        for r in reader:
            self.assertEqual(r["001"].data, str(count))
            self.assertEqual(r["245"]["a"], f"Title {count}")
            count += 1
        self.assertEqual(count, 5)

    def test_json_reader_writer(self):
        import json

        from rmarc.reader import JSONReader
        from rmarc.writer import JSONWriter

        r1 = Record()
        r1.add_field(Field(tag="001", data="1"))
        r1.add_field(Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "First")]))

        r2 = Record()
        r2.add_field(Field(tag="001", data="2"))
        r2.add_field(Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "Second")]))

        from io import StringIO

        out = StringIO()
        writer = JSONWriter(out)
        writer.write(r1)
        writer.write(r2)
        writer.close(close_fh=False)

        json_data = out.getvalue()
        # Verify it's a valid JSON array of 2 records
        parsed = json.loads(json_data)
        self.assertEqual(len(parsed), 2)

        # Now read it back
        reader = JSONReader(json_data)
        recs = list(reader)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["001"].data, "1")
        self.assertEqual(recs[1]["001"].data, "2")

    def test_xml_writer(self):
        import xml.etree.ElementTree as ET

        from rmarc.writer import XMLWriter

        r = Record()
        r.add_field(Field(tag="001", data="123"))
        r.add_field(Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "XML Test")]))

        out = BytesIO()
        writer = XMLWriter(out)
        writer.write(r)
        writer.close(close_fh=False)

        xml_data = out.getvalue()
        root = ET.fromstring(xml_data)
        # Should have one <record> under <collection>
        self.assertEqual(root.tag, "{http://www.loc.gov/MARC21/slim}collection")
        record_node = root.find("{http://www.loc.gov/MARC21/slim}record")
        self.assertIsNotNone(record_node)

        # Check controlfield 001
        cf = record_node.find("{http://www.loc.gov/MARC21/slim}controlfield[@tag='001']")
        self.assertEqual(cf.text, "123")

    def test_record_more_properties(self):
        r = Record()
        # Author
        r.add_field(Field(tag="100", indicators=["1", " "], subfields=[Subfield("a", "Smith, John.")]))
        self.assertEqual(r.author, "Smith, John.")

        # Publisher/Pubyear
        r.add_field(
            Field(tag="260", indicators=[" ", " "], subfields=[Subfield("b", "O'Reilly"), Subfield("c", "2023")])
        )
        self.assertEqual(r.publisher, "O'Reilly")
        self.assertEqual(r.pubyear, "2023")

        # Subjects
        r.add_field(Field(tag="650", indicators=[" ", "0"], subfields=[Subfield("a", "Computers")]))
        r.add_field(Field(tag="651", indicators=[" ", "0"], subfields=[Subfield("a", "Silicon Valley")]))
        self.assertEqual(len(r.subjects), 2)

    def test_field_indicators_validation(self):
        # Indicators should be 2 characters
        with self.assertRaises(ValueError):
            Field(tag="245", indicators=["1", "2", "3"])

        f = Field(tag="245")
        self.assertEqual(f.indicator1, " ")
        self.assertEqual(f.indicator2, " ")

        f.indicator1 = "1"
        self.assertEqual(f.indicator1, "1")
        self.assertEqual(f.indicator2, " ")

    def test_field_get_subfields(self):
        f = Field(
            tag="245", subfields=[Subfield("a", "Main title"), Subfield("b", "Subtitle"), Subfield("a", "Extra title")]
        )
        vals = f.get_subfields("a")
        self.assertEqual(vals, ["Main title", "Extra title"])

        vals = f.get_subfields("a", "b")
        self.assertEqual(vals, ["Main title", "Subtitle", "Extra title"])

    def test_record_remove_fields(self):
        r = Record()
        r.add_field(Field(tag="001", data="1"))
        r.add_field(Field(tag="020", subfields=[Subfield("a", "123")]))
        r.add_field(Field(tag="020", subfields=[Subfield("a", "456")]))

        r.remove_fields("020")
        self.assertEqual(len(r.get_fields("020")), 0)
        self.assertEqual(len(r.fields), 1)

    def test_record_as_json_kwargs(self):
        r = Record()
        r.add_field(Field(tag="001", data="1"))
        j = r.as_json(indent=2)
        self.assertIn("\n  ", j)

    def test_field_subfields_as_dict(self):
        f = Field(
            tag="245", subfields=[Subfield("a", "Title"), Subfield("b", "Subtitle"), Subfield("a", "Alternative Title")]
        )
        d = f.subfields_as_dict()
        self.assertEqual(d["a"], ["Title", "Alternative Title"])
        self.assertEqual(d["b"], ["Subtitle"])

    def test_field_iter(self):
        subfields = [Subfield("a", "1"), Subfield("b", "2")]
        f = Field(tag="245", subfields=subfields)
        iterated = list(f)
        self.assertEqual(iterated, subfields)

    def test_record_iter(self):
        f1 = Field(tag="001", data="1")
        f2 = Field(tag="245", indicators=["0", "0"], subfields=[Subfield("a", "Title")])
        r = Record()
        r.add_field(f1, f2)
        iterated = list(r)
        self.assertEqual(iterated, [f1, f2])

    def test_record_remove_specific_field(self):
        r = Record()
        f1 = Field(tag="020", subfields=[Subfield("a", "123")])
        f2 = Field(tag="020", subfields=[Subfield("a", "456")])
        r.add_field(f1, f2)

        r.remove_field(f1)
        self.assertEqual(len(r.get_fields("020")), 1)
        self.assertEqual(r.get_fields("020")[0], f2)

    def test_record_get_default(self):
        r = Record()
        self.assertIsNone(r.get("999"))
        default_f = Field(tag="999", data="default")
        self.assertEqual(r.get("999", default_f), default_f)

    def test_record_add_grouped_field(self):
        r = Record()
        f1 = Field(tag="100", data="Author")
        f2 = Field(tag="245", data="Title")
        f3 = Field(tag="110", data="Corporate")

        r.add_grouped_field(f1)
        r.add_grouped_field(f2)
        r.add_grouped_field(f3)

        # add_grouped_field groups by the first digit of the tag
        # 100 and 110 should be together
        tags = [f.tag for f in r.fields]
        # Depending on implementation, it might be 100, 110, 245 or 100, 245, 110?
        # Let's check _sort_fields logic in record.py:
        # tag = int(field.tag[0]) if mode == "grouped" else int(field.tag)
        # It inserts before the first field that has a larger "tag" (first digit)

        # 1. add 100: [100]
        # 2. add 245: tag=2. 100 has tag=1. 2 > 1. Appends: [100, 245]
        # 3. add 110: tag=1. 100 has tag=1. 1 is not > 1. 245 has tag=2. 2 > 1. Inserts before 245: [100, 110, 245]
        self.assertEqual(tags, ["100", "110", "245"])

    def test_title_properties(self):
        r = Record()
        r.add_field(
            Field(
                tag="245",
                indicators=["1", "0"],
                subfields=[Subfield("a", "Main Title :"), Subfield("b", "Subtitle /"), Subfield("c", "Author.")],
            )
        )
        self.assertEqual(r.title, "Main Title : Subtitle /")

        r.add_field(
            Field(
                tag="222",
                indicators=[" ", "0"],
                subfields=[Subfield("a", "Key Title :"), Subfield("b", "Key Subtitle")],
            )
        )
        self.assertEqual(r.issn_title, "Key Title : Key Subtitle")


if __name__ == "__main__":
    unittest.main()
