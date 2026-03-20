"""Tests for the CLI interface — exercises argparse and end-to-end workflows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sample_app.cli import build_parser, main


@pytest.fixture
def coll_path(tmp_path):
    """Return a path string for a temp collection."""
    return str(tmp_path / "test.mrc")


def run_cli(*args: str) -> None:
    """Helper to call main() with args."""
    main(list(args))


class TestAddAndList:
    def test_add_book(self, coll_path, capsys):
        run_cli(
            "-c",
            coll_path,
            "add",
            "The Great Gatsby",
            "Fitzgerald, F. Scott",
            "--isbn",
            "978-0743273565",
            "--publisher",
            "Scribner",
            "--year",
            "1925",
            "--subjects",
            "American fiction;Jazz Age",
            "--notes",
            "Classic",
            "--location",
            "Shelf A",
        )
        out = capsys.readouterr().out
        assert "Added book #0" in out

    def test_list_empty(self, coll_path, capsys):
        run_cli("-c", coll_path, "list")
        out = capsys.readouterr().out
        assert "empty" in out.lower()

    def test_list_with_books(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Book A", "Author A")
        run_cli("-c", coll_path, "add", "Book B", "Author B")
        run_cli("-c", coll_path, "list")
        out = capsys.readouterr().out
        assert "Book A" in out
        assert "Book B" in out
        assert "2 total" in out


class TestShowEditDelete:
    def test_show(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Show Me", "Author X", "--isbn", "111")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "Show Me" in out
        assert "Author X" in out
        assert "111" in out

    def test_show_bad_index(self, coll_path):
        run_cli("-c", coll_path, "add", "Book", "Author")
        with pytest.raises(SystemExit):
            run_cli("-c", coll_path, "show", "99")

    def test_edit_title(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Old Title", "Author")
        run_cli("-c", coll_path, "edit", "0", "--title", "New Title")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "New Title" in out

    def test_edit_author(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Book", "Old Author")
        run_cli("-c", coll_path, "edit", "0", "--author", "New Author")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "New Author" in out

    def test_edit_isbn(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Book", "Author", "--isbn", "OLD")
        run_cli("-c", coll_path, "edit", "0", "--isbn", "NEW-ISBN")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "NEW-ISBN" in out

    def test_edit_add_note(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Book", "Author")
        run_cli("-c", coll_path, "edit", "0", "--notes", "My annotation")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "My annotation" in out

    def test_edit_location(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Book", "Author")
        run_cli("-c", coll_path, "edit", "0", "--location", "Living Room")
        run_cli("-c", coll_path, "show", "0")
        out = capsys.readouterr().out
        assert "Living Room" in out

    def test_delete(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Gone Book", "Author")
        run_cli("-c", coll_path, "delete", "0")
        out = capsys.readouterr().out
        assert "Deleted" in out
        run_cli("-c", coll_path, "list")
        out2 = capsys.readouterr().out
        assert "empty" in out2.lower()


class TestSearch:
    def test_search_found(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Python Cookbook", "Beazley")
        run_cli("-c", coll_path, "add", "Rust Book", "Klabnik")
        run_cli("-c", coll_path, "search", "python")
        out = capsys.readouterr().out
        assert "Python Cookbook" in out
        assert "1 result" in out

    def test_search_not_found(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Some Book", "Author")
        run_cli("-c", coll_path, "search", "nonexistent")
        out = capsys.readouterr().out
        assert "No results" in out

    def test_search_with_field(self, coll_path, capsys):
        run_cli("-c", coll_path, "add", "Python", "Smith")
        run_cli("-c", coll_path, "search", "python", "--field", "245")
        out = capsys.readouterr().out
        assert "1 result" in out


class TestReport:
    def test_report_empty(self, coll_path, capsys):
        run_cli("-c", coll_path, "report")
        out = capsys.readouterr().out
        assert "Total books: 0" in out

    def test_report_with_data(self, coll_path, capsys):
        run_cli(
            "-c",
            coll_path,
            "add",
            "Book A",
            "Author X",
            "--publisher",
            "Pub1",
            "--year",
            "2020",
            "--subjects",
            "Science",
        )
        run_cli("-c", coll_path, "add", "Book B", "Author X", "--publisher", "Pub2", "--year", "2021")
        run_cli("-c", coll_path, "report")
        out = capsys.readouterr().out
        assert "Total books: 2" in out
        assert "Author X" in out
        assert "Science" in out


class TestExportImport:
    def test_export_json(self, coll_path, tmp_path, capsys):
        run_cli("-c", coll_path, "add", "JSON Test", "Author")
        json_out = str(tmp_path / "out.json")
        run_cli("-c", coll_path, "export", "json", json_out)
        out = capsys.readouterr().out
        assert "Exported 1" in out

        with open(json_out) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_export_xml(self, coll_path, tmp_path, capsys):
        run_cli("-c", coll_path, "add", "XML Test", "Author")
        xml_out = str(tmp_path / "out.xml")
        run_cli("-c", coll_path, "export", "xml", xml_out)
        out = capsys.readouterr().out
        assert "Exported 1" in out
        assert Path(xml_out).read_bytes().startswith(b"<?xml")

    def test_export_text(self, coll_path, tmp_path, capsys):
        run_cli("-c", coll_path, "add", "Text Test", "Author")
        txt_out = str(tmp_path / "out.txt")
        run_cli("-c", coll_path, "export", "text", txt_out)
        out = capsys.readouterr().out
        assert "Exported 1" in out

    def test_import_marc(self, coll_path, tmp_path, capsys):
        # Create source
        src_path = str(tmp_path / "src.mrc")
        run_cli("-c", src_path, "add", "Import Me", "Author Import")
        # Import into new collection
        run_cli("-c", coll_path, "import", "marc", src_path)
        out = capsys.readouterr().out
        assert "Imported 1" in out
        # Verify
        run_cli("-c", coll_path, "list")
        out2 = capsys.readouterr().out
        assert "Import Me" in out2

    def test_import_xml(self, coll_path, tmp_path, capsys):
        # Create source, export as XML
        src_path = str(tmp_path / "src.mrc")
        run_cli("-c", src_path, "add", "XML Import Book", "Author")
        xml_path = str(tmp_path / "src.xml")
        run_cli("-c", src_path, "export", "xml", xml_path)
        capsys.readouterr()  # clear

        run_cli("-c", coll_path, "import", "xml", xml_path)
        out = capsys.readouterr().out
        assert "Imported 1" in out

    def test_import_missing_file(self, coll_path):
        with pytest.raises(SystemExit):
            run_cli("-c", coll_path, "import", "marc", "/nonexistent/file.mrc")


class TestParser:
    """Verify argparse is wired up correctly."""

    def test_no_command(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_add_args(self):
        parser = build_parser()
        args = parser.parse_args(["add", "Title", "Author", "--isbn", "123"])
        assert args.command == "add"
        assert args.title == "Title"
        assert args.author == "Author"
        assert args.isbn == "123"

    def test_search_args(self):
        parser = build_parser()
        args = parser.parse_args(["search", "query", "--field", "245"])
        assert args.command == "search"
        assert args.query == "query"
        assert args.field == "245"

    def test_export_choices(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["export", "invalid_format", "out.txt"])

    def test_collection_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-c", "my.mrc", "list"])
        assert args.collection == "my.mrc"

    def test_loc_search_args(self):
        parser = build_parser()
        args = parser.parse_args(["loc-search", "python", "--max", "10"])
        assert args.command == "loc-search"
        assert args.query == "python"
        assert args.max == 10

    def test_loc_fetch_args(self):
        parser = build_parser()
        args = parser.parse_args(["loc-fetch", "2020123456", "--show", "--no-add"])
        assert args.command == "loc-fetch"
        assert args.lccn == "2020123456"
        assert args.show is True
        assert args.no_add is True


class TestEndToEnd:
    """Full workflow: add several books, search, edit, delete, export, reimport."""

    def test_full_workflow(self, coll_path, tmp_path, capsys):
        # Add books
        run_cli(
            "-c",
            coll_path,
            "add",
            "Moby Dick",
            "Melville, Herman",
            "--isbn",
            "978-0142437247",
            "--year",
            "1851",
            "--subjects",
            "Whales;Sea adventures",
        )
        run_cli(
            "-c",
            coll_path,
            "add",
            "1984",
            "Orwell, George",
            "--isbn",
            "978-0451524935",
            "--year",
            "1949",
            "--subjects",
            "Dystopia;Politics",
        )
        run_cli(
            "-c",
            coll_path,
            "add",
            "Dune",
            "Herbert, Frank",
            "--isbn",
            "978-0441172719",
            "--year",
            "1965",
            "--subjects",
            "Science fiction",
        )
        capsys.readouterr()  # clear

        # List
        run_cli("-c", coll_path, "list")
        listing = capsys.readouterr().out
        assert "3 total" in listing
        assert "Moby Dick" in listing

        # Search
        run_cli("-c", coll_path, "search", "orwell")
        search_out = capsys.readouterr().out
        assert "1984" in search_out

        # Edit
        run_cli("-c", coll_path, "edit", "2", "--notes", "My favorite sci-fi")
        capsys.readouterr()

        # Show detail
        run_cli("-c", coll_path, "show", "2")
        detail = capsys.readouterr().out
        assert "Dune" in detail
        assert "My favorite sci-fi" in detail

        # Report
        run_cli("-c", coll_path, "report")
        report = capsys.readouterr().out
        assert "Total books: 3" in report
        assert "Dystopia" in report or "Science fiction" in report

        # Export JSON
        json_out = str(tmp_path / "books.json")
        run_cli("-c", coll_path, "export", "json", json_out)
        capsys.readouterr()
        with open(json_out) as f:
            data = json.load(f)
        assert len(data) == 3

        # Export XML
        xml_out = str(tmp_path / "books.xml")
        run_cli("-c", coll_path, "export", "xml", xml_out)
        capsys.readouterr()

        # Delete middle book
        run_cli("-c", coll_path, "delete", "1")
        capsys.readouterr()
        run_cli("-c", coll_path, "list")
        listing2 = capsys.readouterr().out
        assert "2 total" in listing2
        assert "1984" not in listing2

        # Import from the XML (which had 3 books)
        new_coll = str(tmp_path / "imported.mrc")
        run_cli("-c", new_coll, "import", "xml", xml_out)
        import_out = capsys.readouterr().out
        assert "Imported 3" in import_out
