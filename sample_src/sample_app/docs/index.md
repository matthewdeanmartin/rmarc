# BookShelf Sample App

BookShelf is a personal book collection manager that uses
[rmarc](https://github.com/matthewdeanmartin/rmarc) for all storage and
manipulation. It is a **dog-fooding exercise**: every feature of rmarc is
exercised through a realistic application rather than synthetic unit tests.

## Documents

| Document | Audience |
|---|---|
| [User Guide](user_guide.md) | Anyone who wants to run the app |
| [Developer Guide](developer_guide.md) | Python developers learning the rmarc API |
| [rmarc API Patterns](rmarc_patterns.md) | rmarc contributors / library users |

## Quick start

```bash
# From the repo root
cd /path/to/rmarc

# Add a book
uv run python -m sample_app add "Moby Dick" "Melville, Herman" \
    --isbn 978-0142437247 --year 1851 --subjects "Sea stories;Whales"

# List everything
uv run python -m sample_app list

# Search
uv run python -m sample_app search melville

# Fetch from Library of Congress
uv run python -m sample_app loc-search "moby dick"
uv run python -m sample_app loc-fetch 2002727588
```
