"""Storage layer for the book collection.

Uses MARC21 binary as the canonical format, with JSON and XML export support.
Each collection is a single .mrc file on disk.
"""

from __future__ import annotations

import os
from io import BytesIO, StringIO
from pathlib import Path

from rmarc import (
    Field,
    Indicators,
    JSONWriter,
    MARCReader,
    MARCWriter,
    Record,
    Subfield,
    TextWriter,
    XMLWriter,
    parse_xml_to_array,
)


def make_record(
    title: str,
    author: str,
    isbn: str = "",
    publisher: str = "",
    year: str = "",
    subjects: list[str] | None = None,
    notes: str = "",
    location: str = "",
) -> Record:
    """Build a MARC record from simple bibliographic fields."""
    record = Record()

    # Leader: type of record = 'a' (language material), bib level = 'm' (monograph)
    leader = list(record.leader)
    leader[5] = "n"  # new
    leader[6] = "a"  # language material
    leader[7] = "m"  # monograph
    leader[9] = "a"  # UTF-8
    record.leader[5] = "n"
    record.leader[6] = "a"
    record.leader[7] = "m"
    record.leader[9] = "a"

    # 008 - Fixed-length data elements (minimal)
    fixed = "      s" + (year.ljust(4) if year else "    ") + "    xx            000 0 eng d"
    # Pad/trim to 40 chars
    fixed = fixed[:40].ljust(40)
    record.add_ordered_field(Field(tag="008", data=fixed))

    # 020 - ISBN
    if isbn:
        record.add_ordered_field(
            Field(tag="020", indicators=Indicators(" ", " "), subfields=[Subfield("a", isbn)])
        )

    # 100 - Main entry / author
    if author:
        record.add_ordered_field(
            Field(tag="100", indicators=Indicators("1", " "), subfields=[Subfield("a", author)])
        )

    # 245 - Title statement
    ind1 = "1" if author else "0"
    title_subfields = [Subfield("a", title)]
    if author:
        title_subfields.append(Subfield("c", author))
    record.add_ordered_field(
        Field(tag="245", indicators=Indicators(ind1, "0"), subfields=title_subfields)
    )

    # 260 - Publication info
    if publisher or year:
        pub_subfields = []
        if publisher:
            pub_subfields.append(Subfield("b", publisher))
        if year:
            pub_subfields.append(Subfield("c", year))
        record.add_ordered_field(
            Field(tag="260", indicators=Indicators(" ", " "), subfields=pub_subfields)
        )

    # 500 - General note
    if notes:
        record.add_ordered_field(
            Field(tag="500", indicators=Indicators(" ", " "), subfields=[Subfield("a", notes)])
        )

    # 650 - Subject headings
    for subj in subjects or []:
        record.add_ordered_field(
            Field(tag="650", indicators=Indicators(" ", "0"), subfields=[Subfield("a", subj)])
        )

    # 852 - Location
    if location:
        record.add_ordered_field(
            Field(tag="852", indicators=Indicators(" ", " "), subfields=[Subfield("a", location)])
        )

    return record


class Collection:
    """A personal book collection backed by a .mrc file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: list[Record] = []
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        with open(self.path, "rb") as fh:
            reader = MARCReader(fh)
            for record in reader:
                if record is not None:
                    self._records.append(record)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "wb") as fh:
            writer = MARCWriter(fh)
            for record in self._records:
                writer.write(record)
            writer.close(close_fh=False)

    @property
    def records(self) -> list[Record]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)

    # --- CRUD ---

    def add(self, record: Record) -> int:
        """Add a record, return its index."""
        self._records.append(record)
        self.save()
        return len(self._records) - 1

    def get(self, index: int) -> Record:
        return self._records[index]

    def update(self, index: int, record: Record) -> None:
        self._records[index] = record
        self.save()

    def delete(self, index: int) -> Record:
        removed = self._records.pop(index)
        self.save()
        return removed

    # --- Search ---

    def search(self, query: str, field_tag: str | None = None) -> list[tuple[int, Record]]:
        """Case-insensitive search across all fields, or a specific tag."""
        query_lower = query.lower()
        results = []
        for i, rec in enumerate(self._records):
            if field_tag:
                fields = rec.get_fields(field_tag)
            else:
                fields = rec.get_fields()
            for f in fields:
                text = f.value().lower() if not f.control_field else (f.data or "").lower()
                if query_lower in text:
                    results.append((i, rec))
                    break
        return results

    # --- Export ---

    def export_json(self, path: str | Path) -> None:
        out = open(path, "w", encoding="utf-8")
        writer = JSONWriter(out)
        for rec in self._records:
            writer.write(rec)
        writer.close()

    def export_xml(self, path: str | Path) -> None:
        out = open(path, "wb")
        writer = XMLWriter(out)
        for rec in self._records:
            writer.write(rec)
        writer.close()

    def export_text(self, path: str | Path) -> None:
        out = open(path, "w", encoding="utf-8")
        writer = TextWriter(out)
        for rec in self._records:
            writer.write(rec)
        writer.close()

    def import_xml(self, path: str | Path) -> int:
        """Import records from a MARCXML file. Returns count of records imported."""
        records = parse_xml_to_array(str(path))
        for rec in records:
            self._records.append(rec)
        self.save()
        return len(records)

    def import_marc(self, path: str | Path) -> int:
        """Import records from a MARC21 file. Returns count of records imported."""
        count = 0
        with open(path, "rb") as fh:
            reader = MARCReader(fh)
            for record in reader:
                if record is not None:
                    self._records.append(record)
                    count += 1
        self.save()
        return count

    # --- Reports ---

    def report_summary(self) -> str:
        """Return a summary report of the collection."""
        lines = [f"Collection: {self.path.name}", f"Total books: {len(self._records)}", ""]

        # Authors
        authors: dict[str, int] = {}
        subjects: dict[str, int] = {}
        publishers: dict[str, int] = {}
        years: dict[str, int] = {}

        for rec in self._records:
            author = rec.author
            if author:
                authors[author] = authors.get(author, 0) + 1

            for field in rec.subjects:
                subj = field.get("a", "Unknown")
                subjects[subj] = subjects.get(subj, 0) + 1

            pub = rec.publisher
            if pub:
                publishers[pub] = publishers.get(pub, 0) + 1

            yr = rec.pubyear
            if yr:
                years[yr] = years.get(yr, 0) + 1

        if authors:
            lines.append("Authors:")
            for name, count in sorted(authors.items(), key=lambda x: -x[1]):
                lines.append(f"  {name}: {count} book(s)")
            lines.append("")

        if subjects:
            lines.append("Subjects:")
            for name, count in sorted(subjects.items(), key=lambda x: -x[1]):
                lines.append(f"  {name}: {count} book(s)")
            lines.append("")

        if publishers:
            lines.append("Publishers:")
            for name, count in sorted(publishers.items(), key=lambda x: -x[1]):
                lines.append(f"  {name}: {count} book(s)")
            lines.append("")

        if years:
            lines.append("Publication Years:")
            for yr_val, count in sorted(years.items()):
                lines.append(f"  {yr_val}: {count} book(s)")
            lines.append("")

        return "\n".join(lines)

    def report_detail(self, index: int) -> str:
        """Return a detailed view of a single record."""
        rec = self._records[index]
        lines = [f"Record #{index}"]
        lines.append(f"  Title:     {rec.title or 'N/A'}")
        lines.append(f"  Author:    {rec.author or 'N/A'}")
        lines.append(f"  ISBN:      {rec.isbn or 'N/A'}")
        lines.append(f"  Publisher: {rec.publisher or 'N/A'}")
        lines.append(f"  Year:      {rec.pubyear or 'N/A'}")

        subjects = rec.subjects
        if subjects:
            subj_strs = [f.format_field() for f in subjects]
            lines.append(f"  Subjects:  {'; '.join(subj_strs)}")

        notes = rec.notes
        if notes:
            for note in notes:
                lines.append(f"  Note:      {note.format_field()}")

        location = rec.location
        if location:
            lines.append(f"  Location:  {location[0].format_field()}")

        lines.append("")
        lines.append("  Raw MARC fields:")
        for field in rec.get_fields():
            lines.append(f"    {field}")

        return "\n".join(lines)

    def report_list(self) -> str:
        """Return a short listing of all books."""
        if not self._records:
            return "Collection is empty."
        lines = []
        for i, rec in enumerate(self._records):
            title = rec.title or "Untitled"
            author = rec.author or "Unknown"
            isbn = rec.isbn or ""
            isbn_part = f" [{isbn}]" if isbn else ""
            lines.append(f"  {i:>4}  {title} / {author}{isbn_part}")
        return "\n".join(lines)
