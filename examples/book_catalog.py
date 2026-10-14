"""Typed MARC workflows for a book tracker, without starting its GUI.

The caller owns input/output streams. Import reports malformed records and
continues when MARCReader can recover; export leaves the destination open.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import BinaryIO

from rmarc import Field, Indicators, MARCReader, MARCWriter, Record, Subfield


@dataclass(frozen=True)
class Book:
    identifier: str
    title: str
    author: str = ""
    subjects: tuple[str, ...] = ()


@dataclass
class ImportResult:
    books: list[Book] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def to_record(book: Book) -> Record:
    fields = [
        Field("001", data=book.identifier),
        Field("245", indicators=Indicators("1" if book.author else "0", "0"), subfields=[Subfield("a", book.title)]),
    ]
    if book.author:
        fields.append(Field("100", indicators=Indicators("1", " "), subfields=[Subfield("a", book.author)]))
    result = Record(fields=fields)
    replace_subjects(result, book.subjects)
    return result


def replace_subjects(record: Record, subjects: Iterable[str]) -> None:
    """Update a record while retaining unrelated fields and their references."""
    record.fields[:] = [item for item in record.fields if item.tag != "650"]
    for subject in subjects:
        record.add_ordered_field(Field("650", indicators=Indicators(" ", "0"), subfields=[Subfield("a", subject)]))


def import_catalog(source: BinaryIO) -> ImportResult:
    result = ImportResult()
    # The supplied file can already be buffered; leave batching at its default.
    reader = MARCReader(source)
    for record in reader:
        if record is None:
            result.errors.append(str(reader.current_exception))
            continue
        identifier = record.get("001")
        author = record.get("100")
        subjects = tuple(value for item in record.get_fields("650") for value in item.get_subfields("a"))
        result.books.append(
            Book(
                identifier=identifier.data or "" if identifier is not None else "",
                title=record.title or "Untitled",
                author=author.get("a", "") if author is not None else "",
                subjects=subjects,
            )
        )
    return result


def export_catalog(books: Iterable[Book], destination: BinaryIO) -> None:
    writer = MARCWriter(destination)
    try:
        for book in books:
            writer.write(to_record(book))
    finally:
        writer.close(close_fh=False)
