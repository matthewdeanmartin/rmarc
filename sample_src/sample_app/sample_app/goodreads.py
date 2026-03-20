"""Import a Goodreads library-export CSV into a BookShelf collection.

Each row is converted to a MARC21 record via ``store.make_record``.
Optionally enriches records by fetching full cataloguing data from the
Library of Congress in parallel batches.
"""

from __future__ import annotations

import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sample_app.loc import fetch_marc_by_lccn, search_loc
from sample_app.store import Collection, make_record


def _clean_isbn(raw: str) -> str:
    """Strip the ``="..."`` quoting Goodreads wraps around ISBNs."""
    return re.sub(r'[=""]', "", raw).strip()


def _shelf_to_note(shelf: str) -> str:
    if shelf and shelf != "read":
        return f"Goodreads shelf: {shelf}"
    return ""


def parse_goodreads_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a Goodreads export CSV and return a list of row dicts."""
    rows: list[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def row_to_record(row: dict[str, str]):
    """Convert a single Goodreads CSV row to an rmarc Record."""
    title = row.get("Title", "").strip()
    author = row.get("Author l-f", "") or row.get("Author", "")
    author = author.strip()

    isbn = _clean_isbn(row.get("ISBN", ""))
    isbn13 = _clean_isbn(row.get("ISBN13", ""))
    best_isbn = isbn13 or isbn

    publisher = row.get("Publisher", "").strip()
    year = row.get("Year Published", "").strip() or row.get("Original Publication Year", "").strip()

    shelf = row.get("Exclusive Shelf", "").strip()
    notes_parts = []
    if shelf:
        note = _shelf_to_note(shelf)
        if note:
            notes_parts.append(note)
    rating = row.get("My Rating", "0").strip()
    if rating and rating != "0":
        notes_parts.append(f"Rating: {rating}/5")
    review = row.get("My Review", "").strip()
    if review:
        notes_parts.append(f"Review: {review}")

    notes = "; ".join(notes_parts)

    bookshelves = row.get("Bookshelves", "").strip()
    subjects = [s.strip() for s in bookshelves.split(",") if s.strip()] if bookshelves else []

    return make_record(
        title=title,
        author=author,
        isbn=best_isbn,
        publisher=publisher,
        year=year,
        subjects=subjects,
        notes=notes,
    )


def _try_enrich_one(title: str, author: str, isbn: str) -> tuple[str, object | None]:
    """Try to find and fetch a Library of Congress record for one book.

    Returns ``(title, record_or_None)``.
    """
    # Try ISBN search first, then title+author
    queries = []
    if isbn:
        queries.append(isbn)
    if title:
        q = title
        if author:
            q += f" {author.split(',')[0]}"
        queries.append(q)

    for query in queries:
        try:
            results = search_loc(query, max_results=1)
        except ConnectionError:
            continue
        if results and results[0].get("lccn"):
            try:
                rec = fetch_marc_by_lccn(results[0]["lccn"])
                if rec is not None:
                    return title, rec
            except ConnectionError:
                continue
    return title, None


def import_goodreads(
    csv_path: str | Path,
    collection: Collection,
    enrich: bool = False,
    batch_size: int = 20,
    on_progress: callable | None = None,
) -> int:
    """Import a Goodreads CSV into a collection.

    Parameters
    ----------
    csv_path:
        Path to the Goodreads library_export CSV file.
    collection:
        Target collection to add records to.
    enrich:
        If True, attempt to fetch full MARC records from Library of Congress.
    batch_size:
        Number of concurrent LOC requests when enriching.
    on_progress:
        Optional callback ``(current, total, title)`` for progress reporting.

    Returns the number of records imported.
    """
    rows = parse_goodreads_csv(csv_path)
    total = len(rows)
    imported = 0

    if not enrich:
        for i, row in enumerate(rows):
            record = row_to_record(row)
            collection.add(record)
            imported += 1
            if on_progress:
                on_progress(i + 1, total, row.get("Title", ""))
        return imported

    # Enriched import: try LOC in parallel batches, fall back to CSV data
    for batch_start in range(0, total, batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        futures = {}

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            for idx_in_batch, row in enumerate(batch):
                title = row.get("Title", "").strip()
                author = row.get("Author l-f", "") or row.get("Author", "")
                isbn = _clean_isbn(row.get("ISBN13", "")) or _clean_isbn(row.get("ISBN", ""))
                future = executor.submit(_try_enrich_one, title, author.strip(), isbn)
                futures[future] = (batch_start + idx_in_batch, row)

            for future in as_completed(futures):
                global_idx, row = futures[future]
                _, loc_record = future.result()

                if loc_record is not None:
                    collection.add(loc_record)
                else:
                    record = row_to_record(row)
                    collection.add(record)

                imported += 1
                if on_progress:
                    on_progress(imported, total, row.get("Title", ""))

    return imported
