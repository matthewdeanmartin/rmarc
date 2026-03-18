# BookShelf User Guide

BookShelf stores your personal book collection as a MARC21 binary file
(`bookshelf.mrc` by default). MARC21 is the same format used by libraries
worldwide, so records you fetch from the Library of Congress drop straight in.

## Running the app

```bash
# From the rmarc repo root, prefix every command with:
uv run python -m sample_app [global options] <command> [command options]
```

Use `-c` / `--collection` to point at a different file:

```bash
uv run python -m sample_app -c ~/books/fiction.mrc list
```

---

## Commands at a glance

| Command | What it does |
|---|---|
| `add` | Create a new book record |
| `list` | One-line listing of all books |
| `show` | Full detail for one book |
| `edit` | Change fields on an existing book |
| `delete` | Remove a book |
| `search` | Case-insensitive text search |
| `report` | Summary statistics |
| `export` | Save collection as JSON, XML, or text |
| `import` | Load records from a MARC21 or MARCXML file |
| `loc-search` | Search the Library of Congress catalog |
| `loc-fetch` | Download a LOC record by LCCN and add it |

---

## add

Create a book record and append it to the collection.

```
add <title> <author> [options]
```

| Argument | Description |
|---|---|
| `title` | Book title (required, positional) |
| `author` | Author name (required, positional) |
| `--isbn` | ISBN (any format) |
| `--publisher` | Publisher name |
| `--year` | Four-digit publication year |
| `--subjects` | Subject headings, separated by `;` |
| `--notes` | Free-text note (can be added multiple times via `edit`) |
| `--location` | Physical shelf location |

```bash
uv run python -m sample_app add "The Great Gatsby" "Fitzgerald, F. Scott" \
    --isbn 978-0743273565 \
    --publisher Scribner \
    --year 1925 \
    --subjects "American fiction;Jazz Age" \
    --notes "First edition purchased 2024" \
    --location "Shelf A-3"
```

Output:

```
Added book #0: The Great Gatsby
```

The number after `#` is the **index** used by `show`, `edit`, and `delete`.

---

## list

Print a compact one-line entry for every book.

```bash
uv run python -m sample_app list
```

```
Books in bookshelf.mrc (3 total):

     0  The Great Gatsby / Fitzgerald, F. Scott [9780743273565]
     1  Moby Dick / Melville, Herman [9780142437247]
     2  1984 / Orwell, George [9780451524935]
```

The first column is the index. Brackets contain the ISBN when present.

---

## show

Print everything known about one book, including the raw MARC fields.

```bash
uv run python -m sample_app show 0
```

```
Record #0
  Title:     The Great Gatsby
  Author:    Fitzgerald, F. Scott
  ISBN:      9780743273565
  Publisher: Scribner
  Year:      1925
  Subjects:  American fiction; Jazz Age
  Note:      First edition purchased 2024
  Location:  Shelf A-3

  Raw MARC fields:
    =008  \\\\\\\\s1925\\\\xx\\\\\\\\\\\\\\\\\\\\000\0eng\d
    =020  \\$a9780743273565
    =100  1\$aFitzgerald, F. Scott
    =245  10$aThe Great Gatsby$cFitzgerald, F. Scott
    =260  \\$bScribner$c1925
    =500  \\$aFirst edition purchased 2024
    =650  \0$aAmerican fiction
    =650  \0$aJazz Age
    =852  \\$aShelf A-3
```

The "Raw MARC fields" section shows the actual MARC encoding (MARCMaker
notation). Backslash `\` represents a blank indicator or blank space in
control field data.

---

## edit

Change one or more fields. Only the flags you supply are modified; everything
else is left alone.

```bash
# Fix a typo in the title
uv run python -m sample_app edit 0 --title "The Great Gatsby"

# Update the ISBN
uv run python -m sample_app edit 0 --isbn 9780743273565

# Add a shelf location
uv run python -m sample_app edit 0 --location "Living Room"

# Add a note (appended, not replaced)
uv run python -m sample_app edit 0 --notes "Borrowed to Alice 2025-01"
```

| Flag | Effect |
|---|---|
| `--title` | Replace field 245 |
| `--author` | Replace field 100 |
| `--isbn` | Replace field 020 |
| `--publisher` | Replace publisher in field 260 (preserves year) |
| `--year` | Replace year in field 260 (preserves publisher) |
| `--notes` | Append a new field 500 note |
| `--location` | Replace field 852 |

---

## delete

Remove a book by index. Indices shift down after deletion, so use `list` to
confirm the current index before deleting.

```bash
uv run python -m sample_app delete 1
```

```
Deleted book #1: Moby Dick
```

---

## search

Case-insensitive substring search across every MARC field in every record.

```bash
uv run python -m sample_app search fitzgerald
```

```
Found 1 result(s):

     0  The Great Gatsby / Fitzgerald, F. Scott
```

Narrow the search to a specific MARC field tag with `--field`:

```bash
# Only look in title fields (245)
uv run python -m sample_app search gatsby --field 245

# Only look in subject fields (650)
uv run python -m sample_app search "Jazz Age" --field 650

# Only look at authors (100)
uv run python -m sample_app search orwell --field 100
```

---

## report

Print collection statistics: total count, authors, subjects, publishers, and
years.

```bash
uv run python -m sample_app report
```

```
Collection: bookshelf.mrc
Total books: 3

Authors:
  Fitzgerald, F. Scott: 1 book(s)
  Melville, Herman: 1 book(s)
  Orwell, George: 1 book(s)

Subjects:
  American fiction: 1 book(s)
  Dystopia: 1 book(s)
  Jazz Age: 1 book(s)

Publishers:
  Scribner: 1 book(s)

Publication Years:
  1851: 1 book(s)
  1925: 1 book(s)
  1949: 1 book(s)
```

---

## export

Save the entire collection in another format.

```bash
# MARC-in-JSON (one array of objects)
uv run python -m sample_app export json ~/backups/books.json

# MARCXML collection
uv run python -m sample_app export xml ~/backups/books.xml

# Human-readable MARCMaker text
uv run python -m sample_app export text ~/backups/books.txt
```

**JSON format** (MARC-in-JSON standard):

```json
[
  {
    "leader": "00000nam a2200000   4500",
    "fields": [
      {"008": "      s1925    xx            000 0 eng d"},
      {"020": {"ind1": " ", "ind2": " ", "subfields": [{"a": "9780743273565"}]}},
      {"245": {"ind1": "1", "ind2": "0", "subfields": [{"a": "The Great Gatsby"}, {"c": "Fitzgerald, F. Scott"}]}}
    ]
  }
]
```

**XML format** (MARCXML / MARC21slim):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <leader>00000nam a2200000   4500</leader>
    <controlfield tag="008">      s1925    xx            000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">The Great Gatsby</subfield>
    </datafield>
  </record>
</collection>
```

**Text format** (MARCMaker — what `show` prints):

```
=LDR  00000nam a2200000   4500
=008  \\\\\\\\s1925\\\\xx\\\\\\\\\\\\000\0eng\d
=245  10$aThe Great Gatsby$cFitzgerald, F. Scott
```

---

## import

Add records from an existing MARC21 binary file or MARCXML file into the
current collection.

```bash
# Import from another .mrc file
uv run python -m sample_app import marc ~/downloads/catalog_export.mrc

# Import from MARCXML
uv run python -m sample_app import xml ~/downloads/records.xml
```

This is additive — existing records are kept, new ones are appended.

---

## loc-search

Search the Library of Congress catalog for books matching a query. Requires
internet access.

```bash
uv run python -m sample_app loc-search "moby dick"
uv run python -m sample_app loc-search "orwell" --max 10
```

```
Library of Congress results for 'moby dick':

    0  Moby-Dick / Melville, Herman 2002 (LCCN: 2002727588)
    1  The whale / Melville, Herman 1987
    2  Moby Dick / Melville, Herman 1956 (LCCN: 56013141)
```

The LCCN in parentheses is the Library of Congress Control Number, used with
`loc-fetch`.

---

## loc-fetch

Download the official MARC record from the Library of Congress by LCCN and
add it to your collection.

```bash
# Fetch and add
uv run python -m sample_app loc-fetch 2002727588

# Fetch, display all MARC fields, but don't add to collection
uv run python -m sample_app loc-fetch 2002727588 --show --no-add
```

```
Fetched: Moby-Dick / Melville, Herman
Added to collection as #3.
```

With `--show --no-add`:

```
Fetched: Moby-Dick / Melville, Herman

MARC fields:
  =001  2002727588
  =003  DLC
  =008  020308s2002    nyu      b    000 1 eng
  =020  \\$a0142437247
  =100  1\$aMelville, Herman,$d1819-1891.
  =245  10$aMoby-Dick /$cHerman Melville ; edited and introduced by Andrew Delbanco.
  ...

(Not added to collection; use without --no-add to save.)
```

LOC records are richer than manually-entered ones — they typically include
added entries (7xx), series (8xx), subject subdivisions, and LC call numbers.

---

## Working with multiple collections

Use `-c` to maintain separate files:

```bash
uv run python -m sample_app -c fiction.mrc   add "Dune" "Herbert, Frank"
uv run python -m sample_app -c nonfiction.mrc add "Sapiens" "Harari, Yuval Noah"

# Merge nonfiction into fiction
uv run python -m sample_app -c fiction.mrc import marc nonfiction.mrc
```

---

## Tips

- **Indices are positional.** After a `delete`, re-run `list` before using
  `show` or `edit`.
- **`--subjects` uses `;` as separator** so individual subjects can contain
  spaces and commas.
- **The `.mrc` file is the source of truth.** You can share or back it up like
  any other file. To inspect it with standard tools, export to JSON or text.
- **Fetched LOC records are authoritative.** They follow MARC21 cataloging
  standards more rigorously than hand-entered records.
