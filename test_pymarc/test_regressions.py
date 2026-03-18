"""Regression tests for reviewed compatibility and panic-safety issues."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import rmarc
from rmarc._rmarc import decode_marc_raw, encode_marc_raw
from rmarc.marc8 import _marc8_to_unicode_python


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


class ImportFallbackRegressionTest(unittest.TestCase):
    def test_package_import_succeeds_without_rust_extension(self) -> None:
        python_root = _repo_root() / "python"
        script = textwrap.dedent(
            f"""
            import importlib.abc
            import sys

            class BlockRustExtension(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "rmarc._rmarc":
                        raise ImportError("blocked for test")
                    return None

            sys.meta_path.insert(0, BlockRustExtension())
            sys.path.insert(0, r"{python_root}")

            import rmarc

            assert hasattr(rmarc, "Record")
            assert hasattr(rmarc, "MARCReader")
            print("imported")
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=_repo_root(),
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("imported", result.stdout)


class RustCodecSafetyRegressionTest(unittest.TestCase):
    def test_decode_marc_raw_rejects_zero_length_field_without_panicking(self) -> None:
        raw = b"00038    a2200037   4500" + b"245000000000" + b"\x1e" + b"\x1d"

        with self.assertRaises(ValueError):
            decode_marc_raw(raw)

    def test_encode_marc_raw_rejects_short_leader_without_panicking(self) -> None:
        with self.assertRaises(ValueError):
            encode_marc_raw("short", [])

    def test_encode_marc_raw_rejects_non_ascii_leader_without_panicking(self) -> None:
        with self.assertRaises(ValueError):
            encode_marc_raw("\u00e9" * 24, [])


class JSONReaderEncodingRegressionTest(unittest.TestCase):
    def test_json_reader_uses_explicit_encoding_for_file_paths(self) -> None:
        payload = json.dumps(
            [
                {
                    "leader": "00000nam a2200000   4500",
                    "fields": [
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [{"a": "Привет"}],
                            }
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        )

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)

        try:
            Path(path).write_bytes(payload.encode("cp1251"))
            record = next(iter(rmarc.JSONReader(path, encoding="cp1251")))
            self.assertEqual(record["245"]["a"], "\u041f\u0440\u0438\u0432\u0435\u0442")
        finally:
            os.remove(path)

    def test_json_reader_uses_explicit_encoding_for_bytes_payload(self) -> None:
        payload = json.dumps(
            [
                {
                    "leader": "00000nam a2200000   4500",
                    "fields": [
                        {
                            "245": {
                                "ind1": "0",
                                "ind2": "0",
                                "subfields": [{"a": "Привет"}],
                            }
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        ).encode("cp1251")

        record = next(iter(rmarc.JSONReader(payload, encoding="cp1251")))
        self.assertEqual(record["245"]["a"], "\u041f\u0440\u0438\u0432\u0435\u0442")


class Marc8WarningRegressionTest(unittest.TestCase):
    def test_python_marc8_fallback_hides_truncated_multibyte_warnings(self) -> None:
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            _marc8_to_unicode_python(b"\x1b$1X", hide_utf8_warnings=True)

        self.assertEqual(stderr.getvalue(), "")

    def test_python_marc8_fallback_emits_warning_when_not_hidden(self) -> None:
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            _marc8_to_unicode_python(b"\x1b$1X", hide_utf8_warnings=False)

        self.assertIn("Multi-byte position", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
