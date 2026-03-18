# This file is part of rmarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

import os
import tempfile
import unittest

from rmarc import Field, Indicators, Leader, MARCReader, MARCWriter, RawField, Record, Subfield, marc8_to_unicode
from test_pymarc import fixture_path


class MARC8Test(unittest.TestCase):
    def test_marc8_reader(self):
        with fixture_path("marc8.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=False)
            r = next(reader)
            assert isinstance(r, Record)
            self.assertIsInstance(r["240"], RawField)
            utitle = r["240"]["a"]
            self.assertEqual(type(utitle), bytes)
            self.assertEqual(utitle, b"De la solitude \xe1a la communaut\xe2e.")

    def test_marc8_reader_to_unicode(self):
        with fixture_path("marc8.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True)
            r = next(reader)
            assert isinstance(r, Record)
            utitle = r["240"]["a"]
            self.assertEqual(type(utitle), str)
            self.assertEqual(utitle, "De la solitude \xe0 la communaut\xe9.")

    def test_marc8_reader_to_1251(self):
        with fixture_path("1251.dat").open("rb") as fh:
            reader = MARCReader(fh, file_encoding="cp1251")
            r = next(reader)
            assert isinstance(r, Record)
            utitle = r["245"]["a"]
            self.assertEqual(type(utitle), str)
            self.assertEqual(utitle, "Основы гидравлического расчета инженерных сетей")

    def test_marc8_reader_to_1251_without_1251(self):
        with fixture_path("1251.dat").open("rb") as fh:
            reader = MARCReader(fh)
            try:
                r = next(reader)
                r = next(reader)
                assert isinstance(r, Record)
                utitle = r["245"]["a"]
                self.assertEqual(type(utitle), str)
                self.assertEqual(utitle, "Психологический тренинг с подростками")
            except AssertionError:
                self.assertTrue("Was enable to decode invalid MARC")

    def test_marc8_reader_to_unicode_bad_eacc_sequence(self):
        with fixture_path("bad_eacc_encoding.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True, hide_utf8_warnings=True)
            record = next(reader)
            assert isinstance(record, Record)
            self.assertEqual(len(record["880"]["a"]), 12)
            self.assertTrue(record["880"]["a"].endswith(" "))

    def test_marc8_reader_to_unicode_bad_escape(self):
        with fixture_path("bad_marc8_escape.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True)
            r = next(reader)
            assert isinstance(r, Record)
            upublisher = r["260"]["b"]
            self.assertEqual(type(upublisher), str)
            self.assertEqual(upublisher, "La Soci\xe9t\x1b,")

    def test_marc8_read_write(self):
        with fixture_path("marc8.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=False)
            records = list(reader)
            self.assertEqual(len(records), 1)
            r = records[0]
            assert isinstance(r, Record)
            self.assertIsInstance(r["240"], RawField)

        with tempfile.TemporaryFile() as fh:
            fh.write(r.as_marc())

            fh.seek(0)

            reader = MARCReader(fh, to_unicode=False)
            r = next(reader)
            assert isinstance(r, Record)
            self.assertIsInstance(r["240"], RawField)
            utitle = r["240"]["a"]
            self.assertEqual(type(utitle), bytes)
            self.assertEqual(utitle, b"De la solitude \xe1a la communaut\xe2e.")

    def test_marc8_to_unicode(self):
        with (
            fixture_path("test_marc8.txt").open("rb") as marc8_file,
            fixture_path("test_utf8.txt").open("rb") as utf8_file,
        ):
            count = 0

            while True:
                marc8 = marc8_file.readline().strip(b"\r\n")
                utf8 = utf8_file.readline().strip(b"\r\n")
                if marc8 == b"" or utf8 == b"":
                    break
                count += 1
                self.assertEqual(marc8_to_unicode(marc8).encode("utf8"), utf8)

            self.assertEqual(count, 1515)

    def test_writing_unicode(self):
        record = Record()
        record.add_field(Field("245", Indicators("1", "0"), [Subfield(code="a", value=chr(0x1234))]))
        record.leader = Leader("         a              ")
        with fixture_path("foo").open("wb") as fh:
            writer = MARCWriter(fh)
            writer.write(record)

        with fixture_path("foo").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True)
            record = next(reader)
            assert isinstance(record, Record)
            self.assertEqual(record["245"]["a"], chr(0x1234))

        os.remove(fixture_path("foo"))

    def test_reading_utf8_with_flag(self):
        with fixture_path("utf8_with_leader_flag.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=False)
            record = next(reader)
            assert isinstance(record, Record)
            utitle = record["240"]["a"]
            self.assertEqual(type(utitle), bytes)
            self.assertEqual(utitle, b"De la solitude a\xcc\x80 la communaute\xcc\x81.")

        with fixture_path("utf8_with_leader_flag.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True)
            record = next(reader)
            assert isinstance(record, Record)
            utitle = record["240"]["a"]
            self.assertEqual(type(utitle), str)
            self.assertEqual(
                utitle,
                "De la solitude a" + chr(0x0300) + " la communaute" + chr(0x0301) + ".",
            )

    def test_reading_utf8_without_flag(self):
        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=False)
            record = next(reader)
            assert isinstance(record, Record)
            utitle = record["240"]["a"]
            self.assertEqual(type(utitle), bytes)
            self.assertEqual(utitle, b"De la solitude a\xcc\x80 la communaute\xcc\x81.")

        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True, hide_utf8_warnings=True)
            record = next(reader)
            assert isinstance(record, Record)
            utitle = record["240"]["a"]
            self.assertEqual(type(utitle), str)
            # unless you force utf-8 characters will get lost and
            # warnings will appear in the terminal
            self.assertEqual(utitle, "De la solitude a   la communaute .")

        # force reading as utf-8
        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            reader = MARCReader(fh, to_unicode=True, force_utf8=True, hide_utf8_warnings=True)
            record = next(reader)
            assert isinstance(record, Record)
            utitle = record["240"]["a"]
            self.assertEqual(type(utitle), str)
            self.assertEqual(
                utitle,
                "De la solitude a" + chr(0x0300) + " la communaute" + chr(0x0301) + ".",
            )

    def test_record_create_force_utf8(self, force_utf8=True):
        r = Record(force_utf8=True)
        self.assertEqual(r.leader[9], "a")

    def test_subscript_2(self):
        self.assertEqual(marc8_to_unicode(b"CO\x1bb2\x1bs is a gas"), "CO\u2082 is a gas")
        self.assertEqual(marc8_to_unicode(b"CO\x1bb2\x1bs"), "CO\u2082")

    def test_eszett_euro(self):
        # MARC-8 mapping: Revised June 2004 to add the Eszett (M+C7) and the
        # Euro Sign (M+C8) to the MARC-8 set.
        self.assertEqual(
            marc8_to_unicode(b"ESZETT SYMBOL: \xc7 is U+00DF"),
            "ESZETT SYMBOL: \u00df is U+00DF",
        )
        self.assertEqual(
            marc8_to_unicode(b"EURO SIGN: \xc8 is U+20AC"),
            "EURO SIGN: \u20ac is U+20AC",
        )

    def test_alif(self):
        # MARC-8 mapping: Revised March 2005 to change the mapping from MARC-8
        # to Unicode for the Alif (M+2E) from U+02BE to U+02BC.
        self.assertEqual(marc8_to_unicode(b"ALIF: \xae is U+02BC"), "ALIF: \u02bc is U+02BC")


if __name__ == "__main__":
    unittest.main()
