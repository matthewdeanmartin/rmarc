//! Binary MARC21 codec: decode raw bytes into structured components,
//! and encode structured components back to bytes.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyString, PyTuple};

use crate::marc8;

const LEADER_LEN: usize = 24;
const DIRECTORY_ENTRY_LEN: usize = 12;
const SUBFIELD_INDICATOR: u8 = 0x1F;
const END_OF_FIELD: u8 = 0x1E;
const END_OF_RECORD: u8 = 0x1D;

/// Decode mode for subfield values
enum DecodeMode {
    /// Return raw bytes (to_unicode=false, or unknown encoding for Python to handle)
    Raw,
    /// Decode as UTF-8
    Utf8,
    /// Decode using MARC-8 converter
    Marc8,
}

struct ObjectTypes<'a, 'py> {
    field: &'a Bound<'py, PyAny>,
    new_field: Bound<'py, PyAny>,
    subfield: &'a Bound<'py, PyAny>,
    indicators: &'a Bound<'py, PyAny>,
}

struct DecodeOptions<'a> {
    to_unicode: bool,
    force_utf8: bool,
    encoding: &'a str,
    utf8_handling: &'a str,
    quiet: bool,
}

/// Decode a raw MARC21 record into structured components.
///
/// Returns: (leader_str, [(tag, field_data), ...])
///   where field_data is either:
///     - ("control", data_bytes_or_str) for control fields
///     - ("data", ind1, ind2, [(code_str, value_str_or_bytes), ...]) for data fields
///
/// When to_unicode=true and the encoding can be handled in Rust, values are
/// returned as decoded strings. Otherwise raw bytes are returned.
#[pyfunction]
#[pyo3(signature = (data, to_unicode=true, force_utf8=false, encoding="iso8859-1", utf8_handling="strict", quiet=false))]
pub fn decode_marc_raw<'py>(
    py: Python<'py>,
    data: &[u8],
    to_unicode: bool,
    force_utf8: bool,
    encoding: &str,
    utf8_handling: &str,
    quiet: bool,
) -> PyResult<(Bound<'py, PyString>, Bound<'py, PyList>)> {
    decode_marc_impl(
        py,
        data,
        DecodeOptions {
            to_unicode,
            force_utf8,
            encoding,
            utf8_handling,
            quiet,
        },
        None,
    )
}

/// Build the actual Python objects once, without an intermediate tuple tree.
/// Types come from the caller; no process-global Python class cache is needed.
#[pyfunction]
#[pyo3(signature = (data, field_type, subfield_type, indicators_type, to_unicode=true, force_utf8=false, encoding="iso8859-1", utf8_handling="strict", quiet=false))]
#[allow(clippy::too_many_arguments)]
pub fn decode_marc_fields<'py>(
    py: Python<'py>,
    data: &[u8],
    field_type: Bound<'py, PyAny>,
    subfield_type: Bound<'py, PyAny>,
    indicators_type: Bound<'py, PyAny>,
    to_unicode: bool,
    force_utf8: bool,
    encoding: &str,
    utf8_handling: &str,
    quiet: bool,
) -> PyResult<(Bound<'py, PyString>, Bound<'py, PyList>)> {
    let types = ObjectTypes {
        new_field: field_type.getattr(pyo3::intern!(py, "__new__"))?,
        field: &field_type,
        subfield: &subfield_type,
        indicators: &indicators_type,
    };
    decode_marc_impl(
        py,
        data,
        DecodeOptions {
            to_unicode,
            force_utf8,
            encoding,
            utf8_handling,
            quiet,
        },
        Some(&types),
    )
}

fn decode_marc_impl<'py>(
    py: Python<'py>,
    data: &[u8],
    options: DecodeOptions<'_>,
    types: Option<&ObjectTypes<'_, 'py>>,
) -> PyResult<(Bound<'py, PyString>, Bound<'py, PyList>)> {
    let DecodeOptions {
        to_unicode,
        force_utf8,
        encoding,
        utf8_handling,
        quiet,
    } = options;
    if data.len() < LEADER_LEN {
        return Err(PyValueError::new_err("Record too short for leader"));
    }

    // Extract leader as ASCII string
    let leader_bytes = &data[..LEADER_LEN];
    if !leader_bytes.is_ascii() {
        return Err(PyValueError::new_err("Leader is not valid ASCII"));
    }
    let leader_str = std::str::from_utf8(leader_bytes)
        .map_err(|_| PyValueError::new_err("Leader is not valid ASCII"))?;

    // Determine encoding from leader[9] and flags
    let is_utf8 = leader_bytes[9] == b'a' || force_utf8;
    let effective_encoding = if is_utf8 { "utf-8" } else { encoding };

    // Determine decode mode
    // Only handle encodings Rust knows natively; for others return raw bytes
    // so Python can use its codec system
    let decode_mode = if !to_unicode {
        DecodeMode::Raw
    } else if effective_encoding == "utf-8" {
        DecodeMode::Utf8
    } else if effective_encoding == "iso8859-1" {
        DecodeMode::Marc8
    } else {
        // Unknown encoding (cp1251, etc.) — return raw bytes for Python to decode
        DecodeMode::Raw
    };
    // Explicit file_encoding without a leader/force flag uses strict decoding
    // in pymarc, even when utf8_handling requests something else.
    let subfield_errors = if is_utf8 { utf8_handling } else { "strict" };

    // Parse base address from leader positions 12-16
    let base_address_str = std::str::from_utf8(&data[12..17])
        .map_err(|_| PyValueError::new_err("Base address is not valid ASCII"))?;
    let base_address: usize = base_address_str
        .parse()
        .map_err(|_| PyValueError::new_err("Base address is not a valid number"))?;

    if base_address == 0 {
        return Err(PyValueError::new_err("BaseAddressNotFound"));
    }
    if base_address >= data.len() {
        return Err(PyValueError::new_err("BaseAddressInvalid"));
    }

    // Parse record length from leader
    let record_length_str = std::str::from_utf8(&data[..5])
        .map_err(|_| PyValueError::new_err("Record length not valid ASCII"))?;
    let record_length: usize = record_length_str
        .parse()
        .map_err(|_| PyValueError::new_err("Record length not a valid number"))?;
    if data.len() < record_length {
        return Err(PyValueError::new_err("TruncatedRecord"));
    }

    // Extract directory
    if base_address <= LEADER_LEN {
        return Err(PyValueError::new_err("RecordDirectoryInvalid"));
    }
    let directory = &data[LEADER_LEN..base_address - 1];

    // Validate directory is ASCII before checking length
    if !directory.is_ascii() {
        return Err(PyValueError::new_err("Directory is not valid ASCII"));
    }

    if !directory.len().is_multiple_of(DIRECTORY_ENTRY_LEN) {
        return Err(PyValueError::new_err("RecordDirectoryInvalid"));
    }

    let field_total = directory.len() / DIRECTORY_ENTRY_LEN;
    if field_total == 0 {
        return Err(PyValueError::new_err("NoFieldsFound"));
    }

    let fields_list = PyList::empty(py);

    for i in 0..field_total {
        let entry_start = i * DIRECTORY_ENTRY_LEN;
        let entry = &directory[entry_start..entry_start + DIRECTORY_ENTRY_LEN];

        let tag_str = std::str::from_utf8(&entry[0..3])
            .map_err(|_| PyValueError::new_err("Tag is not valid ASCII"))?;
        let entry_length: usize = std::str::from_utf8(&entry[3..7])
            .map_err(|_| PyValueError::new_err("Field length not valid ASCII"))?
            .parse()
            .map_err(|_| PyValueError::new_err("Field length not a number"))?;
        let entry_offset: usize = std::str::from_utf8(&entry[7..12])
            .map_err(|_| PyValueError::new_err("Field offset not valid ASCII"))?
            .parse()
            .map_err(|_| PyValueError::new_err("Field offset not a number"))?;

        let field_start = base_address + entry_offset;
        if entry_length == 0 {
            return Err(PyValueError::new_err("DirectoryInvalid: zero-length field"));
        }
        let field_end = base_address + entry_offset + entry_length - 1;
        if field_end > data.len() {
            return Err(PyValueError::new_err("Field extends beyond record"));
        }
        let field_data = &data[field_start..field_end];

        let is_control = tag_str < "010" && tag_str.bytes().all(|b| b.is_ascii_digit());
        let tag_py = PyString::intern(py, tag_str);

        if is_control {
            let value: Bound<'_, PyAny> = match &decode_mode {
                DecodeMode::Raw => PyBytes::new(py, field_data).into_any(),
                DecodeMode::Utf8 => decode_utf8(py, field_data, "strict")?.into_any(),
                DecodeMode::Marc8 => {
                    // pymarc decodes legacy control fields as Latin-1, not MARC-8.
                    if field_data.is_ascii() {
                        PyString::new(py, std::str::from_utf8(field_data).expect("ASCII"))
                            .into_any()
                    } else {
                        PyBytes::new(py, field_data)
                            .call_method1(pyo3::intern!(py, "decode"), ("latin-1",))?
                    }
                }
            };
            if let Some(types) = types {
                let field = types.new_field.call1((types.field,))?;
                field.setattr(pyo3::intern!(py, "tag"), tag_py)?;
                field.setattr(pyo3::intern!(py, "data"), value)?;
                field.setattr(pyo3::intern!(py, "control_field"), true)?;
                field.setattr(pyo3::intern!(py, "_indicators"), py.None())?;
                field.setattr(pyo3::intern!(py, "subfields"), PyList::empty(py))?;
                fields_list.append(field)?;
                continue;
            }
            let control_tuple =
                PyTuple::new(py, &[PyString::intern(py, "control").into_any(), value])?;
            let field_tuple = PyTuple::new(py, &[tag_py.into_any(), control_tuple.into_any()])?;
            fields_list.append(field_tuple)?;
        } else {
            let mut subfield_parts = split_on_indicator(field_data);
            let indicators = subfield_parts.next().expect("split always yields a part");
            if types.is_some() && (indicators.len() != 2 || !indicators.is_ascii()) {
                // Let the Python path reproduce warnings and ASCII error details.
                return Err(PyValueError::new_err(
                    "Python fallback: malformed indicators",
                ));
            }
            let (ind1, ind2) = parse_indicators(indicators);

            let subfields_list = PyList::empty(py);
            for part in subfield_parts {
                if part.is_empty() {
                    continue;
                }
                let code_byte = part[0];
                let value = &part[1..];

                if code_byte.is_ascii() {
                    let code_str = std::str::from_utf8(&part[..1]).unwrap();
                    let code_py = PyString::intern(py, code_str);
                    let value_py: Bound<'_, PyAny> = match &decode_mode {
                        DecodeMode::Raw => PyBytes::new(py, value).into_any(),
                        DecodeMode::Utf8 => decode_utf8(py, value, subfield_errors)?.into_any(),
                        DecodeMode::Marc8 => {
                            if value.last() == Some(&0x1b) {
                                return Err(PyValueError::new_err(
                                    "Python fallback: trailing MARC-8 escape",
                                ));
                            }
                            let s = marc8::marc8_to_unicode(value, quiet);
                            PyString::new(py, &s).into_any()
                        }
                    };
                    if let Some(types) = types {
                        subfields_list.append(types.subfield.call1((code_py, value_py))?)?;
                        continue;
                    }
                    let sub_tuple = PyTuple::new(py, &[code_py.into_any(), value_py])?;
                    subfields_list.append(sub_tuple)?;
                } else {
                    if types.is_some() {
                        return Err(PyValueError::new_err(
                            "Python fallback: non-ASCII subfield code",
                        ));
                    }
                    // Non-ASCII code - return raw bytes for Python to handle
                    let sub_tuple = PyTuple::new(
                        py,
                        &[
                            PyBytes::new(py, &part[..1]).into_any(),
                            PyBytes::new(py, value).into_any(),
                        ],
                    )?;
                    subfields_list.append(sub_tuple)?;
                }
            }

            if let Some(types) = types {
                let field = types.new_field.call1((types.field,))?;
                field.setattr(pyo3::intern!(py, "tag"), tag_py)?;
                field.setattr(pyo3::intern!(py, "data"), py.None())?;
                field.setattr(pyo3::intern!(py, "control_field"), false)?;
                let indicators = types.indicators.call1((
                    PyString::new(py, std::str::from_utf8(&[ind1]).expect("ASCII indicator")),
                    PyString::new(py, std::str::from_utf8(&[ind2]).expect("ASCII indicator")),
                ))?;
                field.setattr(pyo3::intern!(py, "_indicators"), indicators)?;
                field.setattr(pyo3::intern!(py, "subfields"), subfields_list)?;
                fields_list.append(field)?;
                continue;
            }

            let data_tuple = PyTuple::new(
                py,
                &[
                    PyString::intern(py, "data").into_any(),
                    PyString::new(py, &String::from(ind1 as char)).into_any(),
                    PyString::new(py, &String::from(ind2 as char)).into_any(),
                    subfields_list.into_any(),
                ],
            )?;
            let field_tuple = PyTuple::new(py, &[tag_py.into_any(), data_tuple.into_any()])?;
            fields_list.append(field_tuple)?;
        }
    }

    Ok((PyString::new(py, leader_str), fields_list))
}

/// Borrow valid UTF-8; delegate invalid bytes to Python's codec registry.
fn decode_utf8<'py>(
    py: Python<'py>,
    data: &[u8],
    handling: &str,
) -> PyResult<Bound<'py, PyString>> {
    if let Ok(text) = std::str::from_utf8(data) {
        // Borrow valid UTF-8 directly into Python, avoiding Vec and String copies.
        return Ok(PyString::new(py, text));
    }
    // Python owns error-handler semantics (including registered custom handlers
    // and surrogateescape, which cannot be represented by Rust's String).
    PyBytes::new(py, data)
        .call_method1(pyo3::intern!(py, "decode"), ("utf-8", handling))?
        .cast_into::<PyString>()
        .map_err(Into::into)
}

/// Split byte slice on SUBFIELD_INDICATOR (0x1F)
fn split_on_indicator(data: &[u8]) -> impl Iterator<Item = &[u8]> {
    data.split(|byte| *byte == SUBFIELD_INDICATOR)
}

/// Parse indicator bytes, handling missing/malformed indicators
fn parse_indicators(indicators: &[u8]) -> (u8, u8) {
    match indicators.len() {
        0 => (b' ', b' '),
        1 => (indicators[0], b' '),
        _ => (indicators[0], indicators[1]),
    }
}

#[cfg(test)]
pub(crate) fn split_on_indicator_pub(data: &[u8]) -> Vec<Vec<u8>> {
    split_on_indicator(data)
        .into_iter()
        .map(|s| s.to_vec())
        .collect()
}

#[cfg(test)]
pub(crate) fn parse_indicators_pub(indicators: &[u8]) -> (u8, u8) {
    parse_indicators(indicators)
}

/// Encode structured field data back to MARC21 bytes.
#[pyfunction]
pub fn encode_marc_raw<'py>(
    py: Python<'py>,
    leader: &str,
    fields: Vec<(String, Bound<'py, PyBytes>)>,
) -> PyResult<Bound<'py, PyBytes>> {
    if leader.len() < LEADER_LEN {
        return Err(PyValueError::new_err(format!(
            "Leader must be at least {} bytes, got {}",
            LEADER_LEN,
            leader.len()
        )));
    }
    if !leader.is_ascii() {
        return Err(PyValueError::new_err(
            "Leader contains non-ASCII characters",
        ));
    }

    let mut directory = Vec::with_capacity(fields.len() * DIRECTORY_ENTRY_LEN + 1);
    let mut field_data = Vec::new();
    let mut offset: usize = 0;

    for (tag, data) in &fields {
        let data_bytes = data.as_bytes();
        let length = data_bytes.len();

        let dir_entry = format!("{:>03}{:04}{:05}", tag, length, offset);
        directory.extend_from_slice(dir_entry.as_bytes());

        field_data.extend_from_slice(data_bytes);
        offset += length;
    }

    directory.push(END_OF_FIELD);
    field_data.push(END_OF_RECORD);

    let base_address = LEADER_LEN + directory.len();
    let record_length = base_address + field_data.len();

    let new_leader = format!(
        "{:0>5}{}{:0>5}{}",
        record_length,
        &leader[5..12],
        base_address,
        &leader[17..]
    );

    let mut result = Vec::with_capacity(record_length);
    result.extend_from_slice(new_leader.as_bytes());
    result.extend_from_slice(&directory);
    result.extend_from_slice(&field_data);

    Ok(PyBytes::new(py, &result))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── split_on_indicator ────────────────────────────────────────────────────

    #[test]
    fn split_on_indicator_empty() {
        assert_eq!(split_on_indicator_pub(b""), vec![b"".to_vec()]);
    }

    #[test]
    fn split_on_indicator_no_delimiter() {
        assert_eq!(split_on_indicator_pub(b"hello"), vec![b"hello".to_vec()]);
    }

    #[test]
    fn split_on_indicator_single_subfield() {
        // indicator block (" ") then 0x1F 'a' "value"
        let input = b"  \x1Favalue";
        let parts = split_on_indicator_pub(input);
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0], b"  ");
        assert_eq!(parts[1], b"avalue");
    }

    #[test]
    fn split_on_indicator_multiple_subfields() {
        let input = b"  \x1Fahello\x1Fbworld";
        let parts = split_on_indicator_pub(input);
        assert_eq!(parts.len(), 3);
        assert_eq!(parts[0], b"  ");
        assert_eq!(parts[1], b"ahello");
        assert_eq!(parts[2], b"bworld");
    }

    #[test]
    fn split_on_indicator_leading_delimiter() {
        let input = b"\x1Faonly";
        let parts = split_on_indicator_pub(input);
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0], b"".to_vec());
        assert_eq!(parts[1], b"aonly");
    }

    // ── parse_indicators ─────────────────────────────────────────────────────

    #[test]
    fn parse_indicators_empty_defaults_to_spaces() {
        assert_eq!(parse_indicators_pub(b""), (b' ', b' '));
    }

    #[test]
    fn parse_indicators_one_byte() {
        assert_eq!(parse_indicators_pub(b"1"), (b'1', b' '));
    }

    #[test]
    fn parse_indicators_two_bytes() {
        assert_eq!(parse_indicators_pub(b"12"), (b'1', b'2'));
    }

    #[test]
    fn parse_indicators_extra_bytes_ignored() {
        assert_eq!(parse_indicators_pub(b"12extra"), (b'1', b'2'));
    }

    // ── MARC record structure constants ───────────────────────────────────────

    #[test]
    fn constants_have_expected_values() {
        assert_eq!(LEADER_LEN, 24);
        assert_eq!(DIRECTORY_ENTRY_LEN, 12);
        assert_eq!(SUBFIELD_INDICATOR, 0x1F);
        assert_eq!(END_OF_FIELD, 0x1E);
        assert_eq!(END_OF_RECORD, 0x1D);
    }

    #[test]
    fn split_on_indicator_multiple_empty_subfields() {
        // "  " (indicators) + \x1f + 'a' + "" + \x1f + 'b' + ""
        let input = b"  \x1Fa\x1Fb";
        let parts = split_on_indicator_pub(input);
        assert_eq!(parts.len(), 3);
        assert_eq!(parts[0], b"  ");
        assert_eq!(parts[1], b"a");
        assert_eq!(parts[2], b"b");
    }

    #[test]
    fn parse_indicators_malformed() {
        // Only one byte provided
        assert_eq!(parse_indicators_pub(b"1"), (b'1', b' '));
        // More than two bytes - should take first two
        assert_eq!(parse_indicators_pub(b"123"), (b'1', b'2'));
    }
}
