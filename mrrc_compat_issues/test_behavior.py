"""Behavioral differences: each assertion passes on pymarc 5.4.0.

These intentionally fail on affected mrrc versions. No rmarc or data files needed.
"""

import pytest


def test_title_includes_subtitle(marc):
    record = marc.Record()
    record.add_field(
        marc.Field(
            "245",
            indicators=["0", "0"],
            subfields=[marc.Subfield("a", "Main title :"), marc.Subfield("b", "subtitle.")],
        )
    )

    assert record.title == "Main title : subtitle."


def test_get_fields_preserves_record_order(marc):
    record = marc.Record()
    for tag in ["650", "245", "650"]:
        record.add_field(marc.Field(tag, indicators=[" ", " "], subfields=[marc.Subfield("a", "text")]))

    assert [field.tag for field in record.get_fields("650", "245")] == ["650", "245", "650"]


def test_repeated_selector_does_not_duplicate_fields(marc):
    record = marc.Record()
    record.add_field(marc.Field("650", indicators=[" ", " "], subfields=[marc.Subfield("a", "subject")]))

    assert len(record.get_fields("650", "650")) == 1


def test_missing_subfield_raises_key_error(marc):
    field = marc.Field("245", indicators=[" ", " "], subfields=[marc.Subfield("a", "title")])

    with pytest.raises(KeyError):
        field["z"]


def test_binary_roundtrip_preserves_field_order(marc):
    # pymarc supplies valid input and independently inspects each library's output.
    import pymarc

    source = pymarc.Record(force_utf8=True)
    for tag in ["650", "245", "650"]:
        source.add_field(pymarc.Field(tag, indicators=[" ", " "], subfields=[pymarc.Subfield("a", "text")]))
    record = next(marc.MARCReader(source.as_marc()))
    reread = pymarc.Record(record.as_marc())

    assert [field.tag for field in reread.fields] == ["650", "245", "650"]


def test_decoded_legacy_record_serializes_like_pymarc(marc):
    import pymarc

    source = pymarc.Record(to_unicode=False)
    source.add_field(pymarc.Field("245", indicators=[" ", " "], subfields=[pymarc.Subfield("a", "ASCII title")]))
    raw = source.as_marc()
    assert raw[9:10] == b" "  # Source uses the legacy encoding flag.
    expected = pymarc.Record(raw).as_marc()

    assert next(marc.MARCReader(raw)).as_marc() == expected


def test_direct_subfield_assignment_updates_record(marc):
    """Passing control: direct assignment already works in both libraries."""
    record = marc.Record()
    record.add_field(marc.Field("245", indicators=[" ", " "], subfields=[marc.Subfield("a", "old")]))
    record["245"]["a"] = "new"

    assert record.title == "new"
