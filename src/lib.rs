use pyo3::prelude::*;

mod marc8;
mod marc8_mapping;
mod marc_codec;

/// Returns the rmarc library version string.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_returns_nonempty_string() {
        let v = version();
        assert!(!v.is_empty());
    }

    #[test]
    fn version_starts_with_digit() {
        let v = version();
        assert!(
            v.chars().next().unwrap().is_ascii_digit(),
            "version should start with a digit, got: {v}"
        );
    }
}

#[pymodule]
fn _rmarc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;

    m.add_function(wrap_pyfunction!(marc_codec::decode_marc_raw, m)?)?;
    m.add_function(wrap_pyfunction!(marc_codec::encode_marc_raw, m)?)?;
    m.add_function(wrap_pyfunction!(marc8::marc8_to_unicode_rs, m)?)?;
    Ok(())
}
