"""Generated, small MARC records checked against pymarc 5.4.0.

Run: python -m pytest test_pymarc/test_hypothesis_codec.py --hypothesis-show-statistics
Hypothesis prints a minimized example on failure and saves it for the next run.
No external corpus or network is required. Both native and fallback paths run.
"""

from io import BytesIO
from unittest.mock import patch

import pymarc
import pytest
import rmarc
from hypothesis import given, settings
from hypothesis import strategies as st

TEXT = st.text(st.characters(exclude_categories=("Cs",), exclude_characters="\x1d\x1e\x1f"), max_size=48)
CODE = st.sampled_from(list("abcxyz0126"))
INDICATORS = st.tuples(st.sampled_from(list(" 0129")), st.sampled_from(list(" 0129")))
SUBFIELDS = st.lists(st.tuples(CODE, TEXT), max_size=6)
CONTROL = st.tuples(st.sampled_from(["001", "005", "008"]), TEXT)
DATA = st.tuples(st.sampled_from(["010", "020", "100", "245", "500", "650", "880", "999"]), INDICATORS, SUBFIELDS)
RECORD = st.lists(st.one_of(CONTROL, DATA), max_size=12)
PROPERTY = settings(max_examples=150, deadline=None)


def make_record(module, fields, **kwargs):
    record = module.Record(**kwargs)
    for spec in fields:
        if len(spec) == 2:
            field = module.Field(spec[0], data=spec[1])
        else:
            field = module.Field(spec[0], indicators=spec[1], subfields=[module.Subfield(*s) for s in spec[2]])
        record.add_field(field)
    return record


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(fields=RECORD)
def test_unicode_write_and_read_match_pymarc(native, fields):
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        expected = make_record(pymarc, fields)
        actual = make_record(rmarc, fields)
        encoded = expected.as_marc()
        assert actual.as_marc() == encoded
        assert actual.as_marc21() == encoded
        assert str(actual.leader) == str(expected.leader)
        if not fields:
            # pymarc writes an empty record but deliberately refuses to read it.
            with pytest.raises(pymarc.exceptions.NoFieldsFound):
                pymarc.Record(encoded)
            with pytest.raises(rmarc.exceptions.NoFieldsFound):
                rmarc.Record(encoded)
            return
        reference = pymarc.Record(encoded)
        decoded = rmarc.Record(encoded)
        assert decoded.as_dict() == reference.as_dict()
        assert decoded.as_marc() == reference.as_marc()


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(fields=RECORD, edits=st.lists(st.tuples(st.integers(0, 4), CODE, TEXT), max_size=12))
def test_mutable_lists_and_lookups_match_pymarc(native, fields, edits):
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        records = [make_record(module, fields) for module in (pymarc, rmarc)]
        for operation, code, value in edits:
            for module, record in zip((pymarc, rmarc), records, strict=True):
                alias = record.get_fields()
                assert alias is record.fields
                if operation == 0:
                    alias.append(module.Field("245", subfields=[module.Subfield(code, value)]))
                elif operation == 1:
                    alias.reverse()
                elif operation == 2 and alias:
                    alias.pop(0)
                else:
                    for field in alias:
                        if not field.control_field:
                            if operation == 3:
                                field.subfields.append(module.Subfield(code, value))
                            else:
                                field.subfields[:] = [module.Subfield(code, value)]
                            break
            expected, actual = records
            assert actual.as_dict() == expected.as_dict()
            assert actual.as_marc() == expected.as_marc()
            assert actual.title == expected.title
            assert [f.tag for f in actual.get_fields("650", "245", "245")] == [
                f.tag for f in expected.get_fields("650", "245", "245")
            ]


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(value=TEXT, force_utf8=st.booleans())
def test_legacy_writer_bytes_or_exact_encoding_error(native, value, force_utf8):
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        fields = [("245", (" ", " "), [("a", value)])]
        expected = make_record(pymarc, fields, to_unicode=False, force_utf8=force_utf8)
        actual = make_record(rmarc, fields, to_unicode=False, force_utf8=force_utf8)
        try:
            encoded = expected.as_marc()
        except UnicodeEncodeError as error:
            with pytest.raises(UnicodeEncodeError) as caught:
                actual.as_marc()
            assert caught.value.args == error.args
        else:
            assert actual.as_marc() == encoded


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(tag=st.one_of(st.integers(0, 100000).map(str), st.sampled_from(["", "ab", "abc", "+01", " 1", "١٢٣", "²"])))
def test_mutated_tags_keep_pymarc_padding_and_errors(native, tag):
    # A caller can change Field.tag after the constructor normalizes it.
    fields = [("245", (" ", " "), [("a", "value")])]
    expected = make_record(pymarc, fields)
    actual = make_record(rmarc, fields)
    expected.fields[0].tag = actual.fields[0].tag = tag
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        try:
            encoded = expected.as_marc()
        except ValueError as error:
            with pytest.raises(ValueError) as caught:
                actual.as_marc()
            assert caught.value.args == error.args
        else:
            assert actual.as_marc() == encoded


RAW = st.lists(st.integers(0, 255).filter(lambda n: n not in (29, 30, 31)), max_size=60).map(bytes)


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(prefix=TEXT, suffix=RAW, handling=st.sampled_from(["strict", "ignore", "replace", "surrogateescape", "backslashreplace"]))
def test_invalid_utf8_decoding_matches_pymarc(native, prefix, suffix, handling):
    record = pymarc.Record(to_unicode=False, force_utf8=True)
    value = prefix.encode("utf-8") + b"\xff" + suffix
    record.add_field(pymarc.RawField("245", subfields=[pymarc.Subfield("a", value)]))
    encoded = record.as_marc()
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        try:
            expected = pymarc.Record(encoded, force_utf8=True, utf8_handling=handling)
        except UnicodeDecodeError as error:
            with pytest.raises(UnicodeDecodeError) as caught:
                rmarc.Record(encoded, force_utf8=True, utf8_handling=handling)
            assert caught.value.args == error.args
        else:
            actual = rmarc.Record(encoded, force_utf8=True, utf8_handling=handling)
            assert actual.as_dict() == expected.as_dict()


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(control=RAW, value=RAW)
def test_raw_bytes_survive_without_transcoding(native, control, value):
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        records = []
        for module in (pymarc, rmarc):
            record = module.Record(to_unicode=False)
            record.add_field(module.RawField("001", data=control))
            record.add_field(module.RawField("245", subfields=[module.Subfield("a", value)]))
            records.append(record)
        encoded = records[0].as_marc()
        assert records[1].as_marc() == encoded
        actual = rmarc.Record(encoded, to_unicode=False)
        expected = pymarc.Record(encoded, to_unicode=False)
        assert actual["001"].data == expected["001"].data == control
        assert actual["245"]["a"] == expected["245"]["a"] == value
        assert actual.as_marc() == expected.as_marc()


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@PROPERTY
@given(fields=RECORD, cut=st.integers(1, 12))
def test_reader_chunk_error_and_stream_position_match_pymarc(native, fields, cut):
    """A guard against invisible read-ahead changing public reader state."""
    good = make_record(pymarc, fields).as_marc()
    damaged = good[:-cut]
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        readers = [module.MARCReader(BytesIO(good + damaged)) for module in (pymarc, rmarc)]
        for _ in range(4):
            outcomes = []
            for reader in readers:
                try:
                    record = next(reader)
                    outcome = record.as_dict() if record is not None else None
                except StopIteration:
                    outcome = "stop"
                error = reader.current_exception
                outcomes.append((outcome, reader.current_chunk, type(error).__name__, reader.file_handle.tell()))
            assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
def test_writer_calls_custom_field_serializers_once_in_order(native):
    calls = []

    class CustomField(rmarc.Field):
        def as_marc(self, encoding):
            calls.append((self.tag, encoding))
            return b"  \x1faoverride\x1e"

    class CustomRawField(rmarc.RawField):
        def as_marc(self):
            calls.append((self.tag, None))
            return b"raw\x1e"

    record = rmarc.Record()
    record.add_field(CustomField("245"), CustomRawField("001", data=b"ignored"))
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        encoded = record.as_marc()
    assert calls == [("245", "utf-8"), ("001", None)]
    decoded = pymarc.Record(encoded)
    assert decoded.title == "override"
    assert decoded["001"].data == "raw"


@pytest.mark.parametrize("length", [0, 1, 9998, 9999, 10000, 99998, 99999, 100000])
def test_writer_decimal_widths_do_not_truncate(length):
    """Even oversized, invalid MARC must retain pymarc's serialization behavior."""
    fields = [("001", "x" * length), ("005", "tail")]
    assert make_record(rmarc, fields).as_marc() == make_record(pymarc, fields).as_marc()
