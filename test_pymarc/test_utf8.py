# This file is part of rmarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import os
import unittest

import rmarc
from test_pymarc import fixture_path


class MARCUnicodeTest(unittest.TestCase):
    def test_read_utf8(self):
        self.field_count = 0

        def process_xml(record):
            for _ in record.get_fields():
                self.field_count += 1

        rmarc.map_xml(process_xml, str(fixture_path("utf8.xml")))
        self.assertEqual(self.field_count, 8)

    def test_copy_utf8(self):
        with fixture_path("write-utf8-test.dat").open("wb") as fh:
            writer = rmarc.MARCWriter(fh)
            new_record = rmarc.Record(to_unicode=True, force_utf8=True)

            def process_xml(record):
                new_record.leader = record.leader

                for field in record.get_fields():
                    new_record.add_field(field)

            rmarc.map_xml(process_xml, str(fixture_path("utf8.xml")))

            try:
                writer.write(new_record)
                writer.close()

            finally:
                # remove it
                os.remove(fixture_path("write-utf8-test.dat"))

    def test_combining_diacritic(self):
        """Issue 74: raises UnicodeEncodeError on Python 2."""
        with fixture_path("diacritic.dat").open("rb") as fh:
            reader = rmarc.MARCReader(fh)
            record = next(reader)
            str(record)

    def test_utf8_strict_raises_on_invalid(self):
        """strict UTF-8 handling must raise UnicodeDecodeError on invalid bytes."""
        # Build a valid UTF-8 MARC record, then inject an invalid byte
        record = rmarc.Record()
        record.add_field(rmarc.Field(tag="001", data="test"))
        record.add_field(
            rmarc.Field(
                tag="245",
                indicators=rmarc.field.Indicators("0", "0"),
                subfields=[rmarc.field.Subfield(code="a", value="Hello World")],
            )
        )
        good_marc = record.as_marc()
        # Replace 'W' with 0xFF (invalid UTF-8 start byte), keeping same length
        idx = good_marc.index(b"W")
        bad_marc = good_marc[:idx] + b"\xff" + good_marc[idx + 1 :]

        with self.assertRaises(UnicodeDecodeError):
            rmarc.Record(data=bad_marc, to_unicode=True, utf8_handling="strict")

    def test_utf8_replace_on_invalid(self):
        """replace UTF-8 handling must substitute replacement characters."""
        record = rmarc.Record()
        record.add_field(rmarc.Field(tag="001", data="test"))
        record.add_field(
            rmarc.Field(
                tag="245",
                indicators=rmarc.field.Indicators("0", "0"),
                subfields=[rmarc.field.Subfield(code="a", value="Hello World")],
            )
        )
        good_marc = record.as_marc()
        idx = good_marc.index(b"W")
        bad_marc = good_marc[:idx] + b"\xff" + good_marc[idx + 1 :]

        r = rmarc.Record(data=bad_marc, to_unicode=True, utf8_handling="replace")
        val = r["245"]["a"]
        self.assertIn("\ufffd", val)

    def test_utf8_ignore_on_invalid(self):
        """ignore UTF-8 handling must drop invalid bytes silently."""
        record = rmarc.Record()
        record.add_field(rmarc.Field(tag="001", data="test"))
        record.add_field(
            rmarc.Field(
                tag="245",
                indicators=rmarc.field.Indicators("0", "0"),
                subfields=[rmarc.field.Subfield(code="a", value="Hello World")],
            )
        )
        good_marc = record.as_marc()
        idx = good_marc.index(b"W")
        bad_marc = good_marc[:idx] + b"\xff" + good_marc[idx + 1 :]

        r = rmarc.Record(data=bad_marc, to_unicode=True, utf8_handling="ignore")
        val = r["245"]["a"]
        self.assertNotIn("\ufffd", val)
        self.assertIn("Hello", val)


if __name__ == "__main__":
    unittest.main()
