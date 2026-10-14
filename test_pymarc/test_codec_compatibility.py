"""Encoding and mutable-object regressions against pymarc 5.4 semantics."""

import codecs
from pathlib import Path

import pytest
import rmarc
import rmarc.record as record_module


@pytest.fixture(params=[True, False], ids=["rust", "python"])
def codec(request, monkeypatch):
    if request.param and not record_module._HAS_RUST_CODEC:
        pytest.skip("Rust extension unavailable")
    monkeypatch.setattr(record_module, "_HAS_RUST_CODEC", request.param)


def utf8_record(value="valid\ufffdX"):
    record = rmarc.Record(force_utf8=True)
    record.add_field(rmarc.Field("245", subfields=[rmarc.Subfield("a", value)]))
    return record.as_marc()


@pytest.mark.parametrize(
    "handling", ["strict", "ignore", "replace", "backslashreplace", "surrogateescape", "custom_rmarc_test"]
)
def test_utf8_handlers_match_python(codec, handling):
    codecs.register_error("custom_rmarc_test", lambda error: ("CUSTOM", error.end))
    value = b"valid\xef\xbf\xbd\xff"
    raw = utf8_record().replace(b"X", b"\xff")
    if handling == "strict":
        with pytest.raises(UnicodeDecodeError) as expected:
            value.decode("utf-8")
        with pytest.raises(UnicodeDecodeError) as actual:
            rmarc.Record(raw, utf8_handling=handling)
        assert actual.value.args == expected.value.args
    else:
        record = rmarc.Record(raw, utf8_handling=handling)
        assert record.title == value.decode("utf-8", handling)


def test_unknown_error_handler_is_looked_up_only_for_invalid_data(codec):
    assert rmarc.Record(utf8_record("valid"), utf8_handling="not_registered").title == "valid"
    with pytest.raises(LookupError):
        rmarc.Record(utf8_record().replace(b"X", b"\xff"), utf8_handling="not_registered")


@pytest.mark.parametrize("encoding", ["utf-8", "UTF-8", "utf8", "cp1251"])
def test_explicit_file_encoding_without_leader_flag(codec, encoding):
    record = rmarc.Record(to_unicode=False)
    record.add_field(
        rmarc.RawField("245", subfields=[rmarc.Subfield("a", "caf\u00e9".encode(encoding, errors="replace"))])
    )
    raw = record.as_marc()
    actual = rmarc.Record(raw, file_encoding=encoding)
    assert isinstance(actual.title, str)
    assert actual.title == "caf\u00e9".encode(encoding, errors="replace").decode(encoding)


def test_explicit_utf8_without_flag_uses_strict_errors(codec):
    raw = utf8_record().replace(b"X", b"\xff")
    raw = raw[:9] + b" " + raw[10:]
    # pymarc applies utf8_handling only when the leader or force flag requests UTF-8.
    with pytest.raises(UnicodeDecodeError):
        rmarc.Record(raw, file_encoding="utf-8", utf8_handling="ignore")


def test_legacy_control_field_uses_latin1_not_marc8(codec):
    record = rmarc.Record(to_unicode=False)
    record.add_field(rmarc.RawField("001", data=b"\xe9"))
    assert rmarc.Record(record.as_marc())["001"].data == "\u00e9"


def test_control_field_utf8_errors_are_strict(codec):
    record = rmarc.Record(to_unicode=False, force_utf8=True)
    record.add_field(rmarc.RawField("001", data=b"\xff"))
    with pytest.raises(UnicodeDecodeError):
        rmarc.Record(record.as_marc(), utf8_handling="replace")


def test_failed_decode_preserves_prior_fields_and_error_details(codec):
    record = rmarc.Record(force_utf8=True)
    record.add_field(rmarc.Field("001", data="id"), rmarc.Field("245", subfields=[rmarc.Subfield("a", "X")]))
    raw = record.as_marc().replace(b"X", b"\xff")
    target = rmarc.Record()
    fields = target.fields
    with pytest.raises(UnicodeDecodeError) as error:
        target.decode_marc(raw)
    assert error.value.object == b"\xff"
    assert target.fields is fields
    assert [field.tag for field in fields] == ["001"]


def test_native_objects_keep_python_mutation_semantics(codec):
    record = rmarc.Record(utf8_record("title"))
    assert type(record["245"]) is rmarc.Field
    assert type(record["245"].subfields[0]) is rmarc.Subfield
    assert type(record["245"].indicators) is rmarc.Indicators
    fields = record.get_fields()
    assert fields is record.fields
    field = fields[0]
    field.subfields.append(rmarc.Subfield("b", "subtitle"))
    assert record.title == "title subtitle"
    field["a"] = "changed"
    assert rmarc.Record(record.as_marc()).title == "changed subtitle"
    fields.clear()
    assert record.title is None


def test_raw_objects_remain_raw(codec):
    record = rmarc.Record(utf8_record("caf\u00e9"), to_unicode=False)
    assert type(record["245"]) is rmarc.RawField
    assert record["245"]["a"] == b"caf\xc3\xa9"


def test_subclass_add_field_hook_is_preserved(codec):
    class TrackingRecord(rmarc.Record):
        def add_field(self, *fields):
            for field in fields:
                field.subfields.append(rmarc.Subfield("b", "hook"))
            super().add_field(*fields)

    assert TrackingRecord(utf8_record("title")).title == "title hook"


def test_custom_error_handler_called_once_per_invalid_sequence(codec):
    calls = []

    def handler(error):
        calls.append(error.start)
        return "fixed", error.end

    codecs.register_error("rmarc_count_calls", handler)
    record = rmarc.Record(utf8_record().replace(b"X", b"\xff"), utf8_handling="rmarc_count_calls")
    assert record.title == "valid\ufffdfixed"
    assert calls == [8]


def test_marc8_shortcut_keeps_controls_and_escape_semantics():
    pymarc = pytest.importorskip("pymarc")
    for data in [bytes(range(32, 127)), b"before\x00after", b"before\x1b(Bafter", b"\xe2e"]:
        assert rmarc.marc8_to_unicode(data) == pymarc.marc8_to_unicode(data)


def test_trailing_marc8_escape_error_matches_python(codec):
    pymarc = pytest.importorskip("pymarc")
    with pytest.raises(UnicodeDecodeError) as expected:
        pymarc.marc8_to_unicode(b"\x1b")
    with pytest.raises(UnicodeDecodeError) as actual:
        rmarc.marc8_to_unicode(b"\x1b")
    assert actual.value.args == expected.value.args
    record = rmarc.Record(to_unicode=False)
    record.add_field(rmarc.RawField("245", subfields=[rmarc.Subfield("a", b"\x1b")]))
    with pytest.raises(UnicodeDecodeError) as actual:
        rmarc.Record(record.as_marc())
    assert actual.value.args == expected.value.args


def test_base_address_at_end_of_record(codec):
    raw = b"00037nam  2200037   4500" + b"001000100000" + b"\x1e"
    with pytest.raises(rmarc.BaseAddressInvalid):
        rmarc.Record(raw)


@pytest.mark.parametrize(
    "tag,expected",
    [
        (None, "None"),
        (" 1", " 1"),
        ("+01", "+01"),
        ("1", "001"),
        (1, "001"),
        ("\u0661\u0662\u0663", "\u0661\u0662\u0663"),
    ],
)
def test_pymarc_54_tag_normalization(tag, expected):
    assert rmarc.Field(tag).tag == expected


def test_lookup_order_aliases_and_failed_assignment():
    record = rmarc.Record()
    for tag in ["650", "245", "650"]:
        record.add_field(rmarc.Field(tag, subfields=[rmarc.Subfield("a", tag)]))
    assert [f.tag for f in record.get_fields("650", "245", "650")] == ["650", "245", "650"]
    first = record["650"]
    first.tag = "500"
    assert record["500"] is first
    assert record["650"] is record.fields[2]
    first.subfields.append(rmarc.Subfield("a", "duplicate"))
    original = first.subfields[:]
    with pytest.raises(KeyError):
        first["a"] = "must not partially modify"
    assert first.subfields == original
    fields = record.fields
    record.remove_fields("650", "245")
    assert record.fields is fields
    assert fields == [first]


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"to_unicode": False},
        {"utf8_handling": "ignore"},
        {"utf8_handling": "replace"},
        {"force_utf8": True},
        {"file_encoding": "cp1251"},
    ],
)
def test_fixture_reader_results_match_pymarc(codec, options):
    pymarc = pytest.importorskip("pymarc")

    def read(module, raw):
        reader = module.MARCReader(raw, **options)
        result = []
        for record in reader:
            if record is None:
                error = reader.current_exception
                result.append((type(error).__name__, error.args))
            else:
                result.append(record.as_dict())
        return result

    root = Path(__file__).parent
    for path in sorted([*root.glob("*.dat"), *root.glob("*.mrc")]):
        assert read(rmarc, path.read_bytes()) == read(pymarc, path.read_bytes()), path.name
