#!/usr/bin/env bash
# sample_integration_test.sh
#
# End-to-end integration test for BookShelf / rmarc.
# Exercises every CLI command including live Library of Congress API calls.
#
# Usage:
#   bash sample_app/sample_integration_test.sh
#
# Requirements:
#   - uv available on PATH (repo uses uv for dependency management)
#   - Internet access (for loc-search and loc-fetch)
#
# Exit codes:
#   0  all assertions passed
#   1  one or more assertions failed

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS=0
FAIL=0
TOTAL=0

# Colours (suppressed when not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' CYAN='' RESET=''
fi

section() { echo -e "\n${CYAN}=== $* ===${RESET}"; }

pass() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    echo -e "  ${GREEN}PASS${RESET}  $*"
}

fail() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo -e "  ${RED}FAIL${RESET}  $*"
}

# assert_contains <label> <haystack> <needle>
assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -qF "$needle"; then
        pass "$label"
    else
        fail "$label  (expected to find: '$needle')"
        echo "       Output was: $haystack"
    fi
}

# assert_not_contains <label> <haystack> <needle>
assert_not_contains() {
    local label="$1" haystack="$2" needle="$3"
    if ! echo "$haystack" | grep -qF "$needle"; then
        pass "$label"
    else
        fail "$label  (did NOT expect to find: '$needle')"
    fi
}

# assert_file_contains <label> <file> <needle>
assert_file_contains() {
    local label="$1" file="$2" needle="$3"
    if grep -qF "$needle" "$file" 2>/dev/null; then
        pass "$label"
    else
        fail "$label  (file '$file' does not contain: '$needle')"
    fi
}

# assert_file_exists <label> <file>
assert_file_exists() {
    local label="$1" file="$2"
    if [ -f "$file" ]; then
        pass "$label"
    else
        fail "$label  (file not found: '$file')"
    fi
}

# assert_exit_ok <label> — last command must have exited 0
assert_exit_ok() {
    local label="$1" code="${2:-$?}"
    if [ "$code" -eq 0 ]; then
        pass "$label"
    else
        fail "$label  (exit code: $code)"
    fi
}

# Run bookshelf command and capture stdout+stderr
bs() { uv run python -m sample_app -c "$COLL" "$@" 2>&1; }

# ---------------------------------------------------------------------------
# Setup: temp workspace
# ---------------------------------------------------------------------------

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

COLL="$TMPDIR_TEST/test.mrc"
EXPORT_JSON="$TMPDIR_TEST/export.json"
EXPORT_XML="$TMPDIR_TEST/export.xml"
EXPORT_TXT="$TMPDIR_TEST/export.txt"
IMPORT_COLL="$TMPDIR_TEST/imported.mrc"

echo -e "${YELLOW}BookShelf integration test${RESET}"
echo "Workspace: $TMPDIR_TEST"

# ---------------------------------------------------------------------------
# 1. Empty collection
# ---------------------------------------------------------------------------
section "1. Empty collection"

out=$(bs list)
assert_contains "list on empty collection" "$out" "empty"

out=$(bs report)
assert_contains "report on empty collection" "$out" "Total books: 0"

# ---------------------------------------------------------------------------
# 2. Add books
# ---------------------------------------------------------------------------
section "2. Add books"

out=$(bs add "The Great Gatsby" "Fitzgerald, F. Scott" \
    --isbn 978-0743273565 \
    --publisher Scribner \
    --year 1925 \
    --subjects "American fiction;Jazz Age" \
    --notes "A classic novel" \
    --location "Shelf A-1")
assert_contains "add book 0" "$out" "Added book #0"

out=$(bs add "Moby Dick" "Melville, Herman" \
    --isbn 978-0142437247 \
    --publisher "Penguin Classics" \
    --year 1851 \
    --subjects "Sea stories;Whales" \
    --location "Shelf A-2")
assert_contains "add book 1" "$out" "Added book #1"

out=$(bs add "1984" "Orwell, George" \
    --isbn 978-0451524935 \
    --publisher "Signet Classic" \
    --year 1949 \
    --subjects "Dystopia;Totalitarianism;Politics")
assert_contains "add book 2" "$out" "Added book #2"

# ---------------------------------------------------------------------------
# 3. List
# ---------------------------------------------------------------------------
section "3. List"

out=$(bs list)
assert_contains "list shows total 3"         "$out" "3 total"
assert_contains "list shows Great Gatsby"    "$out" "Great Gatsby"
assert_contains "list shows Moby Dick"       "$out" "Moby Dick"
assert_contains "list shows 1984"            "$out" "1984"
assert_contains "list shows Fitzgerald"      "$out" "Fitzgerald"
assert_contains "list shows ISBN"            "$out" "9780743273565"

# ---------------------------------------------------------------------------
# 4. Show
# ---------------------------------------------------------------------------
section "4. Show"

out=$(bs show 0)
assert_contains "show title"     "$out" "Great Gatsby"
assert_contains "show author"    "$out" "Fitzgerald"
assert_contains "show isbn"      "$out" "9780743273565"
assert_contains "show publisher" "$out" "Scribner"
assert_contains "show year"      "$out" "1925"
assert_contains "show subject"   "$out" "American fiction"
assert_contains "show note"      "$out" "classic novel"
assert_contains "show location"  "$out" "Shelf A-1"
assert_contains "show raw 245"   "$out" "=245"
assert_contains "show raw 100"   "$out" "=100"
assert_contains "show raw 008"   "$out" "=008"

out=$(bs show 1)
assert_contains "show Moby Dick" "$out" "Moby Dick"
assert_contains "show Melville"  "$out" "Melville"

# show out of range should fail
if bs show 99 >/dev/null 2>&1; then
    fail "show out-of-range should exit non-zero"
else
    pass "show out-of-range exits non-zero"
fi

# ---------------------------------------------------------------------------
# 5. Edit
# ---------------------------------------------------------------------------
section "5. Edit"

out=$(bs edit 2 --title "Nineteen Eighty-Four")
assert_contains "edit title returns confirmation" "$out" "Updated book #2"

out=$(bs show 2)
assert_contains "edited title visible in show" "$out" "Nineteen Eighty-Four"

out=$(bs edit 2 --author "Orwell, Eric Arthur Blair (George)")
out=$(bs show 2)
assert_contains "edited author" "$out" "Eric Arthur Blair"

out=$(bs edit 2 --isbn 9990001112223)
out=$(bs show 2)
assert_contains "edited isbn" "$out" "9990001112223"

out=$(bs edit 2 --publisher "Secker and Warburg")
out=$(bs show 2)
assert_contains "edited publisher" "$out" "Secker and Warburg"

out=$(bs edit 2 --year 1948)
out=$(bs show 2)
assert_contains "edited year" "$out" "1948"

out=$(bs edit 2 --notes "Orwell's most famous dystopia")
out=$(bs show 2)
assert_contains "added note" "$out" "famous dystopia"

out=$(bs edit 2 --location "Shelf B-7")
out=$(bs show 2)
assert_contains "edited location" "$out" "Shelf B-7"

# edit out of range should fail
if bs edit 99 --title "Ghost" >/dev/null 2>&1; then
    fail "edit out-of-range should exit non-zero"
else
    pass "edit out-of-range exits non-zero"
fi

# ---------------------------------------------------------------------------
# 6. Search
# ---------------------------------------------------------------------------
section "6. Search"

out=$(bs search fitzgerald)
assert_contains "search by author name"    "$out" "1 result"
assert_contains "search result title"      "$out" "Great Gatsby"

out=$(bs search melville)
assert_contains "search Melville"          "$out" "1 result"

out=$(bs search "eighty")
assert_contains "search edited title"      "$out" "1 result"
assert_contains "search edited title book" "$out" "Nineteen Eighty-Four"

out=$(bs search "nonexistent_xyzzy_12345")
assert_contains "search no results"        "$out" "No results"

# field-targeted search
out=$(bs search "Great Gatsby" --field 245)
assert_contains "search field 245 found"   "$out" "1 result"

out=$(bs search "fitzgerald" --field 100)
assert_contains "search field 100 found"   "$out" "1 result"

out=$(bs search "fitzgerald" --field 650)
assert_contains "search field 650 not found" "$out" "No results"

out=$(bs search "whales" --field 650)
assert_contains "search subject term"      "$out" "1 result"

# ---------------------------------------------------------------------------
# 7. Report
# ---------------------------------------------------------------------------
section "7. Report"

out=$(bs report)
assert_contains "report total"      "$out" "Total books: 3"
assert_contains "report author"     "$out" "Fitzgerald"
assert_contains "report subject"    "$out" "American fiction"
assert_contains "report year 1851"  "$out" "1851"
assert_contains "report year 1925"  "$out" "1925"
assert_contains "report publisher"  "$out" "Scribner"

# ---------------------------------------------------------------------------
# 8. Export — JSON
# ---------------------------------------------------------------------------
section "8. Export — JSON"

out=$(bs export json "$EXPORT_JSON")
assert_contains "export json confirmation" "$out" "Exported 3"
assert_file_exists "json file created" "$EXPORT_JSON"

# Validate JSON structure with Python (via a temp script to avoid quoting issues)
cat > "$TMPDIR_TEST/check_json.py" << 'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
assert isinstance(data, list), "not a list"
assert len(data) == 3, f"expected 3 records, got {len(data)}"
assert "leader" in data[0], "no leader"
assert "fields" in data[0], "no fields"
tags = []
for entry in data[0]["fields"]:
    tags.extend(entry.keys())
assert "245" in tags, f"245 not found in tags: {tags}"
print("ok")
PYEOF
python_check=$(uv run python "$TMPDIR_TEST/check_json.py" "$EXPORT_JSON" 2>&1)
assert_contains "json structure valid" "$python_check" "ok"

# ---------------------------------------------------------------------------
# 9. Export — XML
# ---------------------------------------------------------------------------
section "9. Export — XML"

out=$(bs export xml "$EXPORT_XML")
assert_contains "export xml confirmation" "$out" "Exported 3"
assert_file_exists "xml file created" "$EXPORT_XML"

assert_file_contains "xml has collection element"  "$EXPORT_XML" "<collection"
assert_file_contains "xml has record element"      "$EXPORT_XML" "<record"
assert_file_contains "xml has datafield"           "$EXPORT_XML" "datafield"
assert_file_contains "xml has 245 tag"             "$EXPORT_XML" '"245"'

# ---------------------------------------------------------------------------
# 10. Export — text
# ---------------------------------------------------------------------------
section "10. Export — text (MARCMaker)"

out=$(bs export text "$EXPORT_TXT")
assert_contains "export text confirmation" "$out" "Exported 3"
assert_file_exists "text file created" "$EXPORT_TXT"

assert_file_contains "text has =245"  "$EXPORT_TXT" "=245"
assert_file_contains "text has =100"  "$EXPORT_TXT" "=100"
assert_file_contains "text has title" "$EXPORT_TXT" "Great Gatsby"

# ---------------------------------------------------------------------------
# 11. Delete
# ---------------------------------------------------------------------------
section "11. Delete"

out=$(bs delete 2)
assert_contains "delete confirmation" "$out" "Deleted book #2"

out=$(bs list)
assert_contains "list after delete shows 2 total" "$out" "2 total"
assert_not_contains "deleted book gone from list"  "$out" "Nineteen Eighty-Four"

# delete out of range
if bs delete 99 >/dev/null 2>&1; then
    fail "delete out-of-range should exit non-zero"
else
    pass "delete out-of-range exits non-zero"
fi

# ---------------------------------------------------------------------------
# 12. Import — MARC21
# ---------------------------------------------------------------------------
section "12. Import — MARC21"

# The JSON export we made earlier had 3 books; re-import the MARC backup
# First create a fresh 2-book source
SRC_COLL="$TMPDIR_TEST/src.mrc"
uv run python -m sample_app -c "$SRC_COLL" add "Import Book A" "Author A" --year 2001 >/dev/null
uv run python -m sample_app -c "$SRC_COLL" add "Import Book B" "Author B" --year 2002 >/dev/null

out=$(uv run python -m sample_app -c "$IMPORT_COLL" import marc "$SRC_COLL")
assert_contains "import marc confirmation" "$out" "Imported 2"

out=$(uv run python -m sample_app -c "$IMPORT_COLL" list)
assert_contains "import marc result count" "$out" "2 total"
assert_contains "import marc book A"       "$out" "Import Book A"
assert_contains "import marc book B"       "$out" "Import Book B"

# import missing file should fail
if uv run python -m sample_app -c "$IMPORT_COLL" import marc /no/such/file.mrc >/dev/null 2>&1; then
    fail "import missing file should exit non-zero"
else
    pass "import missing file exits non-zero"
fi

# ---------------------------------------------------------------------------
# 13. Import — MARCXML (round-trip through the XML export)
# ---------------------------------------------------------------------------
section "13. Import — MARCXML"

XML_IMPORT_COLL="$TMPDIR_TEST/xml_import.mrc"
out=$(uv run python -m sample_app -c "$XML_IMPORT_COLL" import xml "$EXPORT_XML")
assert_contains "import xml confirmation" "$out" "Imported 3"

out=$(uv run python -m sample_app -c "$XML_IMPORT_COLL" list)
assert_contains "xml import result count" "$out" "3 total"
assert_contains "xml import Great Gatsby" "$out" "Great Gatsby"
assert_contains "xml import Moby Dick"    "$out" "Moby Dick"

# ---------------------------------------------------------------------------
# 14. Library of Congress — loc-search (live network)
# ---------------------------------------------------------------------------
section "14. Library of Congress — loc-search (live)"

echo "  Querying LOC for 'moby dick'..."
out=$(bs loc-search "moby dick" --max 5 2>&1) || true

if echo "$out" | grep -qi "error\|failed\|connection"; then
    echo -e "  ${YELLOW}SKIP${RESET}  loc-search (network unavailable: $out)"
else
    assert_contains "loc-search returns results header" "$out" "Library of Congress results"
    # At least one result line should have a title
    if echo "$out" | grep -qiE "(moby|melville|whale)"; then
        pass "loc-search results contain expected title/author"
    else
        fail "loc-search results do not contain 'moby', 'melville', or 'whale'"
        echo "       Output: $out"
    fi
fi

# Helper: detect any network-layer failure in command output
net_error() { echo "$1" | grep -qi "error\|failed\|connection\|timed out\|forbidden\|certificate\|could not retrieve"; }

# ---------------------------------------------------------------------------
# 15. Library of Congress — loc-fetch (live network)
# ---------------------------------------------------------------------------
section "15. Library of Congress — loc-fetch (live)"

# LCCN 2002727588 = Moby-Dick, Penguin Classics 2002 edition
# This is a stable, well-known record unlikely to disappear from LOC.
LCCN="2002727588"
echo "  Fetching LCCN $LCCN from LOC..."
out=$(bs loc-fetch "$LCCN" --show 2>&1) || true

if net_error "$out"; then
    echo -e "  ${YELLOW}SKIP${RESET}  loc-fetch (network unavailable)"
    echo "         Reason: $(echo "$out" | head -1)"
else
    assert_contains "loc-fetch fetched message"    "$out" "Fetched:"
    assert_contains "loc-fetch added message"      "$out" "Added to collection"
    if echo "$out" | grep -qiE "(moby|melville)"; then
        pass "loc-fetch record title/author correct"
    else
        fail "loc-fetch result does not mention 'moby' or 'melville'"
        echo "       Output: $out"
    fi
    # --show should print raw MARC fields
    assert_contains "loc-fetch --show prints fields" "$out" "=245"

    # The fetched record should now be in the collection
    list_out=$(bs list)
    if echo "$list_out" | grep -qiE "(moby|melville)"; then
        pass "loc-fetched record appears in collection"
    else
        fail "loc-fetched record not found in collection list"
        echo "       List output: $list_out"
    fi
fi

# ---------------------------------------------------------------------------
# 16. loc-fetch --no-add: record is NOT added
# ---------------------------------------------------------------------------
section "16. loc-fetch --no-add (live)"

BEFORE_COUNT=$(bs list 2>/dev/null | grep -oP '\d+ total' | grep -oP '\d+' || echo "0")
echo "  Collection size before: $BEFORE_COUNT"

out=$(bs loc-fetch "$LCCN" --no-add 2>&1) || true

if net_error "$out"; then
    echo -e "  ${YELLOW}SKIP${RESET}  loc-fetch --no-add (network unavailable)"
    echo "         Reason: $(echo "$out" | head -1)"
else
    assert_contains "loc-fetch --no-add prints not-added message" "$out" "Not added"

    AFTER_COUNT=$(bs list 2>/dev/null | grep -oP '\d+ total' | grep -oP '\d+' || echo "0")
    if [ "$BEFORE_COUNT" = "$AFTER_COUNT" ]; then
        pass "loc-fetch --no-add did not change collection size"
    else
        fail "loc-fetch --no-add changed collection size from $BEFORE_COUNT to $AFTER_COUNT"
    fi
fi

# ---------------------------------------------------------------------------
# 17. Multiple collections independence
# ---------------------------------------------------------------------------
section "17. Multiple collections"

COLL_A="$TMPDIR_TEST/coll_a.mrc"
COLL_B="$TMPDIR_TEST/coll_b.mrc"

uv run python -m sample_app -c "$COLL_A" add "Only In A" "Author A" >/dev/null
uv run python -m sample_app -c "$COLL_B" add "Only In B" "Author B" >/dev/null

out_a=$(uv run python -m sample_app -c "$COLL_A" list)
out_b=$(uv run python -m sample_app -c "$COLL_B" list)

assert_contains     "coll A has its book"    "$out_a" "Only In A"
assert_not_contains "coll A lacks B's book"  "$out_a" "Only In B"
assert_contains     "coll B has its book"    "$out_b" "Only In B"
assert_not_contains "coll B lacks A's book"  "$out_b" "Only In A"

# Merge B into A
uv run python -m sample_app -c "$COLL_A" import marc "$COLL_B" >/dev/null
out_merged=$(uv run python -m sample_app -c "$COLL_A" list)
assert_contains "merged A has both books"   "$out_merged" "Only In A"
assert_contains "merged A has B's book"     "$out_merged" "Only In B"

# ---------------------------------------------------------------------------
# 18. Persistence: records survive process restart
# ---------------------------------------------------------------------------
section "18. Persistence"

PERSIST_COLL="$TMPDIR_TEST/persist.mrc"
uv run python -m sample_app -c "$PERSIST_COLL" add "Persisted Book" "Persist Author" >/dev/null

# Read it back in a fresh invocation
out=$(uv run python -m sample_app -c "$PERSIST_COLL" show 0)
assert_contains "persisted title readable" "$out" "Persisted Book"
assert_contains "persisted author readable" "$out" "Persist Author"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All $TOTAL tests passed.${RESET}"
else
    echo -e "${RED}$FAIL of $TOTAL tests FAILED. $PASS passed.${RESET}"
fi
echo "========================================"

[ "$FAIL" -eq 0 ]
