"""BookShelf CLI - manage your personal book collection with MARC records.

Usage:
    python -m sample_app <command> [options]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sample_app.goodreads import import_goodreads
from sample_app.loc import fetch_marc_by_lccn, search_loc
from sample_app.store import Collection, make_record

DEFAULT_COLLECTION = "bookshelf.mrc"


def get_collection(args: argparse.Namespace) -> Collection:
    return Collection(args.collection)


# --- Commands ---


def cmd_add(args: argparse.Namespace) -> None:
    """Add a book to the collection."""
    coll = get_collection(args)
    subjects = [s.strip() for s in args.subjects.split(";")] if args.subjects else []
    record = make_record(
        title=args.title,
        author=args.author,
        isbn=args.isbn,
        publisher=args.publisher,
        year=args.year,
        subjects=subjects,
        notes=args.notes,
        location=args.location,
    )
    idx = coll.add(record)
    print(f"Added book #{idx}: {args.title}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all books in the collection."""
    coll = get_collection(args)
    if len(coll) == 0:
        print("Collection is empty.")
        return
    print(f"Books in {args.collection} ({len(coll)} total):\n")
    print(coll.report_list())


def cmd_show(args: argparse.Namespace) -> None:
    """Show detailed info for a specific book."""
    coll = get_collection(args)
    try:
        print(coll.report_detail(args.index))
    except IndexError:
        print(f"Error: No book at index {args.index}. Collection has {len(coll)} books.", file=sys.stderr)
        sys.exit(1)


def cmd_edit(args: argparse.Namespace) -> None:
    """Edit fields of an existing book."""
    coll = get_collection(args)
    try:
        record = coll.get(args.index)
    except IndexError:
        print(f"Error: No book at index {args.index}.", file=sys.stderr)
        sys.exit(1)

    from rmarc import Field, Indicators, Subfield

    if args.title:
        record.remove_fields("245")
        author = record.author
        ind1 = "1" if author else "0"
        subs = [Subfield("a", args.title)]
        if author:
            subs.append(Subfield("c", author))
        record.add_ordered_field(Field(tag="245", indicators=Indicators(ind1, "0"), subfields=subs))

    if args.author:
        record.remove_fields("100")
        record.add_ordered_field(
            Field(tag="100", indicators=Indicators("1", " "), subfields=[Subfield("a", args.author)])
        )

    if args.isbn:
        record.remove_fields("020")
        record.add_ordered_field(
            Field(tag="020", indicators=Indicators(" ", " "), subfields=[Subfield("a", args.isbn)])
        )

    if args.publisher:
        record.remove_fields("260")
        subs = [Subfield("b", args.publisher)]
        yr = record.pubyear
        if yr:
            subs.append(Subfield("c", yr))
        record.add_ordered_field(Field(tag="260", indicators=Indicators(" ", " "), subfields=subs))

    if args.year:
        f260 = record.get("260")
        if f260:
            record.remove_fields("260")
            subs = [s for s in f260.subfields if s.code != "c"]
            subs.append(Subfield("c", args.year))
            record.add_ordered_field(Field(tag="260", indicators=Indicators(" ", " "), subfields=subs))
        else:
            record.add_ordered_field(
                Field(tag="260", indicators=Indicators(" ", " "), subfields=[Subfield("c", args.year)])
            )

    if args.notes:
        record.add_ordered_field(
            Field(tag="500", indicators=Indicators(" ", " "), subfields=[Subfield("a", args.notes)])
        )

    if args.location:
        record.remove_fields("852")
        record.add_ordered_field(
            Field(tag="852", indicators=Indicators(" ", " "), subfields=[Subfield("a", args.location)])
        )

    coll.update(args.index, record)
    print(f"Updated book #{args.index}.")


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a book from the collection."""
    coll = get_collection(args)
    try:
        removed = coll.delete(args.index)
        print(f"Deleted book #{args.index}: {removed.title or 'Untitled'}")
    except IndexError:
        print(f"Error: No book at index {args.index}.", file=sys.stderr)
        sys.exit(1)


def cmd_search(args: argparse.Namespace) -> None:
    """Search the collection."""
    coll = get_collection(args)
    results = coll.search(args.query, field_tag=args.field)
    if not results:
        print("No results found.")
        return
    print(f"Found {len(results)} result(s):\n")
    for idx, rec in results:
        title = rec.title or "Untitled"
        author = rec.author or "Unknown"
        print(f"  {idx:>4}  {title} / {author}")


def cmd_report(args: argparse.Namespace) -> None:
    """Print a collection summary report."""
    coll = get_collection(args)
    print(coll.report_summary())


def cmd_export(args: argparse.Namespace) -> None:
    """Export collection to JSON, XML, or text."""
    coll = get_collection(args)
    fmt = args.format.lower()
    out = args.output

    if fmt == "json":
        coll.export_json(out)
    elif fmt == "xml":
        coll.export_xml(out)
    elif fmt == "text":
        coll.export_text(out)
    else:
        print(f"Unknown format: {fmt}. Use json, xml, or text.", file=sys.stderr)
        sys.exit(1)
    print(f"Exported {len(coll)} record(s) to {out} ({fmt})")


def cmd_import(args: argparse.Namespace) -> None:
    """Import records from a MARC21 or MARCXML file."""
    coll = get_collection(args)
    path = Path(args.input)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    fmt = args.format.lower()
    if fmt == "marc":
        count = coll.import_marc(path)
    elif fmt == "xml":
        count = coll.import_xml(path)
    else:
        print(f"Unknown format: {fmt}. Use marc or xml.", file=sys.stderr)
        sys.exit(1)
    print(f"Imported {count} record(s) from {path}")


def cmd_import_goodreads(args: argparse.Namespace) -> None:
    """Import books from a Goodreads library export CSV."""
    coll = get_collection(args)
    path = Path(args.csv)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    def progress(current: int, total: int, title: str) -> None:
        print(f"  [{current}/{total}] {title}")

    enrich = args.enrich
    if enrich:
        print(f"Importing from {path} with Library of Congress enrichment...")
    else:
        print(f"Importing from {path}...")

    count = import_goodreads(path, coll, enrich=enrich, batch_size=args.batch_size, on_progress=progress)
    print(f"Imported {count} book(s) from Goodreads CSV.")


def cmd_loc_search(args: argparse.Namespace) -> None:
    """Search the Library of Congress catalog."""
    try:
        results = search_loc(args.query, max_results=args.max)
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No results found at Library of Congress.")
        return

    print(f"Library of Congress results for '{args.query}':\n")
    for i, r in enumerate(results):
        lccn_part = f" (LCCN: {r['lccn']})" if r["lccn"] else ""
        print(f"  {i:>3}  {r['title']} / {r['author'] or 'Unknown'} {r['date']}{lccn_part}")


def cmd_loc_fetch(args: argparse.Namespace) -> None:
    """Fetch a MARC record from LOC by LCCN and add to collection."""
    try:
        record = fetch_marc_by_lccn(args.lccn)
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if record is None:
        print(f"Could not retrieve MARC record for LCCN {args.lccn}.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched: {record.title or 'Untitled'} / {record.author or 'Unknown'}")

    if args.show:
        print("\nMARC fields:")
        for field in record.get_fields():
            print(f"  {field}")
        print()

    if not args.no_add:
        coll = get_collection(args)
        idx = coll.add(record)
        print(f"Added to collection as #{idx}.")
    else:
        print("(Not added to collection; use without --no-add to save.)")


# --- Parser ---


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookshelf",
        description="BookShelf: manage your personal book collection with MARC records.",
    )
    parser.add_argument(
        "-c",
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Path to the .mrc collection file (default: {DEFAULT_COLLECTION})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a book")
    p_add.add_argument("title", help="Book title")
    p_add.add_argument("author", help="Author name")
    p_add.add_argument("--isbn", default="", help="ISBN")
    p_add.add_argument("--publisher", default="", help="Publisher")
    p_add.add_argument("--year", default="", help="Publication year")
    p_add.add_argument("--subjects", default="", help="Subjects separated by semicolons")
    p_add.add_argument("--notes", default="", help="General note")
    p_add.add_argument("--location", default="", help="Shelf location")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="List all books")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = sub.add_parser("show", help="Show details of a book")
    p_show.add_argument("index", type=int, help="Book index number")
    p_show.set_defaults(func=cmd_show)

    # edit
    p_edit = sub.add_parser("edit", help="Edit a book's fields")
    p_edit.add_argument("index", type=int, help="Book index number")
    p_edit.add_argument("--title", default="", help="New title")
    p_edit.add_argument("--author", default="", help="New author")
    p_edit.add_argument("--isbn", default="", help="New ISBN")
    p_edit.add_argument("--publisher", default="", help="New publisher")
    p_edit.add_argument("--year", default="", help="New year")
    p_edit.add_argument("--notes", default="", help="Add a note")
    p_edit.add_argument("--location", default="", help="New shelf location")
    p_edit.set_defaults(func=cmd_edit)

    # delete
    p_del = sub.add_parser("delete", help="Delete a book")
    p_del.add_argument("index", type=int, help="Book index number")
    p_del.set_defaults(func=cmd_delete)

    # search
    p_search = sub.add_parser("search", help="Search the collection")
    p_search.add_argument("query", help="Search text")
    p_search.add_argument("--field", default=None, help="Limit search to a MARC field tag (e.g. 245, 100)")
    p_search.set_defaults(func=cmd_search)

    # report
    p_report = sub.add_parser("report", help="Collection summary report")
    p_report.set_defaults(func=cmd_report)

    # export
    p_export = sub.add_parser("export", help="Export collection to another format")
    p_export.add_argument("format", choices=["json", "xml", "text"], help="Export format")
    p_export.add_argument("output", help="Output file path")
    p_export.set_defaults(func=cmd_export)

    # import
    p_import = sub.add_parser("import", help="Import records from file")
    p_import.add_argument("format", choices=["marc", "xml"], help="Input format")
    p_import.add_argument("input", help="Input file path")
    p_import.set_defaults(func=cmd_import)

    # import-goodreads
    p_igr = sub.add_parser("import-goodreads", help="Import from Goodreads CSV export")
    p_igr.add_argument("csv", help="Path to goodreads_library_export.csv")
    p_igr.add_argument("--enrich", action="store_true", help="Fetch full MARC records from Library of Congress")
    p_igr.add_argument("--batch-size", type=int, default=20, help="Concurrent LOC requests per batch (default: 20)")
    p_igr.set_defaults(func=cmd_import_goodreads)

    # loc-search
    p_locsearch = sub.add_parser("loc-search", help="Search Library of Congress catalog")
    p_locsearch.add_argument("query", help="Search query")
    p_locsearch.add_argument("--max", type=int, default=5, help="Max results (default: 5)")
    p_locsearch.set_defaults(func=cmd_loc_search)

    # loc-fetch
    p_locfetch = sub.add_parser("loc-fetch", help="Fetch MARC record from LOC by LCCN")
    p_locfetch.add_argument("lccn", help="Library of Congress Control Number")
    p_locfetch.add_argument("--show", action="store_true", help="Display the MARC record")
    p_locfetch.add_argument("--no-add", action="store_true", help="Don't add to collection")
    p_locfetch.set_defaults(func=cmd_loc_fetch)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
