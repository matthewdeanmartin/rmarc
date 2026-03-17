# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import unittest
from io import BytesIO

from pymarc.exceptions import RecordLeaderInvalid
from pymarc.marcxml import map_xml, parse_xml_to_array, record_to_xml
from pymarc.reader import MARCReader
from pymarc.record import Record


class XmlTest(unittest.TestCase):
    def test_map_xml(self):
        self.seen = 0

        def count(record):
            self.seen += 1

        map_xml(count, "test/batch.xml")
        self.assertEqual(2, self.seen)

    def test_multi_map_xml(self):
        self.seen = 0

        def count(record):
            self.seen += 1

        map_xml(count, "test/batch.xml", "test/batch.xml")
        self.assertEqual(4, self.seen)

    def test_parse_to_array(self):
        records = parse_xml_to_array("test/batch.xml")
        self.assertEqual(len(records), 2)

        # should've got two records
        self.assertEqual(type(records[0]), Record)
        self.assertEqual(type(records[1]), Record)

        # first record should have 18 fields
        record = records[0]
        self.assertEqual(len(record.get_fields()), 18)

        # check the content of a control field
        self.assertEqual(record["008"].data, "910926s1957    nyuuun              eng  ")

        # check a data field with subfields
        field = record["245"]
        self.assertEqual(field.indicator1, "0")
        self.assertEqual(field.indicator2, "4")
        self.assertEqual(field["a"], "The Great Ray Charles")
        self.assertEqual(field["h"], "[sound recording].")

    def test_xml(self):
        # read in xml to a record
        record1 = parse_xml_to_array("test/batch.xml")[0]
        # generate xml
        xml = record_to_xml(record1)
        # parse generated xml
        record2 = parse_xml_to_array(BytesIO(xml))[0]

        # compare original and resulting record
        self.assertEqual(record1.leader.leader, record2.leader.leader)

        field1 = record1.get_fields()
        field2 = record2.get_fields()
        self.assertEqual(len(field1), len(field2))

        pos = 0
        while pos < len(field1):
            self.assertEqual(field1[pos].tag, field2[pos].tag)
            if field1[pos].control_field:
                self.assertEqual(field1[pos].data, field2[pos].data)
            else:
                self.assertEqual(
                    field1[pos].get_subfields(), field2[pos].get_subfields()
                )
                self.assertEqual(field1[pos].indicators, field2[pos].indicators)
            pos += 1

    def test_strict(self):
        with open("test/batch.xml") as fh:
            a = parse_xml_to_array(fh, strict=True)
            self.assertEqual(len(a), 2)

    def test_xml_namespaces(self):
        """Tests the 'namespace' parameter of the record_to_xml() method."""
        # get a test record
        with open("test/test.dat", "rb") as fh:
            record = next(MARCReader(fh))
            # record_to_xml() with quiet set to False should generate errors
            #   and write them to sys.stderr
            xml = record_to_xml(record, namespace=False)
            # look for the xmlns in the written xml, should be -1
            self.assertFalse(b'xmlns="http://www.loc.gov/MARC21/slim"' in xml)

            # record_to_xml() with quiet set to True should not generate errors
            xml = record_to_xml(record, namespace=True)
            # look for the xmlns in the written xml, should be >= 0
            self.assertTrue(b'xmlns="http://www.loc.gov/MARC21/slim"' in xml)

    def test_bad_tag(self):
        with open("test/bad_tag.xml") as fh:
            self.assertRaises(RecordLeaderInvalid, parse_xml_to_array, fh)


if __name__ == "__main__":
    unittest.main()
