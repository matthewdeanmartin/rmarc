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
            if next_byte == b')' || next_byte == b'-' {
                if pos + 2 < len {
                    g1 = data[pos + 2];
                    pos += 3;
                    continue;
                }
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
