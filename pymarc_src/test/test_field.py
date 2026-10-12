# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.
import sys
import unittest

from pymarc.field import Field, Indicators, Subfield


class FieldTest(unittest.TestCase):
    def setUp(self):
        self.field = Field(
            tag="245",
            indicators=Indicators("0", "1"),
            subfields=[
                Subfield(code="a", value="Huckleberry Finn: "),
                Subfield(code="b", value="An American Odyssey"),
            ],
        )

        self.controlfield = Field(
            tag="008", data="831227m19799999nyu           ||| | ger  "
        )

        self.subjectfield = Field(
            tag="650",
            indicators=Indicators(" ", "0"),
            subfields=[
                Subfield(code="a", value="Python (Computer program language)"),
                Subfield(code="v", value="Poetry."),
            ],
        )

    def test_controlfield_subfield_is_empty(self):
        self.assertEqual(len(self.controlfield.subfields), 0)
        self.assertIsNone(self.controlfield.indicators)

    def test_field_data_is_none_if_not_control(self):
        self.assertIsNone(self.field.data)

    def test_indicators_if_not_supplied(self):
        f = Field(
            tag="245",
            subfields=[
                Subfield(code="a", value="Huckleberry Finn: "),
                Subfield(code="b", value="An American Odyssey"),
            ],
        )
        self.assertEqual(f.indicators, (" ", " "))

    def test_invalid_indicators_list(self):
        with self.assertRaises(ValueError):
            _ = Field(
                tag="245",
                indicators=["a", "b", "c"],  # type: ignore
                subfields=[
                    Subfield(code="a", value="Huckleberry Finn: "),
                    Subfield(code="b", value="An American Odyssey"),
                ],
            )

    def test_invalid_indicators_tuple(self):
        with self.assertRaises(ValueError):
            _ = Field(
                tag="245",
                indicators=("a", "b", "c"),  # type: ignore
                subfields=[
                    Subfield(code="a", value="Huckleberry Finn: "),
                    Subfield(code="b", value="An American Odyssey"),
                ],
            )

    def test_legacy_indicators_two_value_list(self):
        f = Field(
            tag="245",
            indicators=["a", "b"],  # type: ignore
            subfields=[
                Subfield(code="a", value="Huckleberry Finn: "),
                Subfield(code="b", value="An American Odyssey"),
            ],
        )
        self.assertIsInstance(f.indicators, Indicators)

    def test_implicit_coded_subfield_constructor(self):
        field = Field(
            tag="245",
            indicators=Indicators("0", "1"),
            subfields=[
                Subfield("a", "Huckleberry Finn: "),
                Subfield("b", "An American Odyssey"),
            ],
        )
        self.assertEqual(field["a"], "Huckleberry Finn: ")
        self.assertEqual(field["b"], "An American Odyssey")

    def test_explicit_coded_subfield(self):
        field = Field(
            tag="245",
            indicators=Indicators("0", "1"),
            subfields=[
                Subfield(code="a", value="Huckleberry Finn: "),
                Subfield(code="b", value="An American Odyssey"),
            ],
        )
        self.assertEqual(field["a"], "Huckleberry Finn: ")
        self.assertEqual(field["b"], "An American Odyssey")

    def test_old_style_raises_valueerror(self):
        old_style_subfields = ["a", "Huckleberry Finn: ", "b", "An American Odyssey"]
        with self.assertRaises(ValueError):
            _ = Field(
                tag="245",
                indicators=Indicators("0", "1"),
                subfields=old_style_subfields,  # type: ignore
            )

    def test_string(self):
        self.assertEqual(
            str(self.field), "=245  01$aHuckleberry Finn: $bAn American Odyssey"
        )

    def test_controlfield_string(self):
        self.assertEqual(
            str(self.controlfield), r"=008  831227m19799999nyu\\\\\\\\\\\|||\|\ger\\"
        )

    def test_indicators(self):
        assert self.field.indicators
        self.assertEqual(self.field.indicator1, "0")
        self.assertEqual(self.field.indicators.first, "0")
        self.assertEqual(self.field.indicator2, "1")
        self.assertEqual(self.field.indicators.second, "1")

    def test_reassign_indicators(self):
        self.field.indicators = (" ", "1")
        self.assertEqual(self.field.indicator1, " ")
        self.assertEqual(self.field.indicator2, "1")

        self.field.indicators = ["1", " "]
        self.assertEqual(self.field.indicator1, "1")
        self.assertEqual(self.field.indicator2, " ")

    def test_subfields_created(self):
        subfields = self.field.subfields
        self.assertEqual(len(subfields), 2)

    def test_subfield_short(self):
        self.assertEqual(self.field["a"], "Huckleberry Finn: ")
        with self.assertRaises(KeyError):
            _ = self.field["z"]

    def test_subfield_get_none(self):
        self.assertIsNone(self.field.get("z"))

    def test_subfield_setter(self):
        self.field.subfields = [
            Subfield(code="a", value="The Adventures of Tom Sawyer")
        ]
        self.assertEqual(self.field["a"], "The Adventures of Tom Sawyer")

    def test_subfields(self):
        self.assertEqual(self.field.get_subfields("a"), ["Huckleberry Finn: "])
        self.assertEqual(
            self.subjectfield.get_subfields("a"), ["Python (Computer program language)"]
        )

    def test_subfields_multi(self):
        self.assertEqual(
            self.field.get_subfields("a", "b"),
            ["Huckleberry Finn: ", "An American Odyssey"],
        )
        self.assertEqual(
            self.subjectfield.get_subfields("a", "v"),
            ["Python (Computer program language)", "Poetry."],
        )

    def test_encode(self):
        self.field.as_marc(encoding="utf-8")

    def test_membership(self):
        self.assertTrue("a" in self.field)
        self.assertFalse("zzz" in self.field)

    def test_iterator(self):
        string = ""
        for subfield in self.field:
            string += subfield.code
            string += subfield.value
        self.assertEqual(string, "aHuckleberry Finn: bAn American Odyssey")

    def test_value(self):
        self.assertEqual(self.field.value(), "Huckleberry Finn: An American Odyssey")
        self.assertEqual(
            self.controlfield.value(), "831227m19799999nyu           ||| | ger  "
        )

    def test_non_integer_tag(self):
        # make sure this doesn't throw an exception
        Field(
            tag="3 0",
            indicators=Indicators("0", "1"),
            subfields=[Subfield(code="a", value="foo")],
        )

    def test_add_subfield(self):
        field = Field(
            tag="245",
            indicators=Indicators("0", "1"),
            subfields=[Subfield(code="a", value="foo")],
        )
        field.add_subfield("a", "bar")
        self.assertEqual(field.__str__(), "=245  01$afoo$abar")
        field.add_subfield("b", "baz", 0)
        self.assertEqual(field.__str__(), "=245  01$bbaz$afoo$abar")
        field.add_subfield("c", "qux", 2)
        self.assertEqual(field.__str__(), "=245  01$bbaz$afoo$cqux$abar")
        field.add_subfield("z", "wat", 8)
        self.assertEqual(field.__str__(), "=245  01$bbaz$afoo$cqux$abar$zwat")

    def test_delete_subfield(self):
        field = Field(
            tag="200",
            indicators=Indicators("0", "1"),
            subfields=[
                Subfield(code="a", value="My Title"),
                Subfield(code="a", value="Kinda Bogus Anyhow"),
            ],
        )
        self.assertEqual(field.delete_subfield("z"), None)
        self.assertEqual(field.delete_subfield("a"), "My Title")
        self.assertEqual(field.delete_subfield("a"), "Kinda Bogus Anyhow")
        self.assertTrue(len(field.subfields) == 0)

    def test_subfield_delete_contains(self):
        field = Field(
            tag="200",
            indicators=Indicators("0", "1"),
            subfields=[
                Subfield(code="a", value="My Title"),
                Subfield(code="z", value="Kinda Bogus Anyhow"),
            ],
        )
        self.assertTrue("z" in field)
        field.delete_subfield("z")
        self.assertFalse("z" in field)

    def test_is_subject_field(self):
        self.assertEqual(self.subjectfield.is_subject_field(), True)
        self.assertEqual(self.field.is_subject_field(), False)

    def test_format_field(self):
        self.subjectfield.add_subfield("6", "880-4")
        self.assertEqual(
            self.subjectfield.format_field(),
            "Python (Computer program language) -- Poetry.",
        )
        self.field.add_subfield("6", "880-1")
        self.assertEqual(
            self.field.format_field(), "Huckleberry Finn:  An American Odyssey"
        )

    def test_tag_normalize(self):
        f = Field(tag="42", indicators=Indicators("", ""))
        self.assertEqual(f.tag, "042")

    def test_alphatag(self):
        f = Field(
            tag="CAT",
            indicators=Indicators("0", "1"),
            subfields=[Subfield(code="a", value="foo")],
        )
        self.assertEqual(f.tag, "CAT")
        self.assertEqual(f["a"], "foo")
        self.assertEqual(f.control_field, False)

    def test_setitem_no_key(self):
        try:
            self.field["h"] = "error"
        except KeyError:
            pass
        except Exception:
            e = sys.exc_info()[1]
            self.fail(f"Unexpected exception thrown: {e}")
        else:
            self.fail("KeyError not thrown")

    def test_setitem_repeated_key(self):
        try:
            self.field.add_subfield("a", "bar")
            self.field["a"] = "error"
        except KeyError:
            pass
        except Exception:
            e = sys.exc_info()[1]
            self.fail(f"Unexpected exception thrown: {e}")
        else:
            self.fail("KeyError not thrown")

    def test_iter_over_controlfield(self):
        try:
            list(self.controlfield)
        except AttributeError as e:
            self.fail(f"Error during iteration: {e}")

    def test_setitem(self):
        self.field["a"] = "changed"
        self.assertEqual(self.field["a"], "changed")

    def test_delete_subfield_only_by_code(self):
        field = Field(
            tag="960",
            indicators=Indicators(" ", " "),
            subfields=[
                Subfield(code="a", value="b"),
                Subfield(code="b", value="x"),
            ],
        )
        value = field.delete_subfield("b")
        self.assertEqual(value, "x")
        self.assertEqual(field.subfields, [Subfield(code="a", value="b")])

    def test_subfield_dict(self):
        field = Field(
            tag="680",
            indicators=Indicators(" ", " "),
            subfields=[
                Subfield(code="a", value="Repeated"),
                Subfield(code="a", value="Subfield"),
            ],
        )
        dictionary = field.subfields_as_dict()
        self.assertTrue(isinstance(dictionary, dict))
        self.assertIn("a", dictionary)
        self.assertEqual(dictionary["a"], ["Repeated", "Subfield"])

    def test_set_indicators_affects_str(self):
        self.field.indicator1 = "9"
        self.field.indicator2 = "9"
        self.assertEqual(
            str(self.field), "=245  99$aHuckleberry Finn: $bAn American Odyssey"
        )

    def test_set_indicators_affects_marc(self):
        self.field.indicator1 = "9"
        self.field.indicator2 = "9"
        self.assertEqual(
            self.field.as_marc("utf-8"),
            b"99\x1faHuckleberry Finn: \x1fbAn American Odyssey\x1e",
        )

    def test_linkage_occurrence_num(self):
        f = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[Subfield(code="6", value="880-01")],
        )
        self.assertEqual(f.linkage_occurrence_num(), "01")
        f = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[Subfield(code="6", value="530-00/(2/r")],
        )
        self.assertEqual(f.linkage_occurrence_num(), "00")
        f = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[Subfield(code="6", value="100-42/Cyrl")],
        )
        self.assertEqual(f.linkage_occurrence_num(), "42")
        f = Field(
            tag="245",
            indicators=Indicators("1", "0"),
            subfields=[Subfield(code="a", value="Music primer")],
        )
        self.assertIsNone(f.linkage_occurrence_num())

    def test_coded_subfield(self):
        coded_val = self.field.subfields[0]
        self.assertIsInstance(coded_val, Subfield)
        # NB: Python typecheckers don't generally like named tuples yet.
        self.assertEqual(coded_val.code, "a")  # type: ignore
        self.assertEqual(coded_val.value, "Huckleberry Finn: ")  # type: ignore

    def test_convert_legacy_subfields(self) -> None:
        """Tests conversion between the legacy subfield format and the new Subfield format."""
        legacy_fields: list[str] = [
            "a",
            "The pragmatic programmer : ",
            "b",
            "from journeyman to master /",
            "c",
            "Andrew Hunt, David Thomas",
        ]

        coded_fields: list[Subfield] = Field.convert_legacy_subfields(legacy_fields)
        self.assertEqual(
            coded_fields,
            [
                Subfield(code="a", value="The pragmatic programmer : "),
                Subfield(code="b", value="from journeyman to master /"),
                Subfield(code="c", value="Andrew Hunt, David Thomas"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
