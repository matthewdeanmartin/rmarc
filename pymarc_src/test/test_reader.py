# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import re
import tempfile
from unittest import TestCase

import pymarc
from pymarc import Field, Record, exceptions

# TODO: these tests are overly complicated and should be converted over to using
# pytest functions possibly in separate modules instead of getting fancy with inheritence


class MARCReaderBaseTest:
    def test_iterator(self):
        count = 0
        for _ in self.reader:  # type: ignore
            count += 1
        self.assertEqual(count, 10, "found expected number of MARC21 records")  # type: ignore

    def test_string(self):
        # basic test of stringification
        starts_with_leader = re.compile("^=LDR")
        has_numeric_tag = re.compile(r"\n=\d\d\d ")
        for record in self.reader:  # type: ignore
            text = str(record)
            self.assertTrue(starts_with_leader.search(text), "got leader")  # type: ignore
            self.assertTrue(has_numeric_tag.search(text), "got a tag")  # type: ignore


class MARCReaderFileTest(TestCase, MARCReaderBaseTest):
    """Tests MARCReader which provides iterator based access to a MARC file."""

    def setUp(self):
        self.reader = pymarc.MARCReader(open("test/test.dat", "rb"))  # noqa: SIM115

    def tearDown(self):
        if self.reader:
            self.reader.close()

    def test_map_records(self):
        self.count = 0

        def f(r):
            self.count += 1

        with open("test/test.dat", "rb") as fh:
            pymarc.map_records(f, fh)
            self.assertEqual(self.count, 10, "map_records appears to work")

    def test_multi_map_records(self):
        self.count = 0

        def f(r):
            self.count += 1

        with open("test/test.dat", "rb") as fh1, open("test/test.dat", "rb") as fh2:
            pymarc.map_records(f, fh1, fh2)
            self.assertEqual(self.count, 20, "map_records appears to work")

    def test_bad_subfield(self):
        with open("test/bad_subfield_code.dat", "rb") as fh:
            reader = pymarc.MARCReader(fh)
            record = next(reader)
            assert isinstance(record, Record)
            self.assertEqual(record["245"]["a"], "ActivePerl with ASP and ADO /")

    def test_bad_indicator(self):
        with open("test/bad_indicator.dat", "rb") as fh:
            reader = pymarc.MARCReader(fh)
            record = next(reader)
            assert isinstance(record, Record)
            self.assertEqual(record["245"]["a"], "Aristocrats of color :")

    def test_regression_45(self):
        # https://github.com/edsu/pymarc/issues/45
        with open("test/regression45.dat", "rb") as fh:
            reader = pymarc.MARCReader(fh)
            record = next(reader)
            assert isinstance(record, Record)
            self.assertEqual(record["752"]["a"], "Russian Federation")
            self.assertEqual(record["752"]["b"], "Kostroma Oblast")
            self.assertEqual(record["752"]["d"], "Kostroma")

    # inherit same tests from MARCReaderBaseTest


class MARCReaderStringTest(TestCase, MARCReaderBaseTest):
    def setUp(self):
        with open("test/test.dat", "rb") as fh:
            raw = fh.read()
            fh.close()

        self.reader = pymarc.reader.MARCReader(raw)

    # inherit same tests from MARCReaderBaseTest


class MARCReaderFilePermissiveTest(TestCase):
    """Tests MARCReader which provides iterator based access in a permissive way."""

    def setUp(self):
        self.reader = pymarc.MARCReader(open("test/bad_records.mrc", "rb"))  # noqa: SIM115

    def tearDown(self):
        if self.reader:
            self.reader.close()

    def test_permissive_mode(self):
        """Test permissive mode.

        In bad_records.mrc we expect following records in the given order :

        * working record
        * BaseAddressInvalid (base_address (99937) >= len(marc))
        * BaseAddressNotFound (base_address (00000) <= 0)
        * RecordDirectoryInvalid (len(directory) % DIRECTORY_ENTRY_LEN != 0)
        * UnicodeDecodeError (directory with non ascii code (245ù0890000))
        * ValueError (base_address with literal (f0037))
        * last record should be ok
        """
        expected_exceptions = [
            None,
            exceptions.BaseAddressInvalid,
            exceptions.BaseAddressNotFound,
            exceptions.RecordDirectoryInvalid,
            UnicodeDecodeError,
            ValueError,
            exceptions.NoFieldsFound,
            None,
            exceptions.TruncatedRecord,
        ]
        for exception_type in expected_exceptions:
            record = next(self.reader)
            self.assertIsNotNone(self.reader.current_chunk)
            if exception_type is None:
                assert record is not None
                self.assertIsNone(self.reader.current_exception)
                self.assertEqual(record["245"]["a"], "The pragmatic programmer : ")
                self.assertEqual(record["245"]["b"], "from journeyman to master /")
                self.assertEqual(record["245"]["c"], "Andrew Hunt, David Thomas.")
            else:
                self.assertIsNone(
                    record,
                    "expected parsing error with the following "
                    f"exception {exception_type!r}",
                )
                self.assertTrue(
                    isinstance(self.reader.current_exception, exception_type),
                    f"expected {exception_type!r} exception, "
                    f"received: {self.reader.current_exception!r}",
                )


class TestTruncatedData(TestCase):
    def test_empty_data(self):
        count = 0
        for record in pymarc.MARCReader(b""):
            count += 1
            self.assertIsNone(record)
        self.assertEqual(count, 0, "expected no records from empty data")

    def test_partial_length(self):
        count = 0
        reader = pymarc.MARCReader(b"0012")
        for record in reader:
            count += 1
            self.assertIsNone(record, "expected one None record")
        self.assertEqual(count, 1, "expected one None record")
        self.assertEqual(reader.current_chunk, b"0012")
        self.assertTrue(
            isinstance(reader.current_exception, exceptions.TruncatedRecord),
            f"expected {exceptions.TruncatedRecord} exception, "
            f"received: {type(reader.current_exception)}",
        )

    def test_bad_length(self):
        count = 0
        reader = pymarc.MARCReader(b"0012X")
        for record in reader:
            count += 1
            self.assertIsNone(record, "expected one None record")
        self.assertEqual(count, 1, "expected one None record")
        self.assertEqual(reader.current_chunk, b"0012X")
        self.assertTrue(
            isinstance(reader.current_exception, exceptions.RecordLengthInvalid),
            f"expected {exceptions.RecordLengthInvalid} exception, "
            f"received: {type(reader.current_exception)}",
        )

    def test_partial_data(self):
        count = 0
        data = b"00120cam"
        reader = pymarc.MARCReader(data)
        for record in reader:
            count += 1
            self.assertIsNone(record, "expected one None record")
        self.assertEqual(count, 1, "expected one None record")
        self.assertEqual(
            reader.current_chunk,
            data,
            f"expected {data}, received {reader.current_chunk}",
        )
        self.assertTrue(
            isinstance(reader.current_exception, exceptions.TruncatedRecord),
            f"expected {exceptions.TruncatedRecord} exception, "
            f"received: {type(reader.current_exception)}",
        )

    def test_missing_end_of_record(self):
        count = 0
        data = b"00006 "
        reader = pymarc.MARCReader(data)
        for record in reader:
            count += 1
            self.assertIsNone(record, "expected one None record")
        self.assertEqual(count, 1, "expected one None record")
        self.assertEqual(
            reader.current_chunk,
            data,
            f"expected {data}, received {reader.current_chunk}",
        )
        self.assertTrue(
            isinstance(reader.current_exception, exceptions.EndOfRecordNotFound),
            f"expected {exceptions.EndOfRecordNotFound} exception, "
            f"received: {type(reader.current_exception)}",
        )


class MARCMakerReaderTest(TestCase, MARCReaderBaseTest):
    """Tests MARCMakerReader which provides iterator based access to a text file."""

    @classmethod
    def setUpClass(cls):
        with open("test/test.dat", "rb") as fh:
            cls.records = [str(record) for record in pymarc.MARCReader(fh)]

    def setUp(self):
        self.reader = pymarc.MARCMakerReader("\n".join(self.records))

    def test_round_trip(self):
        for index, record in enumerate(self.reader):
            self.assertEqual(
                str(record), self.records[index], "records should be identical"
            )

    def test_parse_line_leader(self):
        leader = self.reader._parse_line("=LDR  00755cam  22002414a 4500")
        self.assertEqual(str(leader), "00755cam  22002414a 4500")

    def test_parse_line_control_field(self):
        field = self.reader._parse_line("=008  010314s1999fr||||||||||||||||fre")
        assert isinstance(field, Field)
        self.assertEqual(field.tag, "008")
        self.assertEqual(field.data, "010314s1999fr||||||||||||||||fre")

    def test_parse_line_data_field(self):
        field = self.reader._parse_line("=028  01$aSTMA 8007$bTamla Motown Records")
        assert isinstance(field, Field)
        self.assertEqual(field.tag, "028")
        self.assertEqual(field.indicator1, "0")
        self.assertEqual(field.indicator2, "1")
        self.assertEqual(field["a"], "STMA 8007")
        self.assertEqual(field["b"], "Tamla Motown Records")

    def test_parse_line_startswith_equal_sign(self):
        with self.assertRaises(ValueError) as cm:
            self.reader._parse_line("028  01$aSTMA 8007$bTamla Motown Records")
        self.assertEqual(str(cm.exception), 'Line should start with a "=".')

    def test_parse_line_spaces_separator(self):
        with self.assertRaises(ValueError) as cm:
            self.reader._parse_line("=028 01$aSTMA 8007$bTamla Motown Records")
        self.assertEqual(
            str(cm.exception),
            "Tag should be separated from the rest of the field by two spaces.",
        )

    def test_invalid_lines(self):
        lines = [
            "=LDR 00755cam  22002414a 4500",
            "LDR  00755cam  22002414a 4500",
            "=008",
            "=009 00755cam",
            "=999",
        ]
        for line in lines:
            with self.subTest(line=line):
                reader = pymarc.MARCMakerReader(line)
                with self.assertRaises(pymarc.exceptions.PymarcException) as cm:
                    next(reader)
                self.assertEqual(str(cm.exception), f'Unable to parse line "{line}"')

    def test_open_from_file(self):
        for encoding in ["utf-8", "ISO-8859-1", None]:
            with self.subTest(encoding=encoding):
                with tempfile.NamedTemporaryFile("w", encoding=encoding) as tmp:
                    tmp.write("\n".join(self.records))
                    tmp.flush()
                    reader = pymarc.MARCMakerReader(tmp.name, encoding=encoding)
                record = next(reader)
                self.assertEqual(
                    str(record), self.records[0], "records should be identical"
                )
