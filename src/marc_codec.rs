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
    if data.len() < LEADER_LEN {
        return Err(PyValueError::new_err("Record too short for leader"));
    }

    // Extract leader as ASCII string
    let leader_bytes = &data[..LEADER_LEN];
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
    } else if is_utf8 {
        DecodeMode::Utf8
    } else if effective_encoding == "iso8859-1" {
        DecodeMode::Marc8
    } else {
        // Unknown encoding (cp1251, etc.) — return raw bytes for Python to decode
        DecodeMode::Raw
    };

    // Parse base address from leader positions 12-16
    let base_address_str = std::str::from_utf8(&data[12..17])
        .map_err(|_| PyValueError::new_err("Base address is not valid ASCII"))?;
    let base_address: usize = base_address_str
        .parse()
        .map_err(|_| PyValueError::new_err("Base address is not a valid number"))?;

    if base_address == 0 {
        return Err(PyValueError::new_err("BaseAddressNotFound"));
    }
    if base_address > data.len() {
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

    if directory.len() % DIRECTORY_ENTRY_LEN != 0 {
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
                DecodeMode::Utf8 => {
                    let s = decode_utf8(field_data, utf8_handling);
                    PyString::new(py, &s).into_any()
                }
                DecodeMode::Marc8 => {
                    let s = marc8::marc8_to_unicode_rs(field_data, quiet);
                    PyString::new(py, &s).into_any()
                }
            };
            let control_tuple = PyTuple::new(py, &[
                PyString::intern(py, "control").into_any(),
                value,
            ])?;
            let field_tuple = PyTuple::new(py, &[
                tag_py.into_any(),
                control_tuple.into_any(),
            ])?;
            fields_list.append(field_tuple)?;
        } else {
            let subfield_parts = split_on_indicator(field_data);
            let indicators = &subfield_parts[0];
            let (ind1, ind2) = parse_indicators(indicators);

            let subfields_list = PyList::empty(py);
            for part in &subfield_parts[1..] {
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
                        DecodeMode::Utf8 => {
                            let s = decode_utf8(value, utf8_handling);
                            PyString::new(py, &s).into_any()
                        }
                        DecodeMode::Marc8 => {
                            let s = marc8::marc8_to_unicode_rs(value, quiet);
                            PyString::new(py, &s).into_any()
                        }
                    };
                    let sub_tuple = PyTuple::new(py, &[
                        code_py.into_any(),
                        value_py,
                    ])?;
                    subfields_list.append(sub_tuple)?;
                } else {
                    // Non-ASCII code - return raw bytes for Python to handle
                    let sub_tuple = PyTuple::new(py, &[
                        PyBytes::new(py, &part[..1]).into_any(),
                        PyBytes::new(py, value).into_any(),
                    ])?;
                    subfields_list.append(sub_tuple)?;
                }
            }

            let data_tuple = PyTuple::new(py, &[
                PyString::intern(py, "data").into_any(),
                PyString::new(py, &String::from(ind1 as char)).into_any(),
                PyString::new(py, &String::from(ind2 as char)).into_any(),
                subfields_list.into_any(),
            ])?;
            let field_tuple = PyTuple::new(py, &[
                tag_py.into_any(),
                data_tuple.into_any(),
            ])?;
            fields_list.append(field_tuple)?;
        }
    }

    Ok((PyString::new(py, leader_str), fields_list))
}

/// Decode bytes as UTF-8 with the given error handling
fn decode_utf8(data: &[u8], handling: &str) -> String {
    match handling {
        "strict" => String::from_utf8(data.to_vec()).unwrap_or_else(|_| {
            String::from_utf8_lossy(data).into_owned()
        }),
        "ignore" => String::from_utf8_lossy(data)
            .chars()
            .filter(|c| *c != '\u{FFFD}')
            .collect(),
        _ => String::from_utf8_lossy(data).into_owned(), // "replace" and others
    }
}


/// Split byte slice on SUBFIELD_INDICATOR (0x1F)
fn split_on_indicator(data: &[u8]) -> Vec<&[u8]> {
    let mut parts = Vec::new();
    let mut start = 0;
    for (i, &byte) in data.iter().enumerate() {
        if byte == SUBFIELD_INDICATOR {
            parts.push(&data[start..i]);
            start = i + 1;
        }
    }
    parts.push(&data[start..]);
    parts
}

/// Parse indicator bytes, handling missing/malformed indicators
fn parse_indicators(indicators: &[u8]) -> (u8, u8) {
    match indicators.len() {
        0 => (b' ', b' '),
        1 => (indicators[0], b' '),
        _ => (indicators[0], indicators[1]),
    }
}

/// Encode structured field data back to MARC21 bytes.
#[pyfunction]
pub fn encode_marc_raw<'py>(
    py: Python<'py>,
    leader: &str,
    fields: Vec<(String, Bound<'py, PyBytes>)>,
) -> PyResult<Bound<'py, PyBytes>> {
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
