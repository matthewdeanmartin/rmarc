"""Cross-check every entry in the Python MARC-8 mapping tables against Rust.

Strategy
--------
For each codeset and each (marc8_key → unicode_codepoint, cflag) entry in the
Python tables we:

  1. Synthesise the minimal MARC-8 byte sequence that exercises exactly that
     entry (escape to the right codeset, then the key bytes).
  2. Run it through the *pure-Python* converter (MARC8ToUnicode.translate).
  3. Run it through the *Rust* converter (marc8_to_unicode_rs).
  4. Assert both produce the same NFC string.

This catches transcription errors in either direction — a mistyped codepoint
in the Python table will cause the Python path to diverge, and a mistyped
value in the Rust table will cause the Rust path to diverge.

ODD_MAP entries are checked the same way: synthesise a 3-byte key, confirm
Python and Rust agree on the output character.

Codeset notes
-------------
* 0x31  – CJK multibyte: keys are 3-byte big-endian integers.
          Escape sequence: ESC $ 1  (0x1B 0x24 0x31)
* 0x42  – Basic Latin (ASCII): byte values are plain ASCII, no escape needed.
* 0x45  – ANSEL (default G1): bytes 0x80–0xFF are accessed via the G1 slot
          when the byte value is > 0x80; bytes ≤ 0x80 need G0 = 0x45.
* All other codesets: escape G0 to the charset byte then emit the key byte.
  ANSEL bytes > 0x80 live in G1 by default, but we force G0 = charset for
  simplicity (the converter looks up G1 when code_point > 0x80 and not CJK,
  so we switch G1 instead for those entries).
"""

import unicodedata
import unittest
from typing import Callable

from rmarc._rmarc import marc8_to_unicode_rs
from rmarc.marc8 import _marc8_to_unicode_python
from rmarc.marc8_mapping import CODESETS, ODD_MAP

ESC = b"\x1b"

# Charset IDs that use multi-byte (3-byte) keys.
MULTIBYTE_CHARSETS = {0x31}

# Charset IDs whose non-ASCII bytes live in G1 by default (ANSEL = 0x45).
# For G1 codesets bytes > 0x80 are looked up in G1, so we route them there.
G1_DEFAULT_CHARSET = 0x45

# CHARSET_42 contains a handful of control-byte entries (0x1B ESC, 0x1D–0x1F)
# that the converter intentionally drops (code_point < 0x20 → skip).  There is
# nothing to compare: both converters swallow them silently.  Skip them rather
# than crashing trying to synthesise an input that triggers that code path.
SKIP_KEYS: dict[int, set[int]] = {
    0x42: {0x1B, 0x1D, 0x1E, 0x1F},
}


def _make_input_single(charset_id: int, marc8_byte: int) -> bytes:
    """Return a MARC-8 byte string that will exercise one single-byte entry.

    For G0 codesets we emit:  ESC ( <charset_id> <marc8_byte>
    For entries with byte > 0x80 in the default G1 charset (ANSEL) we rely on
    the default G1 = 0x45 and just emit the raw byte — no escape needed.
    For non-ANSEL codesets we need to switch G0 and emit the byte.  Because
    the Python converter routes bytes > 0x80 through G1 we switch G1 instead:
    ESC ) <charset_id> <marc8_byte>
    """
    b = bytes([marc8_byte])

    if charset_id == G1_DEFAULT_CHARSET and marc8_byte > 0x80:
        # ANSEL G1 is the default — just emit the raw byte.
        return b

    if marc8_byte > 0x80:
        # Non-ANSEL G1: switch G1 to this charset then emit the byte.
        return ESC + b")" + bytes([charset_id]) + b
    else:
        # G0: switch G0 to this charset then emit the byte.
        return ESC + b"(" + bytes([charset_id]) + b


def _make_input_multibyte(marc8_key: int) -> bytes:
    """Return the MARC-8 escape+3-byte sequence for a CJK entry."""
    b0 = (marc8_key >> 16) & 0xFF
    b1 = (marc8_key >> 8) & 0xFF
    b2 = marc8_key & 0xFF
    # ESC $ 1 switches G0 to CJK multibyte (0x31)
    return ESC + b"$1" + bytes([b0, b1, b2])


def _expected_char(unicode_cp: int, cflag: int) -> str:
    """Return the NFC-normalised string we expect from a single mapping entry.

    Combining characters (cflag=1) appear *before* the base in MARC-8.  The
    converters accumulate them and attach them to the next non-combining char.
    To test a combining entry in isolation we append a space as the base so
    both converters have something to attach the combining mark to, then
    we strip the space from the expected result for comparison purposes.

    Non-combining entries produce just the single character.
    """
    ch = chr(unicode_cp)
    if cflag:
        # combining + space → NFC → combining attached to space; we return the
        # raw combining character so callers can adjust their expectations.
        return ch
    return unicodedata.normalize("NFC", ch)


class _ConverterPair:
    """Thin wrapper so tests can call both converters the same way."""

    def __init__(self, name: str, fn: Callable[[bytes], str]) -> None:
        self.name = name
        self.fn = fn

    def convert(self, data: bytes) -> str:
        return self.fn(data)


_PYTHON = _ConverterPair("Python", lambda b: _marc8_to_unicode_python(b, hide_utf8_warnings=True))
_RUST = _ConverterPair("Rust", lambda b: marc8_to_unicode_rs(b, True))


class TestMappingPythonVsRust(unittest.TestCase):
    """Each test method covers one codeset; failures name the exact key."""

    def _check_codeset(self, charset_id: int) -> None:
        charset = CODESETS[charset_id]
        is_mb = charset_id in MULTIBYTE_CHARSETS
        mismatches: list[str] = []

        skip = SKIP_KEYS.get(charset_id, set())
        for marc8_key, (unicode_cp, cflag) in sorted(charset.items()):
            if marc8_key in skip:
                continue
            if is_mb:
                data = _make_input_multibyte(marc8_key)
            else:
                data = _make_input_single(charset_id, marc8_key)

            # For combining marks we need a base character so the converters
            # can emit something.  Append ASCII 'x' as the base.
            if cflag:
                data = data + b"x"

            py_result = _PYTHON.convert(data)
            rs_result = _RUST.convert(data)

            if py_result != rs_result:
                key_hex = f"0x{marc8_key:X}"
                cp_hex = f"U+{unicode_cp:04X}"
                mismatches.append(
                    f"  charset=0x{charset_id:02X} key={key_hex} cp={cp_hex} cflag={cflag}"
                    f"\n    Python → {py_result!r}"
                    f"\n    Rust   → {rs_result!r}"
                )

        if mismatches:
            joined = "\n".join(mismatches)
            self.fail(f"Charset 0x{charset_id:02X}: {len(mismatches)} mismatch(es):\n{joined}")

    # ── One test per codeset ──────────────────────────────────────────────────

    def test_charset_31_cjk(self) -> None:
        self._check_codeset(0x31)

    def test_charset_32_basic_hebrew(self) -> None:
        self._check_codeset(0x32)

    def test_charset_33_basic_arabic(self) -> None:
        self._check_codeset(0x33)

    def test_charset_34_extended_arabic(self) -> None:
        self._check_codeset(0x34)

    def test_charset_42_basic_latin(self) -> None:
        self._check_codeset(0x42)

    def test_charset_45_ansel(self) -> None:
        self._check_codeset(0x45)

    def test_charset_4e_basic_cyrillic(self) -> None:
        self._check_codeset(0x4E)

    def test_charset_51_extended_cyrillic(self) -> None:
        self._check_codeset(0x51)

    def test_charset_53_basic_greek(self) -> None:
        self._check_codeset(0x53)

    def test_charset_62_subscripts(self) -> None:
        self._check_codeset(0x62)

    def test_charset_67_greek_symbols(self) -> None:
        self._check_codeset(0x67)

    def test_charset_70_superscripts(self) -> None:
        self._check_codeset(0x70)

    # ── ODD_MAP ───────────────────────────────────────────────────────────────

    def test_odd_map(self) -> None:
        """Every ODD_MAP entry: Python and Rust must agree."""
        mismatches: list[str] = []

        for marc8_key, unicode_cp in sorted(ODD_MAP.items()):
            # ODD_MAP keys are 3-byte integers; synthesise as CJK multibyte
            # so both converters will compute the same 3-byte code_point and
            # hit the ODD_MAP branch.  We switch to multibyte mode first.
            data = _make_input_multibyte(marc8_key)

            py_result = _PYTHON.convert(data)
            rs_result = _RUST.convert(data)

            if py_result != rs_result:
                key_hex = f"0x{marc8_key:X}"
                cp_hex = f"U+{unicode_cp:04X}"
                mismatches.append(
                    f"  ODD_MAP key={key_hex} cp={cp_hex}\n    Python → {py_result!r}\n    Rust   → {rs_result!r}"
                )

        if mismatches:
            joined = "\n".join(mismatches)
            self.fail(f"ODD_MAP: {len(mismatches)} mismatch(es):\n{joined}")

    # ── Symmetric two-way spot-checks ─────────────────────────────────────────
    # These verify that neither implementation silently ignores entries that the
    # other does have, by asserting on a known expected value rather than just
    # comparing the two sides to each other.

    def test_two_way_ansel_combining_acute(self) -> None:
        """ANSEL 0xE2 = combining acute; with base 'e' → é (U+00E9) in both."""
        data = b"\xe2e"
        expected = "\u00e9"  # é
        self.assertEqual(_PYTHON.convert(data), expected, "Python ANSEL combining acute")
        self.assertEqual(_RUST.convert(data), expected, "Rust ANSEL combining acute")

    def test_two_way_ansel_polish_l(self) -> None:
        """ANSEL 0xA1 = Ł (U+0141)."""
        data = b"\xa1"
        expected = "\u0141"
        self.assertEqual(_PYTHON.convert(data), expected, "Python Ł")
        self.assertEqual(_RUST.convert(data), expected, "Rust Ł")

    def test_two_way_cjk_ideograph(self) -> None:
        """CJK 0x213021 = 一 (U+4E00)."""
        data = b"\x1b$1\x21\x30\x21"
        expected = "\u4e00"
        self.assertEqual(_PYTHON.convert(data), expected, "Python CJK 一")
        self.assertEqual(_RUST.convert(data), expected, "Rust CJK 一")

    def test_two_way_greek_alpha(self) -> None:
        """Greek charset (0x53) 0x41 = Α (U+0391)."""
        data = b"\x1b(SA"
        expected = "\u0391"
        self.assertEqual(_PYTHON.convert(data), expected, "Python Greek Alpha")
        self.assertEqual(_RUST.convert(data), expected, "Rust Greek Alpha")

    def test_two_way_cyrillic_a(self) -> None:
        """Cyrillic charset (0x4E) 0x61 = А (U+0410)."""
        data = b"\x1b(Na"
        expected = "\u0410"
        self.assertEqual(_PYTHON.convert(data), expected, "Python Cyrillic А")
        self.assertEqual(_RUST.convert(data), expected, "Rust Cyrillic А")


if __name__ == "__main__":
    unittest.main()
