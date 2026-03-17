# This file is part of rmarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.
import unittest

from rmarc.exceptions import (
    BaseAddressInvalid,
    FieldNotFound,
    MissingLinkedFields,
    RecordLeaderInvalid,
)
from rmarc.field import Field, Indicators, Subfield
from rmarc.leader import Leader
from rmarc.reader import MARCReader
from rmarc.record import Record


class RecordTest(unittest.TestCase):
    def test_add_field(self):
        record = Record()
        field = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="a", value="Python"),
                Subfield(code="c", value="Guido"),
            ],
        )
        record.add_field(field)
        self.assertTrue(field in record.fields, msg="found field")

    def test_fields(self):
        record = Record(
            fields=[
                Field(
                    tag="245",
                    indicators=Indicators("1", "0"),
                    subfields=[
                        Subfield(code="a", value="Python"),
                        Subfield(code="c", value="Guido"),
                    ],
                ),
                Field(tag="260", subfields=[Subfield(code="a", value="Amsterdam")]),
            ]
        )
        self.assertTrue(record["245"]["a"] == "Python")
        self.assertTrue(record["260"]["a"] == "Amsterdam")

    def test_remove_field(self):
        record = Record()
        field = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="a", value="Python"),
                Subfield(code="c", value="Guido"),
            ],
        )
        record.add_field(field)
        self.assertEqual(record["245"]["a"], "Python")

        # try removing a field that exists
        record.remove_field(field)
        self.assertEqual(record.get("245"), None)

        # try removing a field that doesn't exist
        field = Field("001", data="abcd1234")
        self.assertRaises(FieldNotFound, record.remove_field, field)

    def test_quick_access(self):
        record = Record()
        title = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="a", value="Python"),
                Subfield(code="c", value="Guido"),
            ],
        )
        record.add_field(title)
        self.assertEqual(record["245"], title, "short access")
        self.assertEqual(record.get("999"), None, "short access with no field")

    def test_membership(self):
        record = Record()
        title = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="a", value="Python"),
                Subfield(code="c", value="Guido"),
            ],
        )
        record.add_field(title)
        self.assertTrue("245" in record)
        self.assertFalse("999" in record)

    def test_field_not_found(self):
        record = Record()
        self.assertEqual(len(record.fields), 0)

    def test_find(self):
        record = Record()
        subject1 = Field(
            tag="650",
            indicators=Indicators("", "0"),
            subfields=[Subfield(code="a", value="Programming Language")],
        )
        record.add_field(subject1)
        subject2 = Field(
            tag="650",
            indicators=Indicators("", "0"),
            subfields=[Subfield(code="a", value="Object Oriented")],
        )
        record.add_field(subject2)
        found = record.get_fields("650")
        self.assertEqual(found[0], subject1, "get_fields() item 1")
        self.assertEqual(found[0], subject1, "get_fields() item 2")
        found = record.get_fields()
        self.assertEqual(len(found), 2, "get_fields() with no tag")

    def test_multi_find(self):
        record = Record()
        subject1 = Field(
            tag="650",
            indicators=Indicators("", "0"),
            subfields=[Subfield(code="a", value="Programming Language")],
        )
        record.add_field(subject1)
        subject2 = Field(
            tag="651",
            indicators=Indicators("", "0"),
            subfields=[Subfield(code="a", value="Object Oriented")],
        )
        record.add_field(subject2)
        found = record.get_fields("650", "651")
        self.assertEqual(len(found), 2)

    def test_get_linked_fields(self):
        record = Record()
        t1 = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="6", value="880-01"),
                Subfield(code="a", value="Rū Harison no wārudo myūjikku nyūmon"),
            ],
        )
        record.add_field(t1)
        t2 = Field(
            tag="880",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="6", value="245-01"),
                Subfield(code="a", value="ルー・ハリソンのワールドミュージック入門"),
            ],
        )
        record.add_field(t2)
        pd1 = Field(
            tag="260",
            indicators=Indicators("0", "2"),
            subfields=[
                Subfield(code="6", value="880-02"),
                Subfield(code="a", value="Tōkyō"),
            ],
        )
        record.add_field(pd1)
        pd2 = Field(
            tag="880",
            indicators=Indicators("0", "2"),
            subfields=[
                Subfield(code="6", value="260-02"),
                Subfield(code="a", value="東京"),
            ],
        )
        record.add_field(pd2)
        self.assertEqual(record.get_linked_fields(t1), [t2])
        self.assertEqual(record.get_linked_fields(pd1), [pd2])

    def test_missing_linked_fields_exception(self):
        record = Record()
        t1 = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[
                Subfield(code="6", value="880-01"),
                Subfield(code="a", value="Rū Harison no wārudo myūjikku nyūmon"),
            ],
        )
        record.add_field(t1)
        self.assertRaisesRegex(
            MissingLinkedFields, "^245 field", record.get_linked_fields, t1
        )

    def test_bad_leader(self):
        record = Record()
        self.assertRaises(RecordLeaderInvalid, record.decode_marc, b"foo")

    def test_bad_base_address(self):
        record = Record()
        self.assertRaises(
            BaseAddressInvalid, record.decode_marc, b"00695cam  2200241Ia 45x00"
        )

    def test_title(self):
        record = Record()
        self.assertEqual(record.title, None)
        record.add_field(
            Field(
                "245",
                indicators=Indicators("0", "1"),
                subfields=[
                    Subfield(code="a", value="Foo :"),
                    Subfield(code="b", value="bar"),
                ],
            )
        )
        self.assertEqual(record.title, "Foo : bar")

        record = Record()
        record.add_field(
            Field(
                "245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="Farghin")],
            )
        )
        self.assertEqual(record.title, "Farghin")

    def test_issn_title(self):
        record = Record()
        self.assertEqual(record.issn_title, None)
        record.add_field(
            Field(
                "222",
                indicators=Indicators("", ""),
                subfields=[
                    Subfield(code="a", value="Foo :"),
                    Subfield(code="b", value="bar"),
                ],
            )
        )
        self.assertEqual(record.issn_title, "Foo : bar")

        record = Record()
        record.add_field(
            Field(
                "222",
                Indicators("", ""),
                subfields=[Subfield(code="a", value="Farghin")],
            )
        )
        self.assertEqual(record.issn_title, "Farghin")

        record = Record()
        record.add_field(
            Field(
                "222", Indicators("", ""), subfields=[Subfield(code="b", value="bar")]
            )
        )
        self.assertEqual(record.issn_title, None)

    def test_isbn(self):
        record = Record()
        self.assertEqual(record.isbn, None)
        record.add_field(
            Field(
                "020",
                Indicators("0", "1"),
                subfields=[Subfield(code="a", value="9781416566113")],
            )
        )
        self.assertEqual(record.isbn, "9781416566113")

        record = Record()
        record.add_field(
            Field(
                "020",
                Indicators("0", "1"),
                subfields=[Subfield(code="a", value="978-1416566113")],
            )
        )
        self.assertEqual(record.isbn, "9781416566113")

        record = Record()
        record.add_field(
            Field(
                "020",
                Indicators("0", "1"),
                subfields=[Subfield(code="a", value="ISBN-978-1416566113")],
            )
        )
        self.assertEqual(record.isbn, "9781416566113")

        record = Record()
        record.add_field(
            Field(
                "020",
                Indicators(" ", " "),
                subfields=[Subfield(code="a", value="0456789012 (reel 1)")],
            )
        )
        self.assertEqual(record.isbn, "0456789012")

        record = Record()
        record.add_field(
            Field(
                "020",
                Indicators(" ", " "),
                subfields=[Subfield(code="a", value="006073132X")],
            )
        )
        self.assertEqual(record.isbn, "006073132X")

    def test_issn(self):
        record = Record()
        self.assertEqual(record.issn, None)
        record.add_field(
            Field(
                tag="022",
                indicators=Indicators("0", ""),
                subfields=[Subfield(code="a", value="0395-2037")],
            )
        )
        self.assertEqual(record.issn, "0395-2037")

    def test_issnl(self):
        record = Record()
        self.assertEqual(record.issnl, None)
        record.add_field(
            Field(
                tag="022",
                indicators=Indicators("0", ""),
                subfields=[Subfield(code="l", value="0395-2037")],
            )
        )
        self.assertEqual(record.issnl, "0395-2037")

    def test_multiple_isbn(self):
        with open("test_pymarc/multi_isbn.dat", "rb") as fh:
            reader = MARCReader(fh)
            record = next(reader)
            assert record
            self.assertEqual(record.isbn, "0914378287")

    def test_author(self):
        record = Record()
        self.assertEqual(record.author, None)
        record.add_field(
            Field(
                "100",
                Indicators("1", "0"),
                subfields=[
                    Subfield(code="a", value="Bletch, Foobie,"),
                    Subfield(code="d", value="1979-1981."),
                ],
            )
        )
        self.assertEqual(record.author, "Bletch, Foobie, 1979-1981.")

        record = Record()
        record.add_field(
            Field(
                "130",
                Indicators("0", " "),
                subfields=[
                    Subfield(code="a", value="Bible."),
                    Subfield(code="l", value="Python."),
                ],
            )
        )
        self.assertEqual(record.author, None)

    def test_uniformtitle(self):
        record = Record()
        self.assertEqual(record.uniformtitle, None)
        record.add_field(
            Field(
                "130",
                Indicators("0", " "),
                subfields=[
                    Subfield(code="a", value="Tosefta."),
                    Subfield(code="l", value="English."),
                    Subfield(code="f", value="1977."),
                ],
            )
        )
        self.assertEqual(record.uniformtitle, "Tosefta. English. 1977.")

        record = Record()
        record.add_field(
            Field(
                "240",
                Indicators("1", "4"),
                subfields=[
                    Subfield(code="a", value="The Pickwick papers."),
                    Subfield(code="l", value="French."),
                ],
            )
        )
        self.assertEqual(record.uniformtitle, "The Pickwick papers. French.")

    def test_subjects(self):
        record = Record()
        subject1 = "=630  0\\$aTosefta.$lEnglish.$f1977."
        subject2 = "=600  10$aLe Peu, Pepe."
        shlist = [subject1, subject2]
        self.assertEqual(record.subjects, [])
        record.add_field(
            Field(
                "630",
                Indicators("0", " "),
                subfields=[
                    Subfield(code="a", value="Tosefta."),
                    Subfield(code="l", value="English."),
                    Subfield(code="f", value="1977."),
                ],
            )
        )
        record.add_field(
            Field(
                "730",
                Indicators("0", " "),
                subfields=[
                    Subfield(code="a", value="Tosefta."),
                    Subfield(code="l", value="English."),
                    Subfield(code="f", value="1977."),
                ],
            )
        )
        record.add_field(
            Field(
                "600",
                Indicators("1", "0"),
                subfields=[Subfield(code="a", value="Le Peu, Pepe.")],
            )
        )
        self.assertEqual(len(record.subjects), 2)
        self.assertEqual(record.subjects[0].__str__(), subject1)
        self.assertEqual(record.subjects[1].__str__(), subject2)
        rshlist = [rsh.__str__() for rsh in record.subjects]
        self.assertEqual(shlist, rshlist)

    def test_added_entries(self):
        record = Record()
        ae1 = "=730  0\\$aTosefta.$lEnglish.$f1977."
        ae2 = "=700  10$aLe Peu, Pepe."
        aelist = [ae1, ae2]
        self.assertEqual(record.addedentries, [])
        record.add_field(
            Field(
                "730",
                Indicators("0", " "),
                subfields=[
                    Subfield(code="a", value="Tosefta."),
                    Subfield(code="l", value="English."),
                    Subfield(code="f", value="1977."),
                ],
            )
        )
        record.add_field(
            Field(
                "700",
                Indicators("1", "0"),
                subfields=[Subfield(code="a", value="Le Peu, Pepe.")],
            )
        )
        record.add_field(
            Field(
                "245",
                Indicators("0", "0"),
                subfields=[Subfield(code="a", value="Le Peu's Tosefa.")],
            )
        )
        self.assertEqual(len(record.addedentries), 2)
        self.assertEqual(record.addedentries[0].__str__(), ae1)
        self.assertEqual(record.addedentries[1].__str__(), ae2)
        raelist = [rae.__str__() for rae in record.addedentries]
        self.assertEqual(aelist, raelist)

    def test_physicaldescription(self):
        record = Record()
        pd1 = "=300  \\$a1 photographic print :$bgelatin silver ;$c10 x 56 in."
        pd2 = "=300  \\$aFOO$bBAR$cBAZ"
        pdlist = [pd1, pd2]
        self.assertEqual(record.physicaldescription, [])
        record.add_field(
            Field(
                "300",
                Indicators("\\", ""),
                subfields=[
                    Subfield(code="a", value="1 photographic print :"),
                    Subfield(code="b", value="gelatin silver ;"),
                    Subfield(code="c", value="10 x 56 in."),
                ],
            )
        )
        record.add_field(
            Field(
                "300",
                Indicators("\\", ""),
                subfields=[
                    Subfield(code="a", value="FOO"),
                    Subfield(code="b", value="BAR"),
                    Subfield(code="c", value="BAZ"),
                ],
            )
        )
        self.assertEqual(len(record.physicaldescription), 2)
        self.assertEqual(record.physicaldescription[0].__str__(), pd1)
        self.assertEqual(record.physicaldescription[1].__str__(), pd2)
        rpdlist = [rpd.__str__() for rpd in record.physicaldescription]
        self.assertEqual(pdlist, rpdlist)

    def test_location(self):
        record = Record()
        loc1 = "=852  \\\\$aAmerican Institute of Physics.$bNiels Bohr Library and Archives.$eCollege Park, MD"
        loc2 = "=852  01$aCtY$bMain$hLB201$i.M63"
        loclist = [loc1, loc2]
        self.assertEqual(record.location, [])
        record.add_field(
            Field(
                "040",
                Indicators(" ", " "),
                subfields=[
                    Subfield(code="a", value="DLC"),
                    Subfield(code="c", value="DLC"),
                ],
            )
        )
        record.add_field(
            Field(
                "852",
                Indicators(" ", " "),
                subfields=[
                    Subfield(code="a", value="American Institute of Physics."),
                    Subfield(code="b", value="Niels Bohr Library and Archives."),
                    Subfield(code="e", value="College Park, MD"),
                ],
            )
        )
        record.add_field(
            Field(
                "852",
                Indicators("0", "1"),
                subfields=[
                    Subfield(code="a", value="CtY"),
                    Subfield(code="b", value="Main"),
                    Subfield(code="h", value="LB201"),
                    Subfield(code="i", value=".M63"),
                ],
            )
        )
        self.assertEqual(len(record.location), 2)
        self.assertEqual(record.location[0].__str__(), loc1)
        self.assertEqual(record.location[1].__str__(), loc2)
        rloclist = [rloc.__str__() for rloc in record.location]
        self.assertEqual(loclist, rloclist)

    def test_notes(self):
        record = Record()
        self.assertEqual(record.notes, [])
        record.add_field(
            Field(
                "500",
                Indicators(" ", " "),
                subfields=[
                    Subfield(
                        code="a",
                        value="Recast in bronze from artist's plaster original of 1903.",
                    ),
                ],
            )
        )
        self.assertEqual(
            record.notes[0].format_field(),
            "Recast in bronze from artist's plaster original of 1903.",
        )

    def test_publisher(self):
        record = Record()
        self.assertEqual(record.publisher, None)
        record.add_field(
            Field(
                "260",
                Indicators(" ", " "),
                subfields=[
                    Subfield(code="a", value="Paris :"),
                    Subfield(code="b", value="Gauthier-Villars ;"),
                    Subfield(code="a", value="Chicago :"),
                    Subfield(code="b", value="University of Chicago Press,"),
                    Subfield(code="c", value="1955."),
                ],
            )
        )
        self.assertEqual(record.publisher, "Gauthier-Villars ;")

        record = Record()
        self.assertEqual(record.publisher, None)
        record.add_field(
            Field(
                "264",
                Indicators(" ", "1"),
                subfields=[
                    Subfield(code="a", value="London :"),
                    Subfield(code="b", value="Penguin,"),
                    Subfield(code="c", value="1961."),
                ],
            )
        )
        self.assertEqual(record.publisher, "Penguin,")

    def test_pubyear(self):
        record = Record()
        self.assertEqual(record.pubyear, None)
        record.add_field(
            Field(
                "260",
                Indicators(" ", " "),
                subfields=[
                    Subfield(code="a", value="Paris :"),
                    Subfield(code="b", value="Gauthier-Villars ;"),
                    Subfield(code="a", value="Chicago :"),
                    Subfield(code="b", value="University of Chicago Press,"),
                    Subfield(code="c", value="1955."),
                ],
            )
        )
        self.assertEqual(record.pubyear, "1955.")

        record = Record()
        self.assertEqual(record.pubyear, None)
        record.add_field(
            Field(
                "264",
                Indicators(" ", "1"),
                subfields=[
                    Subfield(code="a", value="London :"),
                    Subfield(code="b", value="Penguin,"),
                    Subfield(code="c", value="1961."),
                ],
            )
        )
        self.assertEqual(record.pubyear, "1961.")

    def test_alphatag(self):
        record = Record()
        record.add_field(
            Field(
                "CAT", Indicators(" ", " "), subfields=[Subfield(code="a", value="foo")]
            )
        )
        record.add_field(
            Field(
                "CAT", Indicators(" ", " "), subfields=[Subfield(code="b", value="bar")]
            )
        )
        fields = record.get_fields("CAT")
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]["a"], "foo")
        self.assertEqual(fields[1]["b"], "bar")
        self.assertEqual(record["CAT"]["a"], "foo")

    def test_copy(self):
        from copy import deepcopy

        with open("test_pymarc/one.dat", "rb") as fh:
            r1 = next(MARCReader(fh))
            assert r1
            r2 = deepcopy(r1)
            r1.add_field(
                Field(
                    "999",
                    Indicators(" ", " "),
                    subfields=[Subfield(code="a", value="foo")],
                )
            )
            r2.add_field(
                Field(
                    "999",
                    Indicators(" ", " "),
                    subfields=[Subfield(code="a", value="bar")],
                )
            )
            self.assertEqual(r1["999"]["a"], "foo")
            self.assertEqual(r2["999"]["a"], "bar")

    def test_as_marc_with_explicit_leader(self):
        """Test setting an explicit leader.

        as_marc() should use the whole leader as set.
        """
        record = Record()
        record.add_field(
            Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="The pragmatic programmer")],
            )
        )
        record.leader = Leader("00067    a2200037   4500")
        leader_not_touched = record.leader
        record.as_marc()
        leader_touched = record.leader
        self.assertTrue(leader_not_touched == leader_touched)

    def test_remove_fields(self):
        with open("test_pymarc/testunimarc.dat", "rb") as fh:
            record = Record(fh.read(), force_utf8=True)
        self.assertTrue(len(record.get_fields("899")) != 0)
        self.assertTrue(len(record.get_fields("702")) != 0)
        record.remove_fields("899", "702")
        self.assertTrue(len(record.get_fields("899")) == 0)
        self.assertTrue(len(record.get_fields("702")) == 0)

    def test_as_marc_consistency(self):
        record = Record()
        leadertype = type(record.leader)
        record.as_marc()
        self.assertEqual(leadertype, type(record.leader))

    def test_init_with_no_leader(self):
        """Test creating a Record object with no leader argument."""
        record = Record()
        record.add_field(
            Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="The pragmatic programmer")],
            )
        )
        transmission_format = record.as_marc()
        transmission_format_leader = transmission_format[0:24]
        self.assertEqual(transmission_format_leader, b"00067    a2200037   4500")

    def test_init_with_no_leader_but_with_force_utf8(self):
        record = Record(force_utf8=True)
        record.add_field(
            Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="The pragmatic programmer")],
            )
        )
        self.assertTrue(isinstance(record.leader, Leader))
        transmission_format = record.as_marc()
        transmission_format_leader = transmission_format[0:24]
        self.assertEqual(transmission_format_leader, b"00067    a2200037   4500")

    def test_init_with_leader(self):
        record = Record(leader="abcdefghijklmnopqrstuvwx")
        record.add_field(
            Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="The pragmatic programmer")],
            )
        )
        transmission_format = record.as_marc()
        transmission_format_leader = transmission_format[0:24]
        self.assertEqual(transmission_format_leader, b"00067fghia2200037rst4500")

    def test_init_with_leader_and_force_utf8(self):
        record = Record(leader="abcdefghijklmnopqrstuvwx", force_utf8=True)
        record.add_field(
            Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=[Subfield(code="a", value="The pragmatic programmer")],
            )
        )
        transmission_format = record.as_marc()
        transmission_format_leader = transmission_format[0:24]
        self.assertEqual(transmission_format_leader, b"00067fghia2200037rst4500")

    def test_as_marc_to_unicode_conversion(self):
        with open("test_pymarc/marc8-to-unicode.dat", "rb") as fh:
            modified_record_bytes = fh.read()

        with open("test_pymarc/marc8.dat", "rb") as fh:
            original_record_bytes = fh.read()
            reader = MARCReader(original_record_bytes, to_unicode=True)
            record = next(reader)
            assert record
            record_bytes = record.as_marc()
            self.assertEqual(record_bytes[9], ord("a"))
            self.assertEqual(modified_record_bytes, record_bytes)

    def test_map_marc8_record_against_unicode_as_marc(self):
        from rmarc.record import map_marc8_record

        with open("test_pymarc/marc8.dat", "rb") as fh:
            reader = MARCReader(fh, to_unicode=True)
            record = next(reader)
            assert record
            map_marc8_data = map_marc8_record(record)
            self.assertEqual(map_marc8_data.as_marc(), record.as_marc())

    def test_fields_parameter(self):
        record = Record(
            fields=[
                Field(
                    tag="245",
                    subfields=[Subfield(code="a", value="A title")],
                ),
                Field(
                    tag="500",
                    subfields=[Subfield(code="a", value="A comment")],
                ),
            ]
        )

        assert record["245"]["a"] == "A title"  # noqa: S101
        assert record["500"]["a"] == "A comment"  # noqa: S101


if __name__ == "__main__":
    unittest.main()
