# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import json
import unittest

import pymarc


class JsonReaderTest(unittest.TestCase):
    def setUp(self):
        with open("test/test.json") as fh:
            self.in_json = json.load(fh, strict=False)

        self._js_fh = open("test/test.json").read()  # noqa: SIM115
        self.reader = pymarc.JSONReader(self._js_fh)

    def testRoundtrip(self):
        """Test from and to json.

        Tests that result of loading records from the test file
        produces objects deeply equal to the result of loading
        marc-in-json files directly
        """
        recs = list(self.reader)
        self.assertEqual(
            len(self.in_json), len(recs), "Incorrect number of records found"
        )
        for i, rec in enumerate(recs):
            deserialized = json.loads(rec.as_json(), strict=False)
            comp = self.in_json[i]
            self.assertEqual(comp, deserialized)

    def testOneRecord(self):
        """Tests case when in source json there is only 1 record not wrapped in list."""
        data = json.dumps(self.in_json[0])
        reader = pymarc.JSONReader(data)
        self.assertEqual([rec.as_dict() for rec in reader][0], self.in_json[0])


class JsonTest(unittest.TestCase):
    def setUp(self):
        self._test_fh = open("test/test.dat", "rb")  # noqa: SIM115
        self.reader = pymarc.MARCReader(self._test_fh)
        self._record = pymarc.Record()
        field = pymarc.Field(
            tag="245",
            indicators=pymarc.Indicators("1", "0"),
            subfields=[
                pymarc.Subfield(code="a", value="Python"),
                pymarc.Subfield(code="c", value="Guido"),
            ],
        )
        self._record.add_field(field)

    def tearDown(self) -> None:
        self._test_fh.close()

    def test_as_dict_single(self):
        _expected = {
            "fields": [
                {
                    "245": {
                        "ind1": "1",
                        "ind2": "0",
                        "subfields": [{"a": "Python"}, {"c": "Guido"}],
                    }
                }
            ],
            "leader": "          22        4500",
        }
        self.assertEqual(_expected, self._record.as_dict())

    def test_as_json_types(self):
        rd = self._record.as_dict()
        assert isinstance(rd, dict)
        assert isinstance(rd["leader"], str)
        assert isinstance(rd["fields"], list)
        assert isinstance(rd["fields"][0], dict)
        assert isinstance(rd["fields"][0], dict)
        assert isinstance(rd["fields"][0]["245"], dict)
        assert isinstance(rd["fields"][0]["245"]["ind1"], str)
        assert isinstance(rd["fields"][0]["245"]["ind2"], str)
        assert isinstance(rd["fields"][0]["245"]["subfields"], list)
        assert isinstance(rd["fields"][0]["245"]["subfields"][0], dict)
        assert isinstance(rd["fields"][0]["245"]["subfields"][0]["a"], str)
        assert isinstance(rd["fields"][0]["245"]["subfields"][1]["c"], str)

    def test_as_json_simple(self):
        record = json.loads(self._record.as_json())

        self.assertTrue("leader" in record)
        self.assertEqual(record["leader"], "          22        4500")

        self.assertTrue("fields" in record)
        self.assertTrue("245" in record["fields"][0])
        self.assertEqual(
            record["fields"][0]["245"],
            {
                "subfields": [{"a": "Python"}, {"c": "Guido"}],
                "ind2": "0",
                "ind1": "1",
            },
        )

    def test_as_json_multiple(self):
        for record in self.reader:
            assert record
            self.assertEqual(dict, json.loads(record.as_json()).__class__)


class JsonParse(unittest.TestCase):
    def setUp(self):
        self._one_dat_fh = open("test/one.dat", "rb")  # noqa: SIM115
        self._one_js_fh = open("test/one.json")  # noqa: SIM115
        self._batch_xml_fh = open("test/batch.xml")  # noqa: SIM115
        self._batch_js_fh = open("test/batch.json")  # noqa: SIM115

        self.reader_dat = pymarc.MARCReader(self._one_dat_fh)
        self.parse_json = pymarc.parse_json_to_array(self._one_js_fh)
        self.batch_xml = pymarc.parse_xml_to_array(self._batch_xml_fh)
        self.batch_json = pymarc.parse_json_to_array(self._batch_js_fh)

    def tearDown(self) -> None:
        self._one_dat_fh.close()
        self._one_js_fh.close()
        self._batch_js_fh.close()
        self._batch_xml_fh.close()

    def testRoundtrip(self):
        recs = list(self.reader_dat)
        self.assertEqual(
            len(self.parse_json), len(recs), "Incorrect number of records found"
        )
        for from_dat, from_json in zip(recs, self.parse_json, strict=False):
            assert from_dat
            assert from_json
            self.assertEqual(
                from_dat.as_marc(), from_json.as_marc(), "Incorrect Record"
            )

    def testParseJsonXml(self):
        self.assertEqual(
            len(self.batch_json),
            len(self.batch_xml),
            "Incorrect number of parse records found",
        )
        for from_dat, from_json in zip(self.batch_json, self.batch_xml, strict=False):
            self.assertEqual(
                from_dat.as_marc(), from_json.as_marc(), "Incorrect Record"
            )


if __name__ == "__main__":
    unittest.main()
