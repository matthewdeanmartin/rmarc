"""Execute the same examples that the build type-checks."""

from io import BytesIO

from examples.book_catalog import Book, export_catalog, import_catalog, replace_subjects, to_record


def test_book_catalog_export_import_and_stream_ownership():
    books = [Book("1", "Café 二", "Some Author", ("History", "Libraries")), Book("2", "No author")]
    stream = BytesIO()
    export_catalog(iter(books), stream)
    assert not stream.closed
    stream.seek(0)
    result = import_catalog(stream)
    assert result.books == books
    assert result.errors == []
    assert not stream.closed


def test_catalog_reports_bad_record_and_continues():
    first = Book("1", "First")
    last = Book("3", "Last")
    bad = to_record(Book("2", "Damaged")).as_marc()
    bad = bad[:12] + b"00000" + bad[17:]
    source = BytesIO(to_record(first).as_marc() + bad + to_record(last).as_marc())
    result = import_catalog(source)
    assert result.books == [first, last]
    assert len(result.errors) == 1
    assert result.errors[0]


def test_subject_replacement_retains_other_fields():
    record = to_record(Book("1", "Title", subjects=("Old",)))
    title = record["245"]
    fields = record.fields
    replace_subjects(record, ["New", "Other"])
    assert record["245"] is title
    assert record.fields is fields
    assert [item["a"] for item in record.get_fields("650")] == ["New", "Other"]
