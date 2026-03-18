"""Tests for the store module — Collection and make_record."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rmarc import Field, Indicators, Record, Subfield

from sample_app.store import Collection, make_record


@pytest.fixture
def tmp_collection(tmp_path):
    """Return a Collection backed by a temp .mrc file."""
    return Collection(tmp_path / "test.mrc")


@pytest.fixture
def sample_record():
    return make_record(
        title="The Great Gatsby",
        author="Fitzgerald, F. Scott",
        isbn="978-0743273565",
        publisher="Scribner",
        year="1925",
        subjects=["American fiction", "Jazz Age"],
        notes="A classic novel.",
        location="Shelf A-3",
    )


# --- make_record ---


class TestMakeRecord:
    def test_basic_fields(self, sample_record):
        assert sample_record.title is not None
        assert "Great Gatsby" in sample_record.title
        assert "Fitzgerald" in sample_record.author
        assert "0743273565" in sample_record.isbn  # rmarc may normalize hyphens

    def test_publisher_and_year(self, sample_record):
        assert sample_record.publisher is not None
        assert "Scribner" in sample_record.publisher
        assert sample_record.pubyear is not None
        assert "1925" in sample_record.pubyear

    def test_subjects(self, sample_record):
        subjects = sample_record.subjects
        assert len(subjects) == 2
        subj_texts = [f.get("a", "") for f in subjects]
        assert "American fiction" in subj_texts
        assert "Jazz Age" in subj_texts

    def test_notes(self, sample_record):
        notes = sample_record.notes
        assert len(notes) == 1
        assert "classic" in notes[0].format_field()

    def test_location(self, sample_record):
        loc = sample_record.location
        assert len(loc) == 1
        assert "Shelf A-3" in loc[0].format_field()

    def test_leader_flags(self, sample_record):
        leader = str(sample_record.leader)
        assert leader[6] == "a"  # language material
        assert leader[7] == "m"  # monograph
        assert leader[9] == "a"  # UTF-8

    def test_control_field_008(self, sample_record):
        f008 = sample_record.get("008")
        assert f008 is not None
        assert f008.control_field
        assert "1925" in f008.data

    def test_no_author(self):
        rec = make_record(title="Anonymous Work", author="")
        f245 = rec.get("245")
        assert f245 is not None
        assert f245.indicator1 == "0"  # no author entry
        assert rec.get("100") is None

    def test_minimal_record(self):
        rec = make_record(title="Bare Minimum", author="Nobody")
        assert rec.title is not None
        assert "Bare Minimum" in rec.title

    def test_roundtrip_marc21(self, sample_record):
        """Record should survive encode -> decode."""
        marc_bytes = sample_record.as_marc()
        assert isinstance(marc_bytes, bytes)
        restored = Record(data=marc_bytes, to_unicode=True, force_utf8=True)
        assert restored.title is not None
        assert "Great Gatsby" in restored.title
        assert "Fitzgerald" in restored.author

    def test_as_dict(self, sample_record):
        d = sample_record.as_dict()
        assert "leader" in d
        assert "fields" in d
        assert len(d["fields"]) > 0

    def test_as_json(self, sample_record):
        import json
        j = sample_record.as_json()
        parsed = json.loads(j)
        assert "leader" in parsed


# --- Collection CRUD ---


class TestCollectionCRUD:
    def test_add_and_get(self, tmp_collection, sample_record):
        idx = tmp_collection.add(sample_record)
        assert idx == 0
        assert len(tmp_collection) == 1
        got = tmp_collection.get(0)
        assert got.title is not None
        assert "Great Gatsby" in got.title

    def test_add_multiple(self, tmp_collection):
        r1 = make_record(title="Book One", author="Author A")
        r2 = make_record(title="Book Two", author="Author B")
        tmp_collection.add(r1)
        tmp_collection.add(r2)
        assert len(tmp_collection) == 2

    def test_update(self, tmp_collection, sample_record):
        tmp_collection.add(sample_record)
        new_rec = make_record(title="Updated Title", author="New Author")
        tmp_collection.update(0, new_rec)
        got = tmp_collection.get(0)
        assert "Updated Title" in got.title

    def test_delete(self, tmp_collection, sample_record):
        tmp_collection.add(sample_record)
        removed = tmp_collection.delete(0)
        assert "Great Gatsby" in removed.title
        assert len(tmp_collection) == 0

    def test_delete_out_of_range(self, tmp_collection):
        with pytest.raises(IndexError):
            tmp_collection.delete(99)

    def test_persistence(self, tmp_path):
        """Records survive save + reload."""
        path = tmp_path / "persist.mrc"
        coll1 = Collection(path)
        coll1.add(make_record(title="Persisted Book", author="Some Author"))

        coll2 = Collection(path)
        assert len(coll2) == 1
        assert "Persisted Book" in coll2.get(0).title

    def test_multiple_persistence(self, tmp_path):
        """Multiple records survive save + reload."""
        path = tmp_path / "multi.mrc"
        coll = Collection(path)
        for i in range(5):
            coll.add(make_record(title=f"Book {i}", author=f"Author {i}", isbn=f"ISBN-{i}"))

        coll2 = Collection(path)
        assert len(coll2) == 5
        for i in range(5):
            assert f"Book {i}" in coll2.get(i).title


# --- Search ---


class TestSearch:
    def test_search_by_title(self, tmp_collection):
        tmp_collection.add(make_record(title="Python Cookbook", author="Beazley"))
        tmp_collection.add(make_record(title="Rust Programming", author="Klabnik"))
        results = tmp_collection.search("python")
        assert len(results) == 1
        assert results[0][0] == 0

    def test_search_by_author(self, tmp_collection):
        tmp_collection.add(make_record(title="Book A", author="Hemingway, Ernest"))
        tmp_collection.add(make_record(title="Book B", author="Fitzgerald, F. Scott"))
        results = tmp_collection.search("hemingway")
        assert len(results) == 1

    def test_search_case_insensitive(self, tmp_collection):
        tmp_collection.add(make_record(title="UPPERCASE TITLE", author="Author"))
        results = tmp_collection.search("uppercase")
        assert len(results) == 1

    def test_search_no_results(self, tmp_collection):
        tmp_collection.add(make_record(title="Something", author="Nobody"))
        results = tmp_collection.search("nonexistent")
        assert len(results) == 0

    def test_search_specific_field(self, tmp_collection):
        tmp_collection.add(make_record(title="Python", author="Smith"))
        # Search in 245 (title) — should find
        results = tmp_collection.search("python", field_tag="245")
        assert len(results) == 1
        # Search in 100 (author) — should not find "python"
        results = tmp_collection.search("python", field_tag="100")
        assert len(results) == 0

    def test_search_by_isbn(self, tmp_collection):
        tmp_collection.add(make_record(title="ISBN Book", author="Auth", isbn="1234567890"))
        results = tmp_collection.search("1234567890")
        assert len(results) == 1

    def test_search_by_subject(self, tmp_collection):
        tmp_collection.add(make_record(title="Bio Book", author="Auth", subjects=["Biology"]))
        results = tmp_collection.search("biology")
        assert len(results) == 1


# --- Reports ---


class TestReports:
    def test_report_summary_empty(self, tmp_collection):
        report = tmp_collection.report_summary()
        assert "Total books: 0" in report

    def test_report_summary_with_books(self, tmp_collection, sample_record):
        tmp_collection.add(sample_record)
        tmp_collection.add(make_record(title="Another", author="Fitzgerald, F. Scott", publisher="Scribner"))
        report = tmp_collection.report_summary()
        assert "Total books: 2" in report
        assert "Fitzgerald" in report
        assert "Scribner" in report

    def test_report_detail(self, tmp_collection, sample_record):
        tmp_collection.add(sample_record)
        detail = tmp_collection.report_detail(0)
        assert "Great Gatsby" in detail
        assert "Fitzgerald" in detail
        assert "978-0743273565" in detail
        assert "Shelf A-3" in detail
        assert "classic" in detail.lower()

    def test_report_list(self, tmp_collection):
        tmp_collection.add(make_record(title="First Book", author="Author 1"))
        tmp_collection.add(make_record(title="Second Book", author="Author 2"))
        listing = tmp_collection.report_list()
        assert "First Book" in listing
        assert "Second Book" in listing
        assert "Author 1" in listing

    def test_report_list_empty(self, tmp_collection):
        listing = tmp_collection.report_list()
        assert "empty" in listing.lower()


# --- Export formats ---


class TestExport:
    def test_export_json(self, tmp_path):
        import json

        coll = Collection(tmp_path / "exp.mrc")
        coll.add(make_record(title="JSON Book", author="Author"))
        json_path = tmp_path / "out.json"
        coll.export_json(json_path)

        with open(json_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_export_xml(self, tmp_path):
        coll = Collection(tmp_path / "exp.mrc")
        coll.add(make_record(title="XML Book", author="Author"))
        xml_path = tmp_path / "out.xml"
        coll.export_xml(xml_path)

        content = xml_path.read_bytes()
        assert b"<record" in content
        assert b"XML Book" in content

    def test_export_text(self, tmp_path):
        coll = Collection(tmp_path / "exp.mrc")
        coll.add(make_record(title="Text Book", author="Author"))
        txt_path = tmp_path / "out.txt"
        coll.export_text(txt_path)

        content = txt_path.read_text()
        assert "=245" in content
        assert "Text Book" in content


# --- Import ---


class TestImport:
    def test_import_marc(self, tmp_path):
        """Create a .mrc, then import it into a fresh collection."""
        src = Collection(tmp_path / "source.mrc")
        src.add(make_record(title="Imported Book", author="Imported Author"))
        src.add(make_record(title="Second Import", author="Another Author"))

        dest = Collection(tmp_path / "dest.mrc")
        count = dest.import_marc(tmp_path / "source.mrc")
        assert count == 2
        assert len(dest) == 2
        assert "Imported Book" in dest.get(0).title

    def test_import_xml(self, tmp_path):
        """Export as XML, then import from XML into fresh collection."""
        src = Collection(tmp_path / "source.mrc")
        src.add(make_record(title="XML Import Test", author="Author"))
        xml_path = tmp_path / "export.xml"
        src.export_xml(xml_path)

        dest = Collection(tmp_path / "dest.mrc")
        count = dest.import_xml(xml_path)
        assert count == 1
        assert "XML Import Test" in dest.get(0).title


# --- Field-level exercises of rmarc ---


class TestRmarcFeatures:
    """Directly exercise rmarc features through the app's records."""

    def test_field_iteration(self, sample_record):
        """Iterate fields on a record."""
        tags = [f.tag for f in sample_record.get_fields()]
        assert "245" in tags
        assert "100" in tags
        assert "008" in tags

    def test_subfield_iteration(self, sample_record):
        """Iterate subfields on a field."""
        f245 = sample_record.get("245")
        codes = [sf.code for sf in f245]
        assert "a" in codes

    def test_subfield_dict(self, sample_record):
        """subfields_as_dict on a field."""
        f245 = sample_record.get("245")
        d = f245.subfields_as_dict()
        assert "a" in d
        assert isinstance(d["a"], list)

    def test_contains_check(self, sample_record):
        assert "245" in sample_record
        assert "999" not in sample_record

    def test_field_contains_subfield(self, sample_record):
        f245 = sample_record.get("245")
        assert "a" in f245
        assert "z" not in f245

    def test_get_subfields(self, sample_record):
        f245 = sample_record.get("245")
        vals = f245.get_subfields("a", "c")
        assert len(vals) >= 1

    def test_add_subfield(self, sample_record):
        f245 = sample_record.get("245")
        original_count = len(f245.subfields)
        f245.add_subfield("b", "a subtitle")
        assert len(f245.subfields) == original_count + 1

    def test_delete_subfield(self, sample_record):
        f245 = sample_record.get("245")
        f245.add_subfield("b", "temp subtitle")
        deleted = f245.delete_subfield("b")
        assert deleted == "temp subtitle"

    def test_set_subfield(self, sample_record):
        f020 = sample_record.get("020")
        f020["a"] = "NEW-ISBN"
        assert f020["a"] == "NEW-ISBN"

    def test_field_value(self, sample_record):
        f245 = sample_record.get("245")
        val = f245.value()
        assert "Great Gatsby" in val

    def test_format_field(self, sample_record):
        f245 = sample_record.get("245")
        fmt = f245.format_field()
        assert "Great Gatsby" in fmt

    def test_is_subject_field(self, sample_record):
        for field in sample_record.subjects:
            assert field.is_subject_field()
        f245 = sample_record.get("245")
        assert not f245.is_subject_field()

    def test_indicators(self, sample_record):
        f245 = sample_record.get("245")
        assert f245.indicator1 == "1"  # has author
        assert f245.indicator2 == "0"

    def test_control_field_properties(self, sample_record):
        f008 = sample_record.get("008")
        assert f008.control_field
        assert f008.data is not None

    def test_record_str(self, sample_record):
        """str(record) should give MARCMaker format."""
        text = str(sample_record)
        assert "=245" in text
        assert "=100" in text

    def test_record_properties(self, sample_record):
        """Exercise all the convenience properties."""
        assert sample_record.title is not None
        assert sample_record.author is not None
        assert sample_record.isbn is not None
        assert sample_record.publisher is not None
        assert sample_record.pubyear is not None
        assert len(sample_record.subjects) > 0
        assert len(sample_record.notes) > 0
        assert len(sample_record.location) > 0

    def test_add_ordered_field(self):
        """add_ordered_field should keep fields sorted by tag."""
        rec = Record()
        rec.add_ordered_field(Field(tag="500", subfields=[Subfield("a", "note")]))
        rec.add_ordered_field(Field(tag="100", subfields=[Subfield("a", "author")]))
        rec.add_ordered_field(Field(tag="245", subfields=[Subfield("a", "title")]))
        tags = [f.tag for f in rec.get_fields()]
        assert tags == sorted(tags)

    def test_add_grouped_field(self):
        """add_grouped_field should group fields with same tag."""
        rec = Record()
        rec.add_grouped_field(Field(tag="650", subfields=[Subfield("a", "Subject 1")]))
        rec.add_grouped_field(Field(tag="245", subfields=[Subfield("a", "Title")]))
        rec.add_grouped_field(Field(tag="650", subfields=[Subfield("a", "Subject 2")]))
        # The two 650 fields should be adjacent
        tags = [f.tag for f in rec.get_fields()]
        first_650 = tags.index("650")
        second_650 = tags.index("650") + tags[first_650 + 1:].index("650") + 1 if tags.count("650") > 1 else first_650
        assert second_650 == first_650 + 1

    def test_remove_fields(self, sample_record):
        assert "650" in sample_record
        sample_record.remove_fields("650")
        assert "650" not in sample_record

    def test_field_as_marc(self, sample_record):
        f245 = sample_record.get("245")
        marc_bytes = f245.as_marc("utf-8")
        assert isinstance(marc_bytes, bytes)

    def test_record_as_marc(self, sample_record):
        marc_bytes = sample_record.as_marc()
        assert isinstance(marc_bytes, bytes)
        assert len(marc_bytes) > 0
