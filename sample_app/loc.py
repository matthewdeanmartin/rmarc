"""Fetch MARC records from the Library of Congress."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO

from rmarc import Record, parse_xml_to_array

LOC_SRU_BASE = "https://lx2.loc.gov/sru/LCDB"
LOC_SEARCH_BASE = "https://www.loc.gov/search/"
LOC_LCCN_BASE = "https://lccn.loc.gov"


def search_loc(query: str, max_results: int = 5) -> list[dict]:
    """Search the Library of Congress and return brief result dicts.

    Uses the loc.gov JSON search API.
    Returns a list of dicts with keys: title, author, date, lccn, url.
    """
    params = urllib.parse.urlencode(
        {
            "q": query,
            "fo": "json",
            "c": str(max_results),
            "fa": "original-format:book",
        }
    )
    url = f"{LOC_SEARCH_BASE}?{params}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        raise ConnectionError(f"Failed to search Library of Congress: {e}") from e

    results = []
    for item in data.get("results", []):
        lccn = ""
        ids = item.get("number", [])
        for ident in ids if isinstance(ids, list) else []:
            if isinstance(ident, str) and ident.startswith("lccn"):
                lccn = ident.replace("lccn ", "").strip()
                break

        results.append(
            {
                "title": item.get("title", "Unknown"),
                "author": ", ".join(item.get("contributor", [])) if item.get("contributor") else "",
                "date": item.get("date", ""),
                "lccn": lccn,
                "url": item.get("url", ""),
            }
        )
    return results


def normalize_lccn(lccn: str) -> str:
    """Normalize an LCCN to the Library of Congress permalink form."""
    compact = re.sub(r"\s+", "", lccn)
    match = re.fullmatch(r"(?P<prefix>[A-Za-z]{0,3})(?P<year>\d{2}|\d{4})-?(?P<serial>\d{1,6})", compact)
    if match is None:
        return compact.replace("-", "").lower()

    prefix = match.group("prefix").lower()
    year = match.group("year")
    serial = match.group("serial")
    return f"{prefix}{year}{serial.zfill(6)}"


def build_lccn_permalink_url(lccn: str, qualifier: str = "") -> str:
    """Build an LCCN permalink URL, optionally with an XML format qualifier."""
    normalized = normalize_lccn(lccn)
    suffix = f"/{qualifier}" if qualifier else ""
    return f"{LOC_LCCN_BASE}/{normalized}{suffix}"


def build_sru_url(lccn: str, record_schema: str = "marcxml", maximum_records: int = 1) -> str:
    """Build an official LC SRU URL for an LCCN search."""
    params = urllib.parse.urlencode(
        {
            "operation": "searchRetrieve",
            "version": "1.1",
            "query": f"bath.lccn={normalize_lccn(lccn)}",
            "maximumRecords": str(maximum_records),
            "recordSchema": record_schema,
        }
    )
    return f"{LOC_SRU_BASE}?{params}"


def _read_url(url: str, *, accept: str | None = None) -> bytes:
    headers = {"Accept": accept} if accept else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def fetch_marcxml_by_lccn(lccn: str) -> bytes:
    """Fetch MARCXML from Library of Congress using documented public endpoints.

    The first attempt uses the documented LCCN permalink `/marcxml` qualifier.
    If that fails, this falls back to the LC SRU endpoint with
    `recordSchema=marcxml`.
    """
    urls = [
        build_lccn_permalink_url(lccn, "marcxml"),
        build_sru_url(lccn, record_schema="marcxml"),
    ]
    last_error: Exception | None = None
    for url in urls:
        try:
            return _read_url(url, accept="application/xml, text/xml;q=0.9, */*;q=0.1")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last_error = exc

    raise ConnectionError(f"Failed to fetch MARCXML record for LCCN {lccn}: {last_error}") from last_error


def fetch_marc_by_lccn(lccn: str) -> Record | None:
    """Fetch an LC MARC record by LCCN and parse it into an ``rmarc.Record``."""
    try:
        xml_bytes = fetch_marcxml_by_lccn(lccn)
    except ConnectionError as e:
        raise ConnectionError(f"Failed to fetch MARC record for LCCN {lccn}: {e}") from e

    records = parse_xml_to_array(BytesIO(xml_bytes))
    if not records:
        return None
    return records[0]
