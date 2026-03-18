"""Tests for the Library of Congress integration.

Network tests are marked with @pytest.mark.network and skipped by default.
Unit tests use mocks.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from rmarc import record_to_xml
from sample_app.loc import (
    build_lccn_permalink_url,
    build_sru_url,
    fetch_marc_by_lccn,
    fetch_marcxml_by_lccn,
    normalize_lccn,
    search_loc,
)
from sample_app.store import make_record


class TestSearchLocMocked:
    """Test search_loc with mocked HTTP responses."""

    def _mock_response(self, data: dict) -> MagicMock:
        mock = MagicMock()
        mock.read.return_value = json.dumps(data).encode("utf-8")
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_search_returns_results(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(
            {
                "results": [
                    {
                        "title": "Test Book",
                        "contributor": ["Author A"],
                        "date": "2020",
                        "number": ["lccn 2020123456"],
                        "url": "https://example.com/book",
                    },
                ]
            }
        )

        results = search_loc("test")
        assert len(results) == 1
        assert results[0]["title"] == "Test Book"
        assert results[0]["author"] == "Author A"
        assert results[0]["lccn"] == "2020123456"

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_search_empty_results(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response({"results": []})
        results = search_loc("nonexistent")
        assert results == []

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_search_no_contributor(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(
            {"results": [{"title": "Anonymous", "date": "2000", "number": [], "url": ""}]}
        )
        results = search_loc("test")
        assert results[0]["author"] == ""

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_search_connection_error(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("fail")
        with pytest.raises(ConnectionError):
            search_loc("test")


class TestFetchMarcMocked:
    """Test fetch_marc_by_lccn with mocked HTTP responses."""

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_fetch_valid_marc(self, mock_urlopen):
        # Create a real MARC record and serialize it as MARCXML
        rec = make_record(title="Fetched Book", author="LOC Author", isbn="999")
        marcxml_bytes = record_to_xml(rec, namespace=True)

        mock_resp = MagicMock()
        mock_resp.read.return_value = marcxml_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_marc_by_lccn("2020123456")
        assert result is not None
        assert "Fetched Book" in result.title

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_fetch_marcxml_falls_back_to_sru(self, mock_urlopen):
        import urllib.error

        rec = make_record(title="Fallback Book", author="LOC Author", isbn="999")
        marcxml_bytes = record_to_xml(rec, namespace=True)

        mock_resp = MagicMock()
        mock_resp.read.return_value = marcxml_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.side_effect = [urllib.error.HTTPError("x", 404, "not found", {}, None), mock_resp]

        result = fetch_marcxml_by_lccn("94-237181")
        assert b"Fallback Book" in result

    @patch("sample_app.loc.urllib.request.urlopen")
    def test_fetch_connection_error(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        with pytest.raises(ConnectionError):
            fetch_marc_by_lccn("bad")


class TestLocUrlHelpers:
    """Test URL and identifier helpers for LoC endpoints."""

    def test_normalize_lccn_pre_2001(self):
        assert normalize_lccn("94-237181") == "94237181"

    def test_normalize_lccn_post_2000(self):
        assert normalize_lccn("2001-1114") == "2001001114"

    def test_build_permalink_url(self):
        assert build_lccn_permalink_url("94-237181", "marcxml") == "https://lccn.loc.gov/94237181/marcxml"

    def test_build_sru_url(self):
        url = build_sru_url("94-237181")
        assert "bath.lccn%3D94237181" in url
        assert "recordSchema=marcxml" in url


class TestLocCliMocked:
    """Test the CLI loc-search and loc-fetch commands with mocks."""

    @patch("sample_app.cli.search_loc")
    def test_loc_search_cli(self, mock_search, tmp_path, capsys):
        mock_search.return_value = [
            {"title": "CLI Result", "author": "Someone", "date": "2021", "lccn": "123", "url": ""},
        ]
        from sample_app.cli import main

        main(["-c", str(tmp_path / "t.mrc"), "loc-search", "test"])
        out = capsys.readouterr().out
        assert "CLI Result" in out

    @patch("sample_app.cli.fetch_marc_by_lccn")
    def test_loc_fetch_cli_show_no_add(self, mock_fetch, tmp_path, capsys):
        rec = make_record(title="LOC Book", author="LOC Author")
        mock_fetch.return_value = rec
        from sample_app.cli import main

        main(["-c", str(tmp_path / "t.mrc"), "loc-fetch", "123", "--show", "--no-add"])
        out = capsys.readouterr().out
        assert "LOC Book" in out
        assert "Not added" in out

    @patch("sample_app.cli.fetch_marc_by_lccn")
    def test_loc_fetch_cli_add(self, mock_fetch, tmp_path, capsys):
        rec = make_record(title="Added From LOC", author="LOC Author")
        mock_fetch.return_value = rec
        from sample_app.cli import main

        coll_path = str(tmp_path / "t.mrc")
        main(["-c", coll_path, "loc-fetch", "123"])
        out = capsys.readouterr().out
        assert "Added to collection" in out

    @patch("sample_app.cli.fetch_marc_by_lccn")
    def test_loc_fetch_cli_not_found(self, mock_fetch, tmp_path):
        mock_fetch.return_value = None
        from sample_app.cli import main

        with pytest.raises(SystemExit):
            main(["-c", str(tmp_path / "t.mrc"), "loc-fetch", "bad"])

    @patch("sample_app.cli.search_loc")
    def test_loc_search_cli_error(self, mock_search, tmp_path):
        mock_search.side_effect = ConnectionError("fail")
        from sample_app.cli import main

        with pytest.raises(SystemExit):
            main(["-c", str(tmp_path / "t.mrc"), "loc-search", "test"])
