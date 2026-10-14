"""Public API differences, possibly intentional; separate from behavioral bugs."""

from io import BytesIO


def test_fields_is_a_mutable_list(marc):
    record = marc.Record()
    record.fields.append(marc.Field("500", indicators=[" ", " "], subfields=[marc.Subfield("a", "note")]))

    assert len(record.get_fields("500")) == 1


def test_subfields_is_a_mutable_list(marc):
    record = marc.Record()
    record.add_field(marc.Field("245", indicators=[" ", " "], subfields=[marc.Subfield("a", "title")]))
    record["245"].subfields.append(marc.Subfield("b", "subtitle"))

    assert record.title == "title subtitle"


def test_get_fields_returns_the_records_actual_list(marc):
    record = marc.Record()

    assert record.get_fields() is record.fields


def test_one_iteration_consumes_one_record_from_callers_stream(marc):
    """Batching can intentionally change this observable pymarc behavior."""
    record = marc.Record()
    record.add_field(marc.Field("001", data="one"))
    encoded = record.as_marc()
    source = BytesIO(encoded * 3)
    reader = marc.MARCReader(source)

    assert next(reader) is not None

    # A caller may inspect the position, stop here, or reuse its own stream.
    assert source.tell() == len(encoded)
