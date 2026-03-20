"""Tests for the Goodreads CSV import module."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from sample_app.goodreads import (
    import_goodreads,
    parse_goodreads_csv,
    row_to_record,
)
from sample_app.store import Collection


SAMPLE_CSV_HEADER = (
    "Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,"
    "My Rating,Average Rating,Publisher,Binding,Number of Pages,"
    "Year Published,Original Publication Year,Date Read,Date Added,"
    "Bookshelves,Bookshelves with positions,Exclusive Shelf,"
    "My Review,Spoiler,Private Notes,Read Count,Owned Copies"
)


def _write_csv(tmp_path: Path, rows: list[str]) -> Path:
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(SAMPLE_CSV_HEADER + "\n" + "\n".join(rows), encoding="utf-8")
    return csv_path


@pytest.fixture
def sample_csv(tmp_path):
    rows = [
        '10001,"The Martian",Andy Weir,"Weir, Andy",,'
        '="0553418025","="9780553418026"",5,4.40,Broadway Books,'
        "Paperback,369,2014,2011,2025/06/15,2025/05/01,sci-fi,,read,,,,1,1",
        '10002,"Dune",Frank Herbert,"Herbert, Frank",,'
        '="0441172717","="9780441172719"",5,4.25,Ace Books,'
        "Mass Market Paperback,688,2005,1965,2025/04/20,2025/03/10,,,read,,,,2,1",
    ]
    return _write_csv(tmp_path, rows)


class TestParseGoodreadsCsv:
    def test_parse_rows(self, sample_csv):
        rows = parse_goodreads_csv(sample_csv)
        assert len(rows) == 2
        assert rows[0]["Title"] == "The Martian"
        assert rows[1]["Title"] == "Dune"

    def test_empty_file(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(SAMPLE_CSV_HEADER + "\n", encoding="utf-8")
        rows = parse_goodreads_csv(csv_path)
        assert rows == []


class TestRowToRecord:
    def test_basic_conversion(self):
        row = {
            "Title": "The Martian",
            "Author": "Andy Weir",
            "Author l-f": "Weir, Andy",
            "ISBN": '="0553418025"',
            "ISBN13": '="9780553418026"',
            "Publisher": "Broadway Books",
            "Year Published": "2014",
            "Original Publication Year": "2011",
            "Exclusive Shelf": "read",
            "My Rating": "5",
            "My Review": "",
            "Bookshelves": "sci-fi",
        }
        rec = row_to_record(row)
        assert "Martian" in rec.title
        assert "Weir" in rec.author
        assert rec.isbn is not None

    def test_rating_in_notes(self):
        row = {
            "Title": "Good Book",
            "Author": "Author A",
            "Author l-f": "",
            "ISBN": "",
            "ISBN13": "",
            "Publisher": "",
            "Year Published": "",
            "Original Publication Year": "",
            "Exclusive Shelf": "read",
            "My Rating": "4",
            "My Review": "",
            "Bookshelves": "",
        }
        rec = row_to_record(row)
        notes = rec.notes
        assert any("Rating: 4/5" in n.format_field() for n in notes)

    def test_currently_reading_shelf_in_notes(self):
        row = {
            "Title": "In Progress",
            "Author": "Author B",
            "Author l-f": "",
            "ISBN": "",
            "ISBN13": "",
            "Publisher": "",
            "Year Published": "",
            "Original Publication Year": "",
            "Exclusive Shelf": "currently-reading",
            "My Rating": "0",
            "My Review": "",
            "Bookshelves": "",
        }
        rec = row_to_record(row)
        notes = rec.notes
        assert any("currently-reading" in n.format_field() for n in notes)


class TestImportGoodreads:
    def test_import_without_enrich(self, sample_csv, tmp_path):
        coll = Collection(tmp_path / "test.mrc")
        count = import_goodreads(sample_csv, coll, enrich=False)
        assert count == 2
        assert len(coll) == 2
        titles = [coll.get(i).title for i in range(2)]
        assert any("Martian" in t for t in titles)
        assert any("Dune" in t for t in titles)

    def test_import_with_progress(self, sample_csv, tmp_path):
        coll = Collection(tmp_path / "test.mrc")
        progress_calls = []

        def on_progress(current, total, title):
            progress_calls.append((current, total, title))

        import_goodreads(sample_csv, coll, enrich=False, on_progress=on_progress)
        assert len(progress_calls) == 2
        assert progress_calls[-1][0] == 2
        assert progress_calls[-1][1] == 2

    def test_import_cli_command(self, sample_csv, tmp_path, capsys):
        from sample_app.cli import main

        coll_path = str(tmp_path / "cli_test.mrc")
        main(["-c", coll_path, "import-goodreads", str(sample_csv)])
        out = capsys.readouterr().out
        assert "Imported 2 book(s)" in out

    def test_import_with_sample_data(self, tmp_path):
        """Import from the bundled sample.csv."""
        sample = Path(__file__).resolve().parent.parent / "sample_app" / "data" / "sample.csv"
        if not sample.exists():
            pytest.skip("sample.csv not found")
        coll = Collection(tmp_path / "test.mrc")
        count = import_goodreads(sample, coll, enrich=False)
        assert count == 5
