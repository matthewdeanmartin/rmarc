//! MARC-8 to Unicode converter.
//!
//! Port of the Python MARC8ToUnicode.translate() method.
//! Handles escape sequences for codeset switching, multibyte CJK,
//! combining characters, and NFC normalization.

use pyo3::prelude::*;

use crate::marc8_mapping;

const BASIC_LATIN: u8 = 0x42;
const ANSEL: u8 = 0x45;
const ESC: u8 = 0x1B;

/// Convert MARC-8 encoded bytes to a Unicode string.
///
/// This is a direct port of the Python MARC8ToUnicode.translate() method.
/// Returns NFC-normalized Unicode text.
#[pyfunction]
pub fn marc8_to_unicode_rs(data: &[u8], quiet: bool) -> String {
    if data.is_empty() {
        return String::new();
    }

    let mut g0: u8 = BASIC_LATIN;
    let mut g1: u8 = ANSEL;

    let mut uni_list: Vec<char> = Vec::with_capacity(data.len());
    let mut combinings: Vec<char> = Vec::new();
    let mut pos: usize = 0;
    let len = data.len();

    while pos < len {
        // Check for escape sequence
        if data[pos] == ESC {
            if pos + 1 >= len {
                // Incomplete escape at end
                uni_list.push(data[pos] as char);
                pos += 1;
                continue;
            }

            let next_byte = data[pos + 1];

            // G0 designators: ( , $
            if next_byte == b'(' || next_byte == b',' || next_byte == b'$' {
                // G0 set
                if pos + 2 < len {
                    // Check for $, sequence (multibyte)
                    if next_byte == b'$' && pos + 2 < len && data[pos + 2] == b',' {
                        // $, followed by charset byte
                        if pos + 3 < len {
                            g0 = data[pos + 3];
                            pos += 4;
                        } else {
                            pos += 3;
                        }
                        continue;
                    }
                    g0 = data[pos + 2];
                    pos += 3;
                    continue;
                } else {
                    uni_list.push(data[pos] as char);
                    pos += 1;
                    continue;
                }
            }

            // G1 designators: ) - $
            if (next_byte == b')' || next_byte == b'-') && pos + 2 < len {
                g1 = data[pos + 2];
                pos += 3;
                continue;
            }

            // Check for $- sequence (G1 multibyte)
            if next_byte == b'$' && pos + 2 < len && data[pos + 2] == b'-' {
                if pos + 3 < len {
                    g1 = data[pos + 3];
                    pos += 4;
                } else {
                    pos += 3;
                }
                continue;
            }

            // Other escape: check if next byte is a known charset
            let charset = next_byte;
            if marc8_mapping::get_codeset(charset).is_some() {
                g0 = charset;
                pos += 2;
                continue;
            } else if charset == 0x73 {
                // ASCII
                g0 = BASIC_LATIN;
                pos += 2;
                if pos == len {
                    break;
                }
                continue;
            }
            // Unknown escape - fall through to normal processing
        }

        let mb_flag = g0 == 0x31; // CJK multibyte

        let code_point: u32;
        if mb_flag {
            if pos + 3 > len {
                // Not enough bytes for multibyte
                code_point = 32; // space
                if !quiet {
                    eprintln!(
                        "Multi-byte position {} exceeds length of marc8 string {}",
                        pos + 3,
                        len
                    );
                }
            } else {
                code_point = (data[pos] as u32) * 65536
                    + (data[pos + 1] as u32) * 256
                    + (data[pos + 2] as u32);
            }
            pos += 3;
        } else {
            code_point = data[pos] as u32;
            pos += 1;
        }

        // Skip control characters
        if code_point < 0x20 || (code_point > 0x80 && code_point < 0xA0) {
            continue;
        }

        // Look up in codeset
        let lookup_result = if code_point > 0x80 && !mb_flag {
            marc8_mapping::get_codeset(g1).and_then(|cs| cs.get(&code_point))
        } else {
            marc8_mapping::get_codeset(g0).and_then(|cs| cs.get(&code_point))
        };

        let (uni, cflag) = match lookup_result {
            Some(&(u, c)) => (u, c != 0),
            None => {
                // Try ODD_MAP
                if let Some(u) = marc8_mapping::odd_map_lookup(code_point) {
                    if let Some(ch) = char::from_u32(u) {
                        uni_list.push(ch);
                    }
                    continue;
                }
                if !quiet {
                    eprintln!(
                        "Unable to parse character 0x{:x} in g0=0x{:x} g1=0x{:x}",
                        code_point, g0, g1
                    );
                }
                (32u32, false) // space
            }
        };

        if let Some(ch) = char::from_u32(uni) {
            if cflag {
                combinings.push(ch);
            } else {
                uni_list.push(ch);
                if !combinings.is_empty() {
                    uni_list.append(&mut combinings);
                }
            }
        }
    }

    // NFC normalization
    let result: String = uni_list.into_iter().collect();
    unicode_normalization_nfc(&result)
}

/// Simple NFC normalization using the `unicode-normalization` crate pattern.
/// We implement a minimal version that handles the common MARC-8 combining cases.
fn unicode_normalization_nfc(s: &str) -> String {
    // Use the unicode_normalization crate for proper NFC
    use unicode_normalization::UnicodeNormalization;
    s.nfc().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Basic Latin passthrough ───────────────────────────────────────────────

    #[test]
    fn empty_input_returns_empty_string() {
        assert_eq!(marc8_to_unicode_rs(b"", false), "");
    }

    #[test]
    fn ascii_text_passthrough() {
        assert_eq!(marc8_to_unicode_rs(b"hello world", false), "hello world");
    }

    #[test]
    fn digits_and_punctuation_passthrough() {
        assert_eq!(marc8_to_unicode_rs(b"abc 123!", false), "abc 123!");
    }

    // ── Control character filtering ───────────────────────────────────────────

    #[test]
    fn control_chars_below_0x20_are_skipped() {
        // 0x01 is a control character and should be dropped
        let result = marc8_to_unicode_rs(b"\x01abc", false);
        assert_eq!(result, "abc");
    }

    // ── Escape sequence handling ──────────────────────────────────────────────

    #[test]
    fn escape_to_basic_latin_0x73() {
        // ESC 0x73 switches back to Basic Latin (ASCII)
        let input = b"\x1b\x73hello";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "hello");
    }

    #[test]
    fn escape_with_paren_switches_g0() {
        // ESC '(' 'B' designates Basic Latin into G0
        let input = b"\x1b\x28\x42hello";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "hello");
    }

    #[test]
    fn incomplete_escape_at_end_does_not_panic() {
        // ESC at end of input
        let result = marc8_to_unicode_rs(b"hi\x1b", false);
        // Should not panic; ESC may or may not appear in output but no crash
        let _ = result;
    }

    // ── ANSEL combining characters ────────────────────────────────────────────

    #[test]
    fn ansel_combining_acute_on_e() {
        // In ANSEL (G1), bytes >0x80 are combining marks or precomposed chars.
        // 0xE2 is "combining acute accent" and 0x65 is 'e' in Basic Latin.
        // MARC-8 puts the combining mark BEFORE the base character.
        // Result should NFC-normalize to U+00E9 (é).
        let input = b"\xe2\x65"; // combining acute + 'e'
        let result = marc8_to_unicode_rs(input, false);
        // After NFC, this should be é (U+00E9)
        assert!(
            result.contains('\u{00e9}') || result.contains('\u{0301}'),
            "Expected combining accent result, got: {:?}",
            result
        );
    }

    // ── Quiet mode ────────────────────────────────────────────────────────────

    #[test]
    fn quiet_mode_suppresses_stderr_for_unknown_chars() {
        // Unknown byte in ANSEL range — quiet=true should not panic
        // (we can't easily capture stderr in tests, so just ensure no panic)
        let result = marc8_to_unicode_rs(b"\x81", true);
        let _ = result;
    }

    #[test]
    fn non_quiet_mode_for_unknown_chars_does_not_panic() {
        let result = marc8_to_unicode_rs(b"\x81", false);
        let _ = result;
    }

    // ── NFC normalization ─────────────────────────────────────────────────────

    #[test]
    fn nfc_normalization_applied() {
        // Input already NFC — should remain unchanged
        let input = "caf\u{00e9}"; // café with precomposed é
        let result = unicode_normalization_nfc(input);
        assert_eq!(result, "caf\u{00e9}");
    }

    #[test]
    fn nfc_normalization_composes_combining() {
        // NFD form: 'e' + combining acute (U+0301) → NFC: é (U+00E9)
        let nfd = "e\u{0301}";
        let result = unicode_normalization_nfc(nfd);
        assert_eq!(result, "\u{00e9}");
    }

    // ── More Complex MARC-8 scenarios ────────────────────────────────────────

    #[test]
    fn marc8_polish_l_and_ae_ligature() {
        // ANSEL 0xA1 is Ł, 0xB1 is ł
        // ANSEL 0xA5 is Æ, 0xB5 is æ
        let input = b"\xa1\xb1 \xa5\xb5";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "Łł Ææ");
    }

    #[test]
    fn marc8_cjk_multibyte() {
        // CJK designator ESC $ 1 (0x1B 0x24 0x31)
        // Character 0x213021 is U+4E00 (一)
        let input = b"\x1b$1\x21\x30\x21";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "一");
    }

    #[test]
    fn marc8_cjk_then_ascii_switch() {
        // Switch to CJK, then back to ASCII with ESC ( B
        let input = b"\x1b$1\x21\x30\x21\x1b(BASCII";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "一ASCII");
    }

    #[test]
    fn marc8_multiple_combinings_on_one_base() {
        // 'a' with acute accent (0xE2) and cedilla (0xF0)
        // In MARC-8 combining marks appear before the base character.
        let input = b"\xf0\xe2a";
        let result = marc8_to_unicode_rs(input, false);
        // Result should be NFC normalized
        use unicode_normalization::UnicodeNormalization;
        let expected: String = "a\u{0327}\u{0301}".nfc().collect();
        assert_eq!(result, expected);
    }

    #[test]
    fn marc8_greek_switch() {
        // Greek designator ESC ( S (0x1B 0x28 0x53)
        // Character 0x41 is Alpha (U+0391)
        let input = b"\x1b(SA";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "\u{0391}");
    }

    #[test]
    fn marc8_cyrillic_switch() {
        // Cyrillic designator ESC ( N (0x1B 0x28 0x4E)
        // Character 0x61 is CYRILLIC CAPITAL LETTER A (U+0410)
        // Character 0x41 is CYRILLIC SMALL LETTER A (U+0430)
        let input = b"\x1b(NaA";
        let result = marc8_to_unicode_rs(input, false);
        assert_eq!(result, "\u{0410}\u{0430}");
    }
}
