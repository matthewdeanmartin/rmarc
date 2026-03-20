# BookShelf — Sample App for rmarc

BookShelf is a personal book collection manager that uses MARC21 records as its
canonical storage format.  It exists primarily as a **dogfooding test** for the
[rmarc](https://github.com/matthewdeanmartin/rmarc) library: real-world,
natural-looking application code that exercises rmarc the way an actual consumer
would, complementing the unit-test suite which can pass even when real usage
fails.

## What it does

| Feature | CLI | GUI |
|---|---|---|
| Add / edit / delete books | `bookshelf add "Title" "Author"` | Add Book dialog |
| List & search collection | `bookshelf list`, `bookshelf search` | Treeview table with live filter |
| Import Goodreads CSV | `bookshelf import-goodreads export.csv` | File > Import Goodreads CSV |
| LOC enrichment | `--enrich` flag (parallel batches) | Prompted on import |
| Search Library of Congress | `bookshelf loc-search "query"` | Books > Search LOC dialog |
| Fetch by LCCN | `bookshelf loc-fetch <lccn>` | Fetch & Add in LOC dialog |
| Export (JSON / XML / text) | `bookshelf export json out.json` | File > Export as ... |
| Import MARC / MARCXML | `bookshelf import marc file.mrc` | File > Import MARC file |

The CLI is intended for scripting and automation; the GUI is a companion for
interactive use.  Both share the same `store.py` and `loc.py` modules.

### Quick start

```bash
# from the repo root
uv run python -m sample_app list                       # CLI
uv run python -m sample_app import-goodreads data/sample.csv  # import sample data
uv run python -m sample_app.ui                         # launch GUI
```

## How the polyrepo / uv-workspace pattern works

This repo uses a **uv workspace** so that the main library (`rmarc`) and its
sample app live in the same Git repository but are separate Python packages with
independent `pyproject.toml` files.

### Directory layout

```
repo-root/
├── pyproject.toml              # main library (rmarc)
├── python/rmarc/               # library source
├── src/                        # Rust source (PyO3)
├── sample_src/
│   ├── Makefile                # build / test / run shortcuts for the sample app
│   └── sample_app/
│       ├── pyproject.toml      # sample app package — depends on rmarc
│       ├── sample_app/         # Python package
│       │   ├── __init__.py
│       │   ├── cli.py
│       │   ├── store.py
│       │   ├── loc.py
│       │   ├── goodreads.py
│       │   ├── ui.py
│       │   └── data/
│       │       └── sample.csv
│       ├── tests/
│       └── docs/
└── ...
```

### Key pieces

1. **Root `pyproject.toml`** declares the workspace:

   ```toml
   [tool.uv.workspace]
   members = [
       "./",
       "sample_src/sample_app",
   ]
   ```

2. **Sample app `pyproject.toml`** depends on the library as a workspace source:

   ```toml
   [project]
   dependencies = ["rmarc"]

   [tool.uv.sources]
   rmarc = { workspace = true }
   ```

   This means `uv` resolves `rmarc` from the local workspace instead of PyPI,
   so the sample app always tests against the local checkout.

3. **`sample_src/Makefile`** provides shortcuts (`make test`, `make run`,
   `make run-gui`) that call `uv run` from the repo root.

### Why this pattern

- **Dogfooding**: the sample app imports rmarc as a normal dependency, not via
  `sys.path` hacks.  If the public API breaks, the sample app breaks too.
- **Separate concerns**: the sample app has its own pyproject.toml, tests, and
  docs.  It doesn't pollute the library's dependency list or test matrix.
- **One `uv sync`**: a single `uv sync` at the repo root installs both
  packages in editable mode.  No manual `pip install -e` dance.
- **Reusable template**: copy the `sample_src/` pattern into any library repo
  to add a dogfooding app.  Update the workspace `members` list and the
  `[tool.uv.sources]` table and you're set.
