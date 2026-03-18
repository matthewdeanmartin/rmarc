"""Suite 1: Comprehensive pytest test suite for rmarc.

Uses tmp_path for all temporary files. Each test scenario is verified
to work with the legacy pymarc-compatible API. Where rmarc behavior
differs from what one might naively expect, those are noted as
"correct behavior" since rmarc IS the reference.
"""

import json
import os
from copy import deepcopy
from io import BytesIO, StringIO

import pytest

import rmarc
from test_pymarc import fixture_path
from rmarc import (
    Field,
    Indicators,
    JSONReader,
    JSONWriter,
    Leader,
    MARCMakerReader,
    MARCReader,
    MARCWriter,
    RawField,
    Record,
    Subfield,
    TextWriter,
    XMLWriter,
    marc8_to_unicode,
)
from rmarc.constants import DIRECTORY_ENTRY_LEN, END_OF_FIELD, END_OF_RECORD, LEADER_LEN, SUBFIELD_INDICATOR
from rmarc.exceptions import (
    BadLeaderValue,
    BadSubfieldCodeWarning,
    BaseAddressInvalid,
    BaseAddressNotFound,
    EndOfRecordNotFound,
    FatalReaderError,
    FieldNotFound,
    MissingLinkedFields,
    NoFieldsFound,
    PymarcException,
    RecordDirectoryInvalid,
    RecordLeaderInvalid,
    RecordLengthInvalid,
    TruncatedRecord,
    WriteNeedsRecord,
)
from rmarc.marcjson import parse_json_to_array
from rmarc.marcxml import map_xml, parse_xml_to_array, record_to_xml, record_to_xml_node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_record():
    """Create a minimal record with a 245 field."""
    r = Record()
    r.add_field(
        Field(
            "245",
            Indicators("0", "1"),
            [Subfield("a", "Test Title /"), Subfield("c", "Test Author.")],
        )
    )
    return r


def _make_full_record():
    """Create a record with control and data fields."""
    r = Record()
    r.add_field(Field("001", data="ocm12345678"))
    r.add_field(Field("003", data="OCoLC"))
    r.add_field(Field("008", data="910926s1957    nyuuun              eng  "))
    r.add_field(Field("020", Indicators(" ", " "), [Subfield("a", "9780316769488")]))
    r.add_field(
        Field(
            "100",
            Indicators("1", " "),
            [Subfield("a", "Salinger, J. D."), Subfield("q", "(Jerome David),"), Subfield("d", "1919-2010.")],
        )
    )
    r.add_field(
        Field(
            "245",
            Indicators("1", "4"),
            [Subfield("a", "The catcher in the rye /"), Subfield("c", "J.D. Salinger.")],
        )
    )
    r.add_field(
        Field(
            "260",
            Indicators(" ", " "),
            [Subfield("a", "Boston :"), Subfield("b", "Little, Brown,"), Subfield("c", "1951.")],
        )
    )
    r.add_field(Field("300", Indicators(" ", " "), [Subfield("a", "277 p. ;"), Subfield("c", "21 cm.")]))
    r.add_field(Field("650", Indicators(" ", "0"), [Subfield("a", "Teenage boys"), Subfield("v", "Fiction.")]))
    r.add_field(Field("852", Indicators("0", " "), [Subfield("a", "DLC"), Subfield("b", "Main")]))
    return r


# ===================================================================
# 1. FIELD BASICS
# ===================================================================


class TestFieldCreation:
    def test_data_field_basic(self):
        f = Field("245", Indicators("1", "0"), [Subfield("a", "Title")])
        assert f.tag == "245"
        assert f.indicator1 == "1"
        assert f.indicator2 == "0"
        assert f["a"] == "Title"
        assert not f.control_field

    def test_control_field_basic(self):
        f = Field("008", data="some data")
        assert f.tag == "008"
        assert f.data == "some data"
        assert f.control_field
        assert f.indicators is None
        assert len(f.subfields) == 0

    def test_tag_normalization_numeric(self):
        f = Field("42", Indicators("", ""))
        assert f.tag == "042"

    def test_tag_normalization_single_digit(self):
        f = Field("1", data="test")
        assert f.tag == "001"

    def test_alpha_tag_not_normalized(self):
        f = Field("CAT", Indicators("0", "1"), [Subfield("a", "foo")])
        assert f.tag == "CAT"
        assert not f.control_field

    def test_non_integer_tag(self):
        # tags like "3 0" should not raise
        f = Field("3 0", Indicators("0", "1"), [Subfield("a", "foo")])
        assert f.tag == "3 0"

    def test_default_indicators(self):
        f = Field("245", subfields=[Subfield("a", "Title")])
        assert f.indicators == Indicators(" ", " ")

    def test_indicators_from_list(self):
        f = Field("245", ["1", "0"], [Subfield("a", "Title")])
        assert isinstance(f.indicators, Indicators)
        assert f.indicator1 == "1"

    def test_indicators_from_tuple(self):
        f = Field("245", ("1", "0"), [Subfield("a", "Title")])
        assert isinstance(f.indicators, Indicators)

    def test_invalid_indicators_three_elements(self):
        with pytest.raises(ValueError):
            Field("245", ["a", "b", "c"], [Subfield("a", "Title")])

    def test_invalid_indicators_tuple_three_elements(self):
        with pytest.raises(ValueError):
            Field("245", ("a", "b", "c"), [Subfield("a", "Title")])

    def test_old_style_subfields_raises(self):
        with pytest.raises(ValueError):
            Field("245", Indicators("0", "1"), ["a", "Title", "c", "Author"])

    def test_control_field_001_through_009(self):
        for tag_num in range(1, 10):
            tag = f"{tag_num:03d}"
            f = Field(tag, data="test")
            assert f.control_field, f"Tag {tag} should be a control field"

    def test_data_field_010_and_above(self):
        f = Field("010", Indicators(" ", " "), [Subfield("a", "test")])
        assert not f.control_field


class TestFieldSubfieldAccess:
    def test_getitem(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        assert f["a"] == "Title"
        assert f["c"] == "Author"

    def test_getitem_missing_raises_keyerror(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        with pytest.raises(KeyError):
            _ = f["z"]

    def test_get_with_default(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        assert f.get("z") is None
        assert f.get("z", "default") == "default"
        assert f.get("a") == "Title"

    def test_contains(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        assert "a" in f
        assert "z" not in f

    def test_contains_control_field(self):
        f = Field("008", data="some data")
        assert "a" not in f

    def test_setitem(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Old")])
        f["a"] = "New"
        assert f["a"] == "New"

    def test_setitem_missing_key_raises(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        with pytest.raises(KeyError):
            f["z"] = "nope"

    def test_setitem_repeated_key_raises(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "One"), Subfield("a", "Two")])
        with pytest.raises(KeyError):
            f["a"] = "error"

    def test_get_subfields_single(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        assert f.get_subfields("a") == ["Title"]

    def test_get_subfields_multi(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        assert f.get_subfields("a", "c") == ["Title", "Author"]

    def test_get_subfields_empty(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        assert f.get_subfields("z") == []

    def test_get_subfields_control_field(self):
        f = Field("008", data="some data")
        assert f.get_subfields("a") == []

    def test_subfields_as_dict(self):
        f = Field("245", Indicators(" ", " "), [Subfield("a", "One"), Subfield("a", "Two"), Subfield("b", "Three")])
        d = f.subfields_as_dict()
        assert d == {"a": ["One", "Two"], "b": ["Three"]}

    def test_subfields_as_dict_control_field(self):
        f = Field("008", data="some data")
        assert f.subfields_as_dict() == {}


class TestFieldSubfieldMutation:
    def test_add_subfield_append(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "foo")])
        f.add_subfield("b", "bar")
        assert str(f) == "=245  01$afoo$bbar"

    def test_add_subfield_at_position_0(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "foo")])
        f.add_subfield("b", "bar", 0)
        assert str(f) == "=245  01$bbar$afoo"

    def test_add_subfield_at_middle(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "foo"), Subfield("c", "baz")])
        f.add_subfield("b", "bar", 1)
        assert str(f) == "=245  01$afoo$bbar$cbaz"

    def test_add_subfield_beyond_end(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "foo")])
        f.add_subfield("z", "end", 999)
        assert str(f) == "=245  01$afoo$zend"

    def test_add_subfield_to_control_field(self):
        f = Field("008", data="data")
        result = f.add_subfield("a", "test")
        assert result is None
        assert len(f.subfields) == 0

    def test_delete_subfield(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("b", "Sub")])
        val = f.delete_subfield("a")
        assert val == "Title"
        assert "a" not in f

    def test_delete_subfield_missing(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        assert f.delete_subfield("z") is None

    def test_delete_subfield_control_field(self):
        f = Field("008", data="data")
        assert f.delete_subfield("a") is None

    def test_delete_subfield_multiple_same_code(self):
        f = Field("200", Indicators("0", "1"), [Subfield("a", "First"), Subfield("a", "Second")])
        assert f.delete_subfield("a") == "First"
        assert f.delete_subfield("a") == "Second"
        assert len(f.subfields) == 0

    def test_delete_then_contains(self):
        f = Field("200", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("z", "Extra")])
        assert "z" in f
        f.delete_subfield("z")
        assert "z" not in f

    def test_subfield_setter(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Old")])
        f.subfields = [Subfield("a", "New")]
        assert f["a"] == "New"

    def test_delete_by_code_not_value(self):
        """Ensure delete_subfield uses code, not value."""
        f = Field("960", Indicators(" ", " "), [Subfield("a", "b"), Subfield("b", "x")])
        value = f.delete_subfield("b")
        assert value == "x"
        assert f.subfields == [Subfield("a", "b")]


class TestFieldIndicators:
    def test_set_indicator1(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        f.indicator1 = "9"
        assert f.indicator1 == "9"
        assert f.indicator2 == "1"

    def test_set_indicator2(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        f.indicator2 = "9"
        assert f.indicator2 == "9"

    def test_reassign_indicators_tuple(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        f.indicators = (" ", "1")
        assert f.indicator1 == " "
        assert f.indicator2 == "1"

    def test_reassign_indicators_list(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        f.indicators = ["1", " "]
        assert f.indicator1 == "1"
        assert f.indicator2 == " "

    def test_indicators_affect_str(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Foo")])
        f.indicator1 = "9"
        f.indicator2 = "9"
        assert str(f) == "=245  99$aFoo"

    def test_indicators_affect_as_marc(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Foo")])
        f.indicator1 = "9"
        f.indicator2 = "9"
        assert f.as_marc("utf-8") == b"99\x1faFoo\x1e"


class TestFieldStringRepr:
    def test_data_field_str(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Huck Finn "), Subfield("b", "Odyssey")])
        assert str(f) == "=245  01$aHuck Finn $bOdyssey"

    def test_control_field_str(self):
        f = Field("008", data="831227m19799999nyu           ||| | ger  ")
        expected = r"=008  831227m19799999nyu\\\\\\\\\\\|||\|\ger\\"
        assert str(f) == expected

    def test_field_value_data_field(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Hello "), Subfield("b", "World")])
        assert f.value() == "Hello World"

    def test_field_value_control_field(self):
        f = Field("008", data="some data")
        assert f.value() == "some data"

    def test_format_field_data(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        assert f.format_field() == "Title Author"

    def test_format_field_subject(self):
        f = Field("650", Indicators(" ", "0"), [Subfield("a", "Python"), Subfield("v", "Poetry.")])
        assert f.format_field() == "Python -- Poetry."

    def test_format_field_skips_subfield_6(self):
        f = Field("650", Indicators(" ", "0"), [Subfield("6", "880-1"), Subfield("a", "Topic")])
        assert f.format_field() == "Topic"

    def test_format_field_control(self):
        f = Field("008", data="some data")
        assert f.format_field() == "some data"


class TestFieldIterator:
    def test_iterate_data_field(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title"), Subfield("c", "Author")])
        subs = list(f)
        assert len(subs) == 2
        assert subs[0] == Subfield("a", "Title")
        assert subs[1] == Subfield("c", "Author")

    def test_iterate_control_field(self):
        f = Field("008", data="some data")
        subs = list(f)
        assert subs == []

    def test_multiple_iterations(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        assert list(f) == [Subfield("a", "Title")]
        assert list(f) == [Subfield("a", "Title")]


class TestFieldEncoding:
    def test_as_marc_data_field(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Test")])
        marc = f.as_marc("utf-8")
        assert marc == b"01\x1faTest\x1e"

    def test_as_marc_control_field(self):
        f = Field("008", data="some data")
        marc = f.as_marc("utf-8")
        assert marc == b"some data\x1e"

    def test_as_marc_utf8_special_chars(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "\u00e9")])  # é
        marc = f.as_marc("utf-8")
        assert b"\xc3\xa9" in marc  # UTF-8 encoding of é

    def test_as_marc_multiple_subfields(self):
        f = Field("245", Indicators("1", "0"), [Subfield("a", "Title /"), Subfield("c", "Author.")])
        marc = f.as_marc("utf-8")
        assert marc == b"10\x1faTitle /\x1fcAuthor.\x1e"


class TestFieldMisc:
    def test_is_subject_field(self):
        assert Field("650", Indicators(" ", "0"), [Subfield("a", "Topic")]).is_subject_field()
        assert Field("600", Indicators("1", "0"), [Subfield("a", "Person")]).is_subject_field()
        assert not Field("245", Indicators("0", "1"), [Subfield("a", "Title")]).is_subject_field()

    def test_is_control_field(self):
        assert Field("008", data="data").is_control_field()
        assert not Field("245", Indicators("0", "1"), [Subfield("a", "Title")]).is_control_field()

    def test_linkage_occurrence_num(self):
        f = Field("245", Indicators("1", "0"), [Subfield("6", "880-01")])
        assert f.linkage_occurrence_num() == "01"

    def test_linkage_occurrence_num_with_script(self):
        f = Field("245", Indicators("1", "0"), [Subfield("6", "100-42/Cyrl")])
        assert f.linkage_occurrence_num() == "42"

    def test_linkage_occurrence_num_none(self):
        f = Field("245", Indicators("1", "0"), [Subfield("a", "Title")])
        assert f.linkage_occurrence_num() is None

    def test_convert_legacy_subfields(self):
        legacy = ["a", "Title /", "c", "Author"]
        coded = Field.convert_legacy_subfields(legacy)
        assert coded == [Subfield("a", "Title /"), Subfield("c", "Author")]

    def test_coded_subfield_is_namedtuple(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        s = f.subfields[0]
        assert isinstance(s, Subfield)
        assert s.code == "a"
        assert s.value == "Title"


# ===================================================================
# 2. LEADER
# ===================================================================


class TestLeader:
    LEADER_STR = "00475casaa2200169 ib4500"

    def test_create(self):
        leader = Leader(self.LEADER_STR)
        assert str(leader) == self.LEADER_STR

    def test_invalid_length_short(self):
        with pytest.raises(RecordLeaderInvalid):
            Leader("short")

    def test_invalid_length_long(self):
        with pytest.raises(RecordLeaderInvalid):
            Leader(self.LEADER_STR + "x")

    def test_properties(self):
        leader = Leader(self.LEADER_STR)
        assert leader.record_length == "00475"
        assert leader.record_status == "c"
        assert leader.type_of_record == "a"
        assert leader.bibliographic_level == "s"
        assert leader.type_of_control == "a"
        assert leader.coding_scheme == "a"
        assert leader.indicator_count == "2"
        assert leader.subfield_code_count == "2"
        assert leader.base_address == "00169"
        assert leader.encoding_level == " "
        assert leader.cataloging_form == "i"
        assert leader.multipart_ressource == "b"
        assert leader.length_of_field_length == "4"
        assert leader.starting_character_position_length == "5"
        assert leader.implementation_defined_length == "0"

    def test_setters(self):
        leader = Leader(self.LEADER_STR)
        leader.record_status = "d"
        assert leader.record_status == "d"
        assert leader[5] == "d"

    def test_setter_wrong_length(self):
        leader = Leader(self.LEADER_STR)
        with pytest.raises(BadLeaderValue):
            leader.record_status = "xx"

    def test_slice_access(self):
        leader = Leader(self.LEADER_STR)
        assert leader[0:5] == "00475"
        assert leader[5] == "c"

    def test_slice_set(self):
        leader = Leader(self.LEADER_STR)
        leader[5] = "n"
        assert leader[5] == "n"

    def test_len(self):
        leader = Leader(self.LEADER_STR)
        assert len(leader) == LEADER_LEN

    def test_equality(self):
        leader1 = Leader(self.LEADER_STR)
        leader2 = Leader(self.LEADER_STR)
        assert leader1 == leader2
        assert leader1 == self.LEADER_STR

    def test_hash(self):
        leader = Leader(self.LEADER_STR)
        assert hash(leader) == hash(self.LEADER_STR)

    def test_add(self):
        leader = Leader(self.LEADER_STR)
        new = leader[0:9] + "b" + leader[10:]
        assert new == "00475casab2200169 ib4500"


# ===================================================================
# 3. RECORD BASICS
# ===================================================================


class TestRecordCreation:
    def test_empty_record(self):
        r = Record()
        assert len(r.fields) == 0
        assert isinstance(r.leader, Leader)
        assert len(str(r.leader)) == LEADER_LEN

    def test_record_with_fields_param(self):
        r = Record(
            fields=[
                Field("245", subfields=[Subfield("a", "A title")]),
                Field("500", subfields=[Subfield("a", "A note")]),
            ]
        )
        assert r["245"]["a"] == "A title"
        assert r["500"]["a"] == "A note"

    def test_record_force_utf8(self):
        r = Record(force_utf8=True)
        assert r.leader[9] == "a"

    def test_record_with_explicit_leader(self):
        r = Record(leader="abcdefghijklmnopqrstuvwx")
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Title")]))
        marc = r.as_marc()
        # Positions 0-4 and 12-16 are recalculated, but 5-11 and 17-19 preserved
        leader = marc[0:24]
        assert leader[5:10] == b"fghia"  # positions 5-9 from original
        assert leader[17:20] == b"rst"  # positions 17-19 from original

    def test_record_with_leader_and_force_utf8(self):
        r = Record(leader="abcdefghijklmnopqrstuvwx", force_utf8=True)
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Title")]))
        marc = r.as_marc()
        leader = marc[0:24]
        assert leader[5:10] == b"fghia"


class TestRecordFieldAccess:
    def test_getitem(self):
        r = _make_simple_record()
        f = r["245"]
        assert f["a"] == "Test Title /"

    def test_getitem_missing_raises(self):
        r = Record()
        with pytest.raises(KeyError):
            _ = r["999"]

    def test_get_returns_none(self):
        r = Record()
        assert r.get("999") is None

    def test_get_returns_field(self):
        r = _make_simple_record()
        f = r.get("245")
        assert f is not None
        assert f["a"] == "Test Title /"

    def test_contains(self):
        r = _make_simple_record()
        assert "245" in r
        assert "999" not in r

    def test_get_fields_all(self):
        r = _make_full_record()
        all_fields = r.get_fields()
        assert len(all_fields) == 10

    def test_get_fields_by_tag(self):
        r = _make_full_record()
        fields = r.get_fields("245")
        assert len(fields) == 1
        assert fields[0]["a"] == "The catcher in the rye /"

    def test_get_fields_multi_tag(self):
        r = _make_full_record()
        fields = r.get_fields("001", "003")
        assert len(fields) == 2

    def test_get_fields_no_match(self):
        r = _make_full_record()
        assert r.get_fields("999") == []


class TestRecordFieldMutation:
    def test_add_field(self):
        r = Record()
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        r.add_field(f)
        assert f in r.fields

    def test_add_multiple_fields(self):
        r = Record()
        f1 = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        f2 = Field("100", Indicators("1", " "), [Subfield("a", "Author")])
        r.add_field(f1, f2)
        assert len(r.fields) == 2

    def test_remove_field(self):
        r = Record()
        f = Field("245", Indicators("0", "1"), [Subfield("a", "Title")])
        r.add_field(f)
        r.remove_field(f)
        assert r.get("245") is None

    def test_remove_field_not_found(self):
        r = Record()
        f = Field("001", data="test")
        with pytest.raises(FieldNotFound):
            r.remove_field(f)

    def test_remove_fields_by_tag(self):
        r = _make_full_record()
        assert len(r.get_fields("650")) > 0
        r.remove_fields("650")
        assert len(r.get_fields("650")) == 0

    def test_remove_fields_multiple_tags(self):
        r = _make_full_record()
        r.remove_fields("001", "003")
        assert r.get("001") is None
        assert r.get("003") is None


class TestRecordIterator:
    def test_iterate(self):
        r = _make_full_record()
        count = 0
        for _ in r:
            count += 1
        assert count == 10

    def test_iterate_empty(self):
        r = Record()
        assert list(r) == []

    def test_multiple_iterations(self):
        r = _make_simple_record()
        assert len(list(r)) == 1
        assert len(list(r)) == 1


class TestRecordLinkedFields:
    def test_get_linked_fields(self):
        r = Record()
        t1 = Field("245", Indicators("1", "0"), [Subfield("6", "880-01"), Subfield("a", "Romanized")])
        t2 = Field("880", Indicators("1", "0"), [Subfield("6", "245-01"), Subfield("a", "ルー")])
        r.add_field(t1, t2)
        linked = r.get_linked_fields(t1)
        assert linked == [t2]

    def test_get_linked_fields_missing_raises(self):
        r = Record()
        f = Field("245", Indicators("1", "0"), [Subfield("6", "880-01"), Subfield("a", "Title")])
        r.add_field(f)
        with pytest.raises(MissingLinkedFields, match="^245 field"):
            r.get_linked_fields(f)


# ===================================================================
# 4. RECORD PROPERTIES (title, isbn, author, etc.)
# ===================================================================


class TestRecordProperties:
    def test_title_none(self):
        assert Record().title is None

    def test_title_a_only(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Farghin")]))
        assert r.title == "Farghin"

    def test_title_a_and_b(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Foo :"), Subfield("b", "bar")]))
        assert r.title == "Foo : bar"

    def test_issn_title_none(self):
        assert Record().issn_title is None

    def test_issn_title(self):
        r = Record()
        r.add_field(Field("222", Indicators("", ""), [Subfield("a", "Journal :"), Subfield("b", "sub")]))
        assert r.issn_title == "Journal : sub"

    def test_issn_title_no_a_subfield(self):
        r = Record()
        r.add_field(Field("222", Indicators("", ""), [Subfield("b", "only b")]))
        assert r.issn_title is None

    def test_isbn_none(self):
        assert Record().isbn is None

    def test_isbn_clean(self):
        r = Record()
        r.add_field(Field("020", Indicators("0", "1"), [Subfield("a", "9781416566113")]))
        assert r.isbn == "9781416566113"

    def test_isbn_with_dashes(self):
        r = Record()
        r.add_field(Field("020", Indicators("0", "1"), [Subfield("a", "978-1416566113")]))
        assert r.isbn == "9781416566113"

    def test_isbn_with_prefix(self):
        r = Record()
        r.add_field(Field("020", Indicators("0", "1"), [Subfield("a", "ISBN-978-1416566113")]))
        assert r.isbn == "9781416566113"

    def test_isbn_with_qualifier(self):
        r = Record()
        r.add_field(Field("020", Indicators(" ", " "), [Subfield("a", "0456789012 (reel 1)")]))
        assert r.isbn == "0456789012"

    def test_isbn_with_x(self):
        r = Record()
        r.add_field(Field("020", Indicators(" ", " "), [Subfield("a", "006073132X")]))
        assert r.isbn == "006073132X"

    def test_issn(self):
        r = Record()
        r.add_field(Field("022", Indicators("0", ""), [Subfield("a", "0395-2037")]))
        assert r.issn == "0395-2037"

    def test_issn_none(self):
        assert Record().issn is None

    def test_issnl(self):
        r = Record()
        r.add_field(Field("022", Indicators("0", ""), [Subfield("l", "0395-2037")]))
        assert r.issnl == "0395-2037"

    def test_issnl_none(self):
        assert Record().issnl is None

    def test_author_from_100(self):
        r = Record()
        r.add_field(Field("100", Indicators("1", "0"), [Subfield("a", "Doe, John,"), Subfield("d", "1990-.")]))
        assert r.author == "Doe, John, 1990-."

    def test_author_none(self):
        assert Record().author is None

    def test_author_from_110(self):
        r = Record()
        r.add_field(Field("110", Indicators("2", " "), [Subfield("a", "Corp Inc.")]))
        assert r.author == "Corp Inc."

    def test_uniformtitle_from_130(self):
        r = Record()
        r.add_field(Field("130", Indicators("0", " "), [Subfield("a", "Tosefta."), Subfield("l", "English.")]))
        assert r.uniformtitle == "Tosefta. English."

    def test_uniformtitle_from_240(self):
        r = Record()
        r.add_field(Field("240", Indicators("1", "4"), [Subfield("a", "Papers."), Subfield("l", "French.")]))
        assert r.uniformtitle == "Papers. French."

    def test_uniformtitle_none(self):
        assert Record().uniformtitle is None

    def test_subjects(self):
        r = _make_full_record()
        assert len(r.subjects) == 1
        assert r.subjects[0].tag == "650"

    def test_subjects_empty(self):
        assert Record().subjects == []

    def test_addedentries(self):
        r = Record()
        r.add_field(Field("700", Indicators("1", "0"), [Subfield("a", "Editor.")]))
        r.add_field(Field("730", Indicators("0", " "), [Subfield("a", "Series.")]))
        assert len(r.addedentries) == 2

    def test_addedentries_empty(self):
        assert Record().addedentries == []

    def test_location(self):
        r = _make_full_record()
        assert len(r.location) == 1
        assert r.location[0]["a"] == "DLC"

    def test_notes(self):
        r = Record()
        r.add_field(Field("500", Indicators(" ", " "), [Subfield("a", "A note.")]))
        r.add_field(Field("520", Indicators(" ", " "), [Subfield("a", "Summary.")]))
        assert len(r.notes) == 2

    def test_physicaldescription(self):
        r = _make_full_record()
        assert len(r.physicaldescription) == 1

    def test_publisher_from_260(self):
        r = Record()
        r.add_field(Field("260", Indicators(" ", " "), [Subfield("b", "Publisher,")]))
        assert r.publisher == "Publisher,"

    def test_publisher_from_264(self):
        r = Record()
        r.add_field(Field("264", Indicators(" ", "1"), [Subfield("b", "Penguin,")]))
        assert r.publisher == "Penguin,"

    def test_publisher_264_wrong_indicator(self):
        r = Record()
        r.add_field(Field("264", Indicators(" ", "2"), [Subfield("b", "Distributor,")]))
        assert r.publisher is None

    def test_publisher_none(self):
        assert Record().publisher is None

    def test_pubyear_from_260(self):
        r = Record()
        r.add_field(Field("260", Indicators(" ", " "), [Subfield("c", "1955.")]))
        assert r.pubyear == "1955."

    def test_pubyear_from_264(self):
        r = Record()
        r.add_field(Field("264", Indicators(" ", "1"), [Subfield("c", "2023.")]))
        assert r.pubyear == "2023."

    def test_pubyear_none(self):
        assert Record().pubyear is None

    def test_series(self):
        r = Record()
        r.add_field(Field("490", Indicators("1", " "), [Subfield("a", "Series Name")]))
        r.add_field(Field("830", Indicators(" ", "0"), [Subfield("a", "Series Traced")]))
        assert len(r.series) == 2

    def test_sudoc(self):
        r = Record()
        r.add_field(Field("086", Indicators("0", " "), [Subfield("a", "Y 4.J 89/1:109/")]))
        assert r.sudoc == "Y 4.J 89/1:109/"


# ===================================================================
# 5. RECORD ENCODING / DECODING (as_marc round-trip)
# ===================================================================


class TestRecordEncoding:
    def test_simple_roundtrip(self):
        r = _make_simple_record()
        marc = r.as_marc()
        r2 = Record(marc)
        assert r2["245"]["a"] == "Test Title /"
        assert r2["245"]["c"] == "Test Author."

    def test_full_record_roundtrip(self):
        r = _make_full_record()
        marc = r.as_marc()
        r2 = Record(marc)
        assert r2["001"].data == "ocm12345678"
        assert r2["100"]["a"] == "Salinger, J. D."
        assert r2["245"]["a"] == "The catcher in the rye /"

    def test_leader_length_correct(self):
        r = _make_simple_record()
        marc = r.as_marc()
        stated_length = int(marc[0:5])
        assert stated_length == len(marc)

    def test_leader_base_address_correct(self):
        r = _make_simple_record()
        marc = r.as_marc()
        base_addr = int(marc[12:17])
        # base address = leader (24) + directory + end-of-field
        assert base_addr > LEADER_LEN

    def test_end_of_record_marker(self):
        r = _make_simple_record()
        marc = r.as_marc()
        assert marc[-1] == ord(END_OF_RECORD)

    def test_unicode_roundtrip(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Mus\u00e9e d'art")]))
        marc = r.as_marc()
        r2 = Record(marc)
        assert r2["245"]["a"] == "Mus\u00e9e d'art"

    def test_as_marc_sets_coding_scheme(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "Title")]))
        marc = r.as_marc()
        assert marc[9] == ord("a")  # coding scheme = UTF-8

    def test_as_marc_consistency(self):
        r = Record()
        leader_type = type(r.leader)
        r.as_marc()
        assert type(r.leader) == leader_type

    def test_no_leader_gives_default(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "The pragmatic programmer")]))
        marc = r.as_marc()
        assert marc[0:24] == b"00067    a2200037   4500"

    def test_empty_record_as_marc(self):
        r = Record()
        marc = r.as_marc()
        assert len(marc) > 0
        assert marc[-1] == ord(END_OF_RECORD)


class TestRecordEncodingFromFile:
    def test_encode_decode_one(self):
        with fixture_path("one.dat").open("rb") as fh:
            original = fh.read()
        with fixture_path("one.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert record is not None
            assert original == record.as_marc()

    def test_encode_decode_alphatag(self):
        with fixture_path("alphatag.dat").open("rb") as fh:
            original = fh.read()
        with fixture_path("alphatag.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert isinstance(record, Record)
            assert original == record.as_marc()


# ===================================================================
# 6. RECORD DICT / JSON
# ===================================================================


class TestRecordDict:
    def test_as_dict_structure(self):
        r = _make_simple_record()
        d = r.as_dict()
        assert "leader" in d
        assert "fields" in d
        assert isinstance(d["leader"], str)
        assert isinstance(d["fields"], list)

    def test_as_dict_control_field(self):
        r = Record()
        r.add_field(Field("008", data="some data"))
        d = r.as_dict()
        assert d["fields"][0] == {"008": "some data"}

    def test_as_dict_data_field(self):
        r = Record()
        r.add_field(Field("245", Indicators("1", "0"), [Subfield("a", "Title")]))
        d = r.as_dict()
        field_dict = d["fields"][0]["245"]
        assert field_dict["ind1"] == "1"
        assert field_dict["ind2"] == "0"
        assert field_dict["subfields"] == [{"a": "Title"}]

    def test_as_json(self):
        r = _make_simple_record()
        j = json.loads(r.as_json())
        assert "leader" in j
        assert "fields" in j

    def test_as_json_roundtrip(self):
        r = _make_full_record()
        j = r.as_json()
        parsed = json.loads(j)
        reader = JSONReader(j)
        r2 = next(iter(reader))
        assert r2["245"]["a"] == "The catcher in the rye /"


# ===================================================================
# 7. RECORD STRING REPR
# ===================================================================


class TestRecordStr:
    def test_str_has_leader(self):
        r = _make_simple_record()
        text = str(r)
        assert text.startswith("=LDR  ")

    def test_str_has_fields(self):
        r = _make_simple_record()
        text = str(r)
        assert "=245" in text

    def test_str_ends_with_newline(self):
        r = _make_simple_record()
        assert str(r).endswith("\n")


# ===================================================================
# 8. ORDERED / GROUPED FIELDS
# ===================================================================


class TestOrderedFields:
    def test_add_ordered_field(self):
        r = Record()
        for tag in ("999", "888", "111", "666", "988", "998"):
            r.add_ordered_field(Field(tag, Indicators("0", "0"), [Subfield("a", "x")]))
        numeric_tags = [int(f.tag) for f in r if f.tag.isdigit()]
        assert numeric_tags == sorted(numeric_tags)

    def test_add_grouped_field(self):
        r = Record()
        for tag in ("999", "888", "111", "666", "988", "998"):
            r.add_grouped_field(Field(tag, Indicators("0", "0"), [Subfield("a", "x")]))
        tags = [f.tag for f in r if f.tag.isdigit()]
        assert tags == ["111", "666", "888", "999", "988", "998"]

    def test_add_ordered_field_with_alpha(self):
        r = Record()
        r.add_ordered_field(Field("500", Indicators("0", "0"), [Subfield("a", "x")]))
        r.add_ordered_field(Field("abc", Indicators("0", "0"), [Subfield("a", "x")]))
        r.add_ordered_field(Field("100", Indicators("0", "0"), [Subfield("a", "x")]))
        # alpha tags go to end, numeric are sorted
        numeric = [int(f.tag) for f in r if f.tag.isdigit()]
        assert numeric == sorted(numeric)


# ===================================================================
# 9. DEEP COPY
# ===================================================================


class TestRecordCopy:
    def test_deepcopy_independent(self):
        r1 = _make_full_record()
        r2 = deepcopy(r1)
        r1.add_field(Field("999", Indicators(" ", " "), [Subfield("a", "r1")]))
        r2.add_field(Field("999", Indicators(" ", " "), [Subfield("a", "r2")]))
        assert r1["999"]["a"] == "r1"
        assert r2["999"]["a"] == "r2"

    def test_deepcopy_preserves_data(self):
        r1 = _make_full_record()
        r2 = deepcopy(r1)
        assert r2["245"]["a"] == r1["245"]["a"]
        assert r2["001"].data == r1["001"].data


# ===================================================================
# 10. MARC READER
# ===================================================================


class TestMARCReaderFile:
    def test_read_test_dat(self):
        with fixture_path("test.dat").open("rb") as fh:
            reader = MARCReader(fh)
            records = list(reader)
        assert len(records) == 10

    def test_each_record_has_leader(self):
        with fixture_path("test.dat").open("rb") as fh:
            for record in MARCReader(fh):
                assert record is not None
                assert len(str(record.leader)) == LEADER_LEN

    def test_read_from_bytes(self):
        with fixture_path("test.dat").open("rb") as fh:
            data = fh.read()
        records = list(MARCReader(data))
        assert len(records) == 10

    def test_map_records(self):
        count = 0

        def f(r):
            nonlocal count
            count += 1

        with fixture_path("test.dat").open("rb") as fh:
            rmarc.map_records(f, fh)
        assert count == 10

    def test_multi_map_records(self):
        count = 0

        def f(r):
            nonlocal count
            count += 1

        with fixture_path("test.dat").open("rb") as fh1, fixture_path("test.dat").open("rb") as fh2:
            rmarc.map_records(f, fh1, fh2)
        assert count == 20

    def test_bad_subfield_code(self):
        with fixture_path("bad_subfield_code.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert isinstance(record, Record)
            assert record["245"]["a"] == "ActivePerl with ASP and ADO /"

    def test_bad_indicator(self):
        with fixture_path("bad_indicator.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert isinstance(record, Record)
            assert record["245"]["a"] == "Aristocrats of color :"

    def test_regression45(self):
        with fixture_path("regression45.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert isinstance(record, Record)
            assert record["752"]["a"] == "Russian Federation"

    def test_close(self):
        fh = fixture_path("test.dat").open("rb")
        reader = MARCReader(fh)
        reader.close()
        assert fh.closed


class TestMARCReaderTruncated:
    def test_empty_data(self):
        records = list(MARCReader(b""))
        assert len(records) == 0

    def test_partial_length(self):
        reader = MARCReader(b"0012")
        records = list(reader)
        assert len(records) == 1
        assert records[0] is None
        assert isinstance(reader.current_exception, TruncatedRecord)
        assert reader.current_chunk == b"0012"

    def test_bad_length(self):
        reader = MARCReader(b"0012X")
        records = list(reader)
        assert len(records) == 1
        assert records[0] is None
        assert isinstance(reader.current_exception, RecordLengthInvalid)

    def test_partial_data(self):
        reader = MARCReader(b"00120cam")
        records = list(reader)
        assert len(records) == 1
        assert records[0] is None
        assert isinstance(reader.current_exception, TruncatedRecord)

    def test_missing_end_of_record(self):
        reader = MARCReader(b"00006 ")
        records = list(reader)
        assert len(records) == 1
        assert records[0] is None
        assert isinstance(reader.current_exception, EndOfRecordNotFound)


class TestMARCReaderPermissive:
    def test_permissive_bad_records(self):
        """Test that bad_records.mrc yields the expected exceptions in order."""
        with fixture_path("bad_records.mrc").open("rb") as fh:
            reader = MARCReader(fh)
            expected = [
                None,  # good record
                BaseAddressInvalid,
                BaseAddressNotFound,
                RecordDirectoryInvalid,
                UnicodeDecodeError,
                ValueError,
                NoFieldsFound,
                None,  # good record
                TruncatedRecord,
            ]
            for exc_type in expected:
                record = next(reader)
                assert reader.current_chunk is not None
                if exc_type is None:
                    assert record is not None
                    assert reader.current_exception is None
                    assert record["245"]["a"] == "The pragmatic programmer : "
                else:
                    assert record is None
                    assert isinstance(reader.current_exception, exc_type)


class TestRecordDecode:
    def test_bad_leader(self):
        r = Record()
        with pytest.raises(RecordLeaderInvalid):
            r.decode_marc(b"foo")

    def test_bad_base_address(self):
        r = Record()
        with pytest.raises(BaseAddressInvalid):
            r.decode_marc(b"00695cam  2200241Ia 45x00")


# ===================================================================
# 11. JSON READER
# ===================================================================


class TestJSONReader:
    def test_read_json_file(self):
        with fixture_path("test.json").open() as fh:
            data = fh.read()
        reader = JSONReader(data)
        records = list(reader)
        assert len(records) > 0
        for r in records:
            assert isinstance(r, Record)

    def test_json_roundtrip(self):
        with fixture_path("test.json").open() as fh:
            expected = json.load(fh, strict=False)
        with fixture_path("test.json").open() as fh:
            reader = JSONReader(fh.read())
        for i, rec in enumerate(reader):
            deserialized = json.loads(rec.as_json(), strict=False)
            assert deserialized == expected[i]

    def test_single_record_json(self):
        with fixture_path("test.json").open() as fh:
            all_json = json.load(fh, strict=False)
        single = json.dumps(all_json[0])
        reader = JSONReader(single)
        records = list(reader)
        assert len(records) == 1

    def test_parse_json_to_array(self):
        with fixture_path("one.json").open() as fh:
            records = parse_json_to_array(fh)
        assert len(records) > 0
        assert isinstance(records[0], Record)


# ===================================================================
# 12. MARC MAKER READER
# ===================================================================


class TestMARCMakerReader:
    @pytest.fixture
    def marcmaker_text(self):
        with fixture_path("test.dat").open("rb") as fh:
            return [str(record) for record in MARCReader(fh)]

    def test_round_trip(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        for i, record in enumerate(reader):
            assert str(record) == marcmaker_text[i]

    def test_parse_leader(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        leader = reader._parse_line("=LDR  00755cam  22002414a 4500")
        assert str(leader) == "00755cam  22002414a 4500"

    def test_parse_control_field(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        field = reader._parse_line("=008  010314s1999fr||||||||||||||||fre")
        assert isinstance(field, Field)
        assert field.tag == "008"
        assert field.data == "010314s1999fr||||||||||||||||fre"

    def test_parse_data_field(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        field = reader._parse_line("=028  01$aSTMA 8007$bTamla Motown Records")
        assert isinstance(field, Field)
        assert field.tag == "028"
        assert field.indicator1 == "0"
        assert field.indicator2 == "1"
        assert field["a"] == "STMA 8007"
        assert field["b"] == "Tamla Motown Records"

    def test_parse_line_no_equals(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        with pytest.raises(ValueError, match='Line should start with a "="'):
            reader._parse_line("028  01$aSTMA 8007")

    def test_parse_line_single_space(self, marcmaker_text):
        reader = MARCMakerReader("\n".join(marcmaker_text))
        with pytest.raises(ValueError, match="two spaces"):
            reader._parse_line("=028 01$aSTMA 8007")

    def test_invalid_lines(self):
        lines = [
            "=LDR 00755cam  22002414a 4500",
            "LDR  00755cam  22002414a 4500",
            "=008",
            "=009 00755cam",
            "=999",
        ]
        for line in lines:
            reader = MARCMakerReader(line)
            with pytest.raises(PymarcException, match="Unable to parse line"):
                next(reader)

    def test_open_from_file(self, marcmaker_text, tmp_path):
        filepath = tmp_path / "test.mrk"
        filepath.write_text("\n".join(marcmaker_text), encoding="utf-8")
        reader = MARCMakerReader(str(filepath), encoding="utf-8")
        record = next(reader)
        assert str(record) == marcmaker_text[0]


# ===================================================================
# 13. WRITERS (all using tmp_path)
# ===================================================================


class TestMARCWriter:
    def test_write_and_read_back(self, tmp_path):
        filepath = tmp_path / "output.mrc"
        with open(filepath, "wb") as fh:
            writer = MARCWriter(fh)
            writer.write(_make_simple_record())
            writer.close()
        with open(filepath, "rb") as fh:
            record = next(MARCReader(fh))
            assert record is not None
            assert record["245"]["a"] == "Test Title /"

    def test_write_multiple_records(self, tmp_path):
        filepath = tmp_path / "multi.mrc"
        with open(filepath, "wb") as fh:
            writer = MARCWriter(fh)
            for _ in range(5):
                writer.write(_make_simple_record())
            writer.close()
        with open(filepath, "rb") as fh:
            records = list(MARCReader(fh))
        assert len(records) == 5

    def test_close_closes_handle(self):
        fh = BytesIO()
        writer = MARCWriter(fh)
        writer.close()
        assert fh.closed

    def test_close_false_keeps_handle_open(self):
        fh = BytesIO()
        writer = MARCWriter(fh)
        writer.close(close_fh=False)
        assert not fh.closed

    def test_write_non_record_raises(self):
        fh = BytesIO()
        writer = MARCWriter(fh)
        with pytest.raises(WriteNeedsRecord):
            writer.write("not a record")

    def test_write_full_record_roundtrip(self, tmp_path):
        r = _make_full_record()
        filepath = tmp_path / "full.mrc"
        with open(filepath, "wb") as fh:
            writer = MARCWriter(fh)
            writer.write(r)
            writer.close()
        with open(filepath, "rb") as fh:
            r2 = next(MARCReader(fh))
            assert r2 is not None
            assert r2["001"].data == "ocm12345678"
            assert r2["245"]["a"] == "The catcher in the rye /"


class TestJSONWriter:
    def test_write_0_records(self):
        fh = StringIO()
        writer = JSONWriter(fh)
        writer.close(close_fh=False)
        assert json.loads(fh.getvalue()) == []

    def test_write_1_record(self):
        fh = StringIO()
        writer = JSONWriter(fh)
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        result = json.loads(fh.getvalue())
        assert len(result) == 1
        assert "245" in result[0]["fields"][0]

    def test_write_3_records(self):
        fh = StringIO()
        writer = JSONWriter(fh)
        for _ in range(3):
            writer.write(_make_simple_record())
        writer.close(close_fh=False)
        result = json.loads(fh.getvalue())
        assert len(result) == 3

    def test_close_closes_handle(self):
        fh = StringIO()
        writer = JSONWriter(fh)
        writer.close()
        assert fh.closed

    def test_close_false_keeps_open(self):
        fh = StringIO()
        writer = JSONWriter(fh)
        writer.close(close_fh=False)
        assert not fh.closed

    def test_write_to_file(self, tmp_path):
        filepath = tmp_path / "output.json"
        with open(filepath, "w") as fh:
            writer = JSONWriter(fh)
            writer.write(_make_full_record())
            writer.close()
        with open(filepath) as fh:
            result = json.load(fh)
        assert len(result) == 1
        assert result[0]["leader"]


class TestTextWriter:
    def test_write_0_records(self):
        fh = StringIO()
        writer = TextWriter(fh)
        writer.close(close_fh=False)
        assert fh.getvalue() == ""

    def test_write_1_record(self):
        fh = StringIO()
        writer = TextWriter(fh)
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        text = fh.getvalue()
        assert text.startswith("=LDR")
        assert "=245" in text

    def test_write_empty_record(self):
        fh = StringIO()
        writer = TextWriter(fh)
        writer.write(Record())
        writer.close(close_fh=False)
        text = fh.getvalue()
        assert "=LDR" in text

    def test_write_multiple_records(self):
        fh = StringIO()
        writer = TextWriter(fh)
        writer.write(_make_simple_record())
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        text = fh.getvalue()
        assert text.count("=LDR") == 2

    def test_close_closes_handle(self):
        fh = StringIO()
        writer = TextWriter(fh)
        writer.close()
        assert fh.closed

    def test_write_to_file(self, tmp_path):
        filepath = tmp_path / "output.txt"
        with open(filepath, "w") as fh:
            writer = TextWriter(fh)
            writer.write(_make_full_record())
            writer.close()
        content = filepath.read_text()
        assert "=245" in content
        assert "=001" in content


class TestXMLWriter:
    def test_write_0_records(self):
        fh = BytesIO()
        writer = XMLWriter(fh)
        writer.close(close_fh=False)
        xml = fh.getvalue()
        assert b"<collection" in xml
        assert b"</collection>" in xml

    def test_write_1_record(self):
        fh = BytesIO()
        writer = XMLWriter(fh)
        writer.write(_make_simple_record())
        writer.close(close_fh=False)
        xml = fh.getvalue()
        assert b"<record>" in xml or b"<record " in xml
        assert b"<leader>" in xml

    def test_write_3_records(self):
        fh = BytesIO()
        writer = XMLWriter(fh)
        for _ in range(3):
            writer.write(_make_simple_record())
        writer.close(close_fh=False)
        xml = fh.getvalue()
        assert xml.count(b"<leader>") == 3

    def test_close_closes_handle(self):
        fh = BytesIO()
        writer = XMLWriter(fh)
        writer.close()
        assert fh.closed

    def test_close_false_keeps_open(self):
        fh = BytesIO()
        writer = XMLWriter(fh)
        writer.close(close_fh=False)
        assert not fh.closed

    def test_write_to_file(self, tmp_path):
        filepath = tmp_path / "output.xml"
        with open(filepath, "wb") as fh:
            writer = XMLWriter(fh)
            writer.write(_make_full_record())
            writer.close()
        content = filepath.read_bytes()
        assert b"<collection" in content
        assert b"</collection>" in content


# ===================================================================
# 14. XML PARSING
# ===================================================================


class TestXMLParsing:
    def test_map_xml(self):
        seen = []
        map_xml(lambda r: seen.append(r), str(fixture_path("batch.xml")))
        assert len(seen) == 2

    def test_multi_map_xml(self):
        seen = []
        map_xml(lambda r: seen.append(r), str(fixture_path("batch.xml")), str(fixture_path("batch.xml")))
        assert len(seen) == 4

    def test_parse_xml_to_array(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        assert len(records) == 2
        assert isinstance(records[0], Record)
        assert isinstance(records[1], Record)

    def test_parse_xml_content(self):
        records = parse_xml_to_array(str(fixture_path("batch.xml")))
        r = records[0]
        assert len(r.get_fields()) == 18
        assert r["008"].data == "910926s1957    nyuuun              eng  "
        assert r["245"]["a"] == "The Great Ray Charles"

    def test_record_to_xml_roundtrip(self):
        r1 = parse_xml_to_array(str(fixture_path("batch.xml")))[0]
        xml = record_to_xml(r1)
        r2 = parse_xml_to_array(BytesIO(xml))[0]
        assert r1.leader.leader == r2.leader.leader
        assert len(r1.get_fields()) == len(r2.get_fields())
        for f1, f2 in zip(r1.get_fields(), r2.get_fields()):
            assert f1.tag == f2.tag
            if f1.control_field:
                assert f1.data == f2.data
            else:
                assert f1.indicators == f2.indicators

    def test_xml_namespace(self):
        with fixture_path("test.dat").open("rb") as fh:
            record = next(MARCReader(fh))
        xml_no_ns = record_to_xml(record, namespace=False)
        assert b'xmlns="http://www.loc.gov/MARC21/slim"' not in xml_no_ns
        xml_ns = record_to_xml(record, namespace=True)
        assert b'xmlns="http://www.loc.gov/MARC21/slim"' in xml_ns

    def test_strict_parsing(self):
        with fixture_path("batch.xml").open() as fh:
            records = parse_xml_to_array(fh, strict=True)
        assert len(records) == 2

    def test_bad_tag_xml(self):
        with fixture_path("bad_tag.xml").open() as fh, pytest.raises(RecordLeaderInvalid):
            parse_xml_to_array(fh)

    def test_write_then_parse_xml(self, tmp_path):
        filepath = tmp_path / "roundtrip.xml"
        r = _make_full_record()
        with open(filepath, "wb") as fh:
            writer = XMLWriter(fh)
            writer.write(r)
            writer.close()
        records = parse_xml_to_array(str(filepath))
        assert len(records) == 1
        assert records[0]["245"]["a"] == "The catcher in the rye /"


# ===================================================================
# 15. JSON PARSING
# ===================================================================


class TestJSONParsing:
    def test_parse_json_to_array_one(self):
        with fixture_path("one.json").open() as fh:
            records = parse_json_to_array(fh)
        assert len(records) > 0

    def test_parse_json_matches_dat(self):
        with fixture_path("one.json").open() as fh:
            json_records = parse_json_to_array(fh)
        with fixture_path("one.dat").open("rb") as fh:
            dat_records = list(MARCReader(fh))
        assert len(json_records) == len(dat_records)
        for jr, dr in zip(json_records, dat_records):
            assert jr.as_marc() == dr.as_marc()

    def test_parse_json_matches_xml(self):
        with fixture_path("batch.json").open() as fh:
            json_records = parse_json_to_array(fh)
        xml_records = parse_xml_to_array(str(fixture_path("batch.xml")))
        assert len(json_records) == len(xml_records)
        for jr, xr in zip(json_records, xml_records):
            assert jr.as_marc() == xr.as_marc()


# ===================================================================
# 16. MARC-8 / CHARACTER ENCODING
# ===================================================================


class TestMARC8:
    def test_marc8_reader_raw(self):
        with fixture_path("marc8.dat").open("rb") as fh:
            r = next(MARCReader(fh, to_unicode=False))
        assert isinstance(r, Record)
        assert isinstance(r["240"], RawField)
        utitle = r["240"]["a"]
        assert isinstance(utitle, bytes)
        assert utitle == b"De la solitude \xe1a la communaut\xe2e."

    def test_marc8_reader_to_unicode(self):
        with fixture_path("marc8.dat").open("rb") as fh:
            r = next(MARCReader(fh, to_unicode=True))
        assert isinstance(r, Record)
        utitle = r["240"]["a"]
        assert isinstance(utitle, str)
        assert utitle == "De la solitude \xe0 la communaut\xe9."

    def test_marc8_to_unicode_function(self):
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
                assert marc8_to_unicode(marc8).encode("utf8") == utf8
            assert count == 1515

    def test_marc8_read_write_roundtrip(self, tmp_path):
        with fixture_path("marc8.dat").open("rb") as fh:
            r = next(MARCReader(fh, to_unicode=False))
        assert isinstance(r, Record)
        filepath = tmp_path / "marc8_out.dat"
        with open(filepath, "wb") as fh:
            fh.write(r.as_marc())
        with open(filepath, "rb") as fh:
            r2 = next(MARCReader(fh, to_unicode=False))
        assert isinstance(r2, Record)
        assert isinstance(r2["240"], RawField)
        assert r2["240"]["a"] == b"De la solitude \xe1a la communaut\xe2e."

    def test_subscript_2(self):
        assert marc8_to_unicode(b"CO\x1bb2\x1bs is a gas") == "CO\u2082 is a gas"
        assert marc8_to_unicode(b"CO\x1bb2\x1bs") == "CO\u2082"

    def test_eszett_euro(self):
        assert marc8_to_unicode(b"ESZETT SYMBOL: \xc7 is U+00DF") == "ESZETT SYMBOL: \u00df is U+00DF"
        assert marc8_to_unicode(b"EURO SIGN: \xc8 is U+20AC") == "EURO SIGN: \u20ac is U+20AC"

    def test_alif(self):
        assert marc8_to_unicode(b"ALIF: \xae is U+02BC") == "ALIF: \u02bc is U+02BC"

    def test_bad_eacc_sequence(self):
        with fixture_path("bad_eacc_encoding.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True, hide_utf8_warnings=True))
        assert isinstance(record, Record)
        assert len(record["880"]["a"]) == 12
        assert record["880"]["a"].endswith(" ")

    def test_bad_escape(self):
        with fixture_path("bad_marc8_escape.dat").open("rb") as fh:
            r = next(MARCReader(fh, to_unicode=True))
        assert isinstance(r, Record)
        assert r["260"]["b"] == "La Soci\xe9t\x1b,"

    def test_cp1251_encoding(self):
        with fixture_path("1251.dat").open("rb") as fh:
            r = next(MARCReader(fh, file_encoding="cp1251"))
        assert isinstance(r, Record)
        assert r["245"]["a"] == "Основы гидравлического расчета инженерных сетей"


class TestUTF8:
    def test_utf8_xml_fields(self):
        field_count = 0

        def process_xml(record):
            nonlocal field_count
            for _ in record.get_fields():
                field_count += 1

        rmarc.map_xml(process_xml, str(fixture_path("utf8.xml")))
        assert field_count == 8

    def test_utf8_write_copy(self, tmp_path):
        filepath = tmp_path / "utf8_copy.dat"
        with open(filepath, "wb") as fh:
            writer = MARCWriter(fh)
            new_record = Record(to_unicode=True, force_utf8=True)

            def process_xml(record):
                new_record.leader = record.leader
                for field in record.get_fields():
                    new_record.add_field(field)

            rmarc.map_xml(process_xml, str(fixture_path("utf8.xml")))
            writer.write(new_record)
            writer.close()
        # Verify the file was written
        assert filepath.stat().st_size > 0

    def test_diacritic_str(self):
        """Issue 74: should not raise UnicodeEncodeError."""
        with fixture_path("diacritic.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            str(record)  # should not raise

    def test_writing_unicode(self, tmp_path):
        filepath = tmp_path / "unicode.dat"
        record = Record()
        record.add_field(Field("245", Indicators("1", "0"), [Subfield("a", chr(0x1234))]))
        record.leader = Leader("         a              ")
        with open(filepath, "wb") as fh:
            writer = MARCWriter(fh)
            writer.write(record)
            writer.close()
        with open(filepath, "rb") as fh:
            r2 = next(MARCReader(fh, to_unicode=True))
            assert isinstance(r2, Record)
            assert r2["245"]["a"] == chr(0x1234)

    def test_utf8_with_leader_flag_raw(self):
        with fixture_path("utf8_with_leader_flag.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=False))
        assert isinstance(record, Record)
        assert record["240"]["a"] == b"De la solitude a\xcc\x80 la communaute\xcc\x81."

    def test_utf8_with_leader_flag_unicode(self):
        with fixture_path("utf8_with_leader_flag.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True))
        assert isinstance(record, Record)
        assert record["240"]["a"] == "De la solitude a" + chr(0x0300) + " la communaute" + chr(0x0301) + "."

    def test_utf8_without_flag_raw(self):
        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=False))
        assert isinstance(record, Record)
        assert record["240"]["a"] == b"De la solitude a\xcc\x80 la communaute\xcc\x81."

    def test_utf8_without_flag_force(self):
        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True, force_utf8=True, hide_utf8_warnings=True))
        assert isinstance(record, Record)
        assert record["240"]["a"] == "De la solitude a" + chr(0x0300) + " la communaute" + chr(0x0301) + "."

    def test_utf8_without_flag_lossy(self):
        """Without force_utf8, MARC-8 decoding loses the combining chars."""
        with fixture_path("utf8_without_leader_flag.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True, hide_utf8_warnings=True))
        assert isinstance(record, Record)
        # NOTE: This is correct behavior - without the UTF-8 flag, the reader
        # attempts MARC-8 decoding which loses the combining diacritical marks
        assert record["240"]["a"] == "De la solitude a   la communaute ."

    def test_marc8_to_unicode_conversion(self):
        """Test that decoding MARC-8 data to unicode and re-encoding produces expected bytes."""
        with fixture_path("marc8-to-unicode.dat").open("rb") as fh:
            expected_bytes = fh.read()
        with fixture_path("marc8.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True))
            assert record is not None
            record_bytes = record.as_marc()
            assert record_bytes[9] == ord("a")
            assert expected_bytes == record_bytes


# ===================================================================
# 17. CONSTANTS
# ===================================================================


class TestConstants:
    def test_leader_len(self):
        assert LEADER_LEN == 24

    def test_directory_entry_len(self):
        assert DIRECTORY_ENTRY_LEN == 12

    def test_subfield_indicator(self):
        assert chr(0x1F) == SUBFIELD_INDICATOR

    def test_end_of_field(self):
        assert chr(0x1E) == END_OF_FIELD

    def test_end_of_record(self):
        assert chr(0x1D) == END_OF_RECORD


# ===================================================================
# 18. EXCEPTIONS
# ===================================================================


class TestExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(RecordLengthInvalid, FatalReaderError)
        assert issubclass(TruncatedRecord, FatalReaderError)
        assert issubclass(EndOfRecordNotFound, FatalReaderError)
        assert issubclass(FatalReaderError, PymarcException)
        assert issubclass(RecordLeaderInvalid, PymarcException)
        assert issubclass(RecordDirectoryInvalid, PymarcException)
        assert issubclass(NoFieldsFound, PymarcException)
        assert issubclass(BaseAddressInvalid, PymarcException)
        assert issubclass(BaseAddressNotFound, PymarcException)
        assert issubclass(WriteNeedsRecord, PymarcException)
        assert issubclass(FieldNotFound, PymarcException)
        assert issubclass(BadLeaderValue, PymarcException)
        assert issubclass(MissingLinkedFields, PymarcException)

    def test_bad_subfield_code_warning(self):
        assert issubclass(BadSubfieldCodeWarning, Warning)

    def test_exception_str(self):
        assert str(RecordLengthInvalid())
        assert str(TruncatedRecord())
        assert str(EndOfRecordNotFound())
        assert str(RecordLeaderInvalid())
        assert str(RecordDirectoryInvalid())
        assert str(NoFieldsFound())
        assert str(BaseAddressInvalid())
        assert str(BaseAddressNotFound())
        assert str(WriteNeedsRecord())
        assert str(FieldNotFound())


# ===================================================================
# 19. CROSS-FORMAT ROUNDTRIP TESTS
# ===================================================================


class TestCrossFormatRoundtrip:
    """Test that records survive conversions between MARC binary, JSON, XML, and text."""

    def test_marc_to_json_to_marc(self, tmp_path):
        r1 = _make_full_record()
        json_str = r1.as_json()
        reader = JSONReader(json_str)
        r2 = next(iter(reader))
        assert r2["245"]["a"] == r1["245"]["a"]
        assert r2["001"].data == r1["001"].data

    def test_marc_to_xml_to_marc(self):
        r1 = _make_full_record()
        xml = record_to_xml(r1)
        r2 = parse_xml_to_array(BytesIO(xml))[0]
        assert r2["245"]["a"] == r1["245"]["a"]

    def test_marc_to_text_to_marc(self):
        r1 = _make_simple_record()
        text = str(r1)
        reader = MARCMakerReader(text)
        r2 = next(reader)
        assert str(r2) == str(r1)

    def test_file_roundtrip_all_formats(self, tmp_path):
        """Write to .mrc, read back, convert to JSON, XML, text, then verify."""
        r = _make_full_record()

        # Write binary
        mrc_path = tmp_path / "test.mrc"
        with open(mrc_path, "wb") as fh:
            MARCWriter(fh).write(r)

        # Read back
        with open(mrc_path, "rb") as fh:
            r2 = next(MARCReader(fh))
        assert r2["245"]["a"] == "The catcher in the rye /"

        # JSON roundtrip
        json_path = tmp_path / "test.json"
        with open(json_path, "w") as fh:
            writer = JSONWriter(fh)
            writer.write(r2)
            writer.close()
        with open(json_path) as fh:
            j = json.load(fh)
        assert len(j) == 1

        # XML roundtrip
        xml_path = tmp_path / "test.xml"
        with open(xml_path, "wb") as fh:
            writer = XMLWriter(fh)
            writer.write(r2)
            writer.close()
        r3 = parse_xml_to_array(str(xml_path))
        assert len(r3) == 1
        assert r3[0]["245"]["a"] == "The catcher in the rye /"


# ===================================================================
# 20. EDGE CASES AND MISC
# ===================================================================


class TestEdgeCases:
    def test_record_with_many_fields(self):
        r = Record()
        for i in range(100):
            r.add_field(Field(f"{(i % 900) + 100:03d}", Indicators(" ", " "), [Subfield("a", f"Field {i}")]))
        marc = r.as_marc()
        r2 = Record(marc)
        assert len(r2.get_fields()) == 100

    def test_empty_subfield_value(self):
        f = Field("245", Indicators("0", "1"), [Subfield("a", "")])
        assert f["a"] == ""
        marc = f.as_marc("utf-8")
        assert marc == b"01\x1fa\x1e"

    def test_special_chars_in_subfields(self):
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", 'Title with <html> & "quotes"')]))
        marc = r.as_marc()
        r2 = Record(marc)
        assert r2["245"]["a"] == 'Title with <html> & "quotes"'

    def test_record_alpha_tags(self):
        r = Record()
        r.add_field(Field("CAT", Indicators(" ", " "), [Subfield("a", "foo")]))
        r.add_field(Field("CAT", Indicators(" ", " "), [Subfield("b", "bar")]))
        fields = r.get_fields("CAT")
        assert len(fields) == 2
        assert r["CAT"]["a"] == "foo"

    def test_multiple_isbn(self):
        with fixture_path("multi_isbn.dat").open("rb") as fh:
            record = next(MARCReader(fh))
            assert record is not None
            assert record.isbn == "0914378287"

    def test_record_from_unimarc(self):
        with fixture_path("testunimarc.dat").open("rb") as fh:
            record = Record(fh.read(), force_utf8=True)
        assert len(record.get_fields("899")) != 0
        record.remove_fields("899")
        assert len(record.get_fields("899")) == 0

    def test_map_marc8_record(self):
        from rmarc.record import map_marc8_record

        with fixture_path("marc8.dat").open("rb") as fh:
            record = next(MARCReader(fh, to_unicode=True))
            assert record is not None
            mapped = map_marc8_record(record)
            assert mapped.as_marc() == record.as_marc()

    def test_as_marc_with_explicit_leader_preserved(self):
        """Setting an explicit leader should be preserved through as_marc()."""
        r = Record()
        r.add_field(Field("245", Indicators("0", "1"), [Subfield("a", "The pragmatic programmer")]))
        r.leader = Leader("00067    a2200037   4500")
        leader_before = str(r.leader)
        r.as_marc()
        leader_after = str(r.leader)
        assert leader_before == leader_after

    def test_record_create_force_utf8(self):
        r = Record(force_utf8=True)
        assert r.leader[9] == "a"
