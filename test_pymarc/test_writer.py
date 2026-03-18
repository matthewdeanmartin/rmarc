# This file is part of rmarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import json
import os
import textwrap
import unittest
from io import BytesIO, StringIO

import rmarc


class JSONWriterTest(unittest.TestCase):
    def test_close_true(self):
        """If close_fh is true, then the file handle is also closed."""
        file_handle = StringIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.JSONWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close()
        self.assertTrue(file_handle.closed, "The file handle should close when the writer closes")

    def test_close_false(self):
        """If close_fh is false, then the file handle is NOT closed."""
        file_handle = StringIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.JSONWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close(close_fh=False)
        self.assertFalse(
            file_handle.closed,
            "The file handle should NOT close when the writer closes",
        )

    def test_writing_0_records(self):
        expected = json.loads(
            r"""
            []
        """
        )
        file_handle = StringIO()
        try:
            writer = rmarc.JSONWriter(file_handle)
            writer.close(close_fh=False)
            actual = json.loads(file_handle.getvalue())
            self.assertEqual(actual, expected)
        finally:
            file_handle.close()

    def test_writing_empty_record(self):
        expected = json.loads(
            r"""
            [
                {
                    "leader" : "          22        4500",
                    "fields" : []
                }
            ]
        """
        )
        file_handle = StringIO()
        try:
            writer = rmarc.JSONWriter(file_handle)
            record = rmarc.Record()
            writer.write(record)
            writer.close(close_fh=False)
            actual = json.loads(file_handle.getvalue())
            self.assertEqual(actual, expected)
        finally:
            file_handle.close()

    def test_writing_1_record(self):
        expected = json.loads(
            r"""
            [
                {
                    "leader" : "          22        4500",
                    "fields" : [
                        {
                            "100": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "me" }
                                ]
                            }
                        },
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "Foo /" },
                                    { "c": "by me." }
                                ]
                            }
                        }
                    ]
                }
            ]
        """
        )
        file_handle = StringIO()
        try:
            writer = rmarc.JSONWriter(file_handle)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            actual = json.loads(file_handle.getvalue())
            self.assertEqual(actual, expected)
        finally:
            file_handle.close()

    def test_writing_3_records(self):
        expected = json.loads(
            r"""
            [
                {
                    "leader" : "          22        4500",
                    "fields" : [
                        {
                            "008": "090227s2009    mau                 chi d"
                        },
                        {
                            "100": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "me" }
                                ]
                            }
                        },
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "Foo /" },
                                    { "c": "by me." }
                                ]
                            }
                        }
                    ]
                },
                {
                    "leader" : "          22        4500",
                    "fields" : [
                        {
                            "100": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "me" }
                                ]
                            }
                        },
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "Foo /" },
                                    { "c": "by me." }
                                ]
                            }
                        }
                    ]
                },
                {
                    "leader" : "          22        4500",
                    "fields" : [
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [
                                    { "a": "Foo /" },
                                    { "c": "by me." }
                                ]
                            }
                        }
                    ]
                }
            ]
        """
        )
        file_handle = StringIO()
        try:
            writer = rmarc.JSONWriter(file_handle)
            record = rmarc.Record()
            record.add_field(rmarc.Field("008", data="090227s2009    mau                 chi d"))
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            actual = json.loads(file_handle.getvalue())
            self.assertEqual(actual, expected)
        finally:
            file_handle.close()


class MARCWriterTest(unittest.TestCase):
    def test_write(self):
        """Write a record off to a file."""
        with open("test_pymarc/writer-test.dat", "wb") as file_handle:
            writer = rmarc.MARCWriter(file_handle)
            record = rmarc.Record()
            field = rmarc.Field(
                "245",
                rmarc.Indicators("0", "0"),
                [rmarc.Subfield(code="a", value="foo")],
            )
            record.add_field(field)
            writer.write(record)
            writer.close()
            self.assertTrue(
                file_handle.closed,
                "The file handle should close when the writer closes",
            )

        # read it back in
        with open("test_pymarc/writer-test.dat", "rb") as fh:
            reader = rmarc.MARCReader(fh)
            next(reader)
            reader.close()

        # remove it
        os.remove("test_pymarc/writer-test.dat")

    def test_close_true(self):
        """If close_fh is true, then the file handle is also closed."""
        file_handle = BytesIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.MARCWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close()
        self.assertTrue(file_handle.closed, "The file handle should close when the writer closes")

    def test_close_false(self):
        """If close_fh is false, then the file handle is NOT closed."""
        file_handle = BytesIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.MARCWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close(close_fh=False)
        self.assertFalse(
            file_handle.closed,
            "The file handle should NOT close when the writer closes",
        )


class TextWriterTest(unittest.TestCase):
    def test_writing_0_records(self):
        file_handle = StringIO()
        try:
            writer = rmarc.TextWriter(file_handle)
            writer.close(close_fh=False)
            self.assertEqual(
                file_handle.getvalue(),
                "",
                "Nothing should be have been written to the file handle",
            )
        finally:
            file_handle.close()

    def test_writing_1_record(self):
        expected = r"""
            =LDR            22        4500
            =100  00$ame
            =245  00$aFoo /$cby me.
        """
        expected = textwrap.dedent(expected[1:])
        file_handle = StringIO()
        try:
            writer = rmarc.TextWriter(file_handle)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_writing_3_records(self):
        expected = r"""
            =LDR            22        4500
            =008  090227s2009\\\\mau\\\\\\\\\\\\\\\\\chi\d
            =100  00$ame
            =245  00$aFoo /$cby me.

            =LDR            22        4500
            =100  00$ame
            =245  00$aFoo /$cby me.

            =LDR            22        4500
            =245  00$aFoo /$cby me.
        """
        expected = textwrap.dedent(expected[1:])
        file_handle = StringIO()
        try:
            writer = rmarc.TextWriter(file_handle)
            record = rmarc.Record()
            record.add_field(rmarc.Field("008", data="090227s2009    mau                 chi d"))
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_writing_empty_record(self):
        expected = r"""
            =LDR            22        4500
        """
        expected = textwrap.dedent(expected[1:])
        file_handle = StringIO()
        try:
            writer = rmarc.TextWriter(file_handle)
            record = rmarc.Record()
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_close_true(self):
        """If close_fh is true, then the file handle is also closed."""
        file_handle = StringIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.TextWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close()
        self.assertTrue(file_handle.closed, "The file handle should close when the writer closes")

    def test_close_false(self):
        """If close_fh is false, then the file handle is NOT closed."""
        file_handle = StringIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.TextWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close(close_fh=False)
        self.assertFalse(
            file_handle.closed,
            "The file handle should NOT close when the writer closes",
        )


class XMLWriterTest(unittest.TestCase):
    def test_writing_0_records(self):
        expected = r"""
            <?xml version="1.0" encoding="UTF-8"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
            </collection>
        """
        expected = textwrap.dedent(expected[1:]).replace("\n", "").encode()
        file_handle = BytesIO()
        try:
            writer = rmarc.XMLWriter(file_handle)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_writing_empty_record(self):
        expected = r"""
            <?xml version="1.0" encoding="UTF-8"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record>
            <leader>          22        4500</leader>
            </record>
            </collection>
        """
        expected = textwrap.dedent(expected[1:]).replace("\n", "").encode()
        file_handle = BytesIO()
        try:
            writer = rmarc.XMLWriter(file_handle)
            record = rmarc.Record()
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_writing_1_record(self):
        expected = r"""
            <?xml version="1.0" encoding="UTF-8"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record>
            <leader>          22        4500</leader>
            <datafield ind1="0" ind2="0" tag="100">
            <subfield code="a">me</subfield>
            </datafield>
            <datafield ind1="0" ind2="0" tag="245">
            <subfield code="a">Foo /</subfield>
            <subfield code="c">by me.</subfield>
            </datafield>
            </record>
            </collection>
        """
        expected = textwrap.dedent(expected[1:]).replace("\n", "").encode()
        file_handle = BytesIO()
        try:
            writer = rmarc.XMLWriter(file_handle)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_writing_3_records(self):
        expected = r"""
            <?xml version="1.0" encoding="UTF-8"?>
            <collection xmlns="http://www.loc.gov/MARC21/slim">
            <record>
            <leader>          22        4500</leader>
            <controlfield tag="008">090227s2009    mau                 chi d</controlfield>
            <datafield ind1="0" ind2="0" tag="100">
            <subfield code="a">me</subfield>
            </datafield>
            <datafield ind1="0" ind2="0" tag="245">
            <subfield code="a">Foo /</subfield>
            <subfield code="c">by me.</subfield>
            </datafield>
            </record>
            <record>
            <leader>          22        4500</leader>
            <datafield ind1="0" ind2="0" tag="100">
            <subfield code="a">me</subfield>
            </datafield>
            <datafield ind1="0" ind2="0" tag="245">
            <subfield code="a">Foo /</subfield>
            <subfield code="c">by me.</subfield>
            </datafield>
            </record>
            <record>
            <leader>          22        4500</leader>
            <datafield ind1="0" ind2="0" tag="245">
            <subfield code="a">Foo /</subfield>
            <subfield code="c">by me.</subfield>
            </datafield>
            </record>
            </collection>
        """
        expected = textwrap.dedent(expected[1:]).replace("\n", "").encode()
        file_handle = BytesIO()
        try:
            writer = rmarc.XMLWriter(file_handle)
            record = rmarc.Record()
            record.add_field(rmarc.Field("008", data="090227s2009    mau                 chi d"))
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "100",
                    rmarc.Indicators("0", "0"),
                    [rmarc.Subfield(code="a", value="me")],
                )
            )
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            record = rmarc.Record()
            record.add_field(
                rmarc.Field(
                    "245",
                    rmarc.Indicators("0", "0"),
                    [
                        rmarc.Subfield(code="a", value="Foo /"),
                        rmarc.Subfield(code="c", value="by me."),
                    ],
                )
            )
            writer.write(record)
            writer.close(close_fh=False)
            self.assertEqual(file_handle.getvalue(), expected)
        finally:
            file_handle.close()

    def test_close_true(self):
        """If close_fh is true, then the file handle is also closed."""
        file_handle = BytesIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.XMLWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close()
        self.assertTrue(file_handle.closed, "The file handle should close when the writer closes")

    def test_close_false(self):
        """If close_fh is false, then the file handle is NOT closed."""
        file_handle = BytesIO()
        self.assertFalse(file_handle.closed, "The file handle should be open")
        writer = rmarc.XMLWriter(file_handle)
        self.assertFalse(file_handle.closed, "The file handle should still be open")
        writer.close(close_fh=False)
        self.assertFalse(
            file_handle.closed,
            "The file handle should NOT close when the writer closes",
        )


if __name__ == "__main__":
    unittest.main()
