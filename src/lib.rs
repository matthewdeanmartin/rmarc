use pyo3::prelude::*;

/// Returns the rmarc library version string.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// A stub MARC record placeholder for Phase 1.
#[pyclass]
struct MarcRecord {
    #[pyo3(get, set)]
    pub tag: String,
}

#[pymethods]
impl MarcRecord {
    #[new]
    fn new(tag: String) -> Self {
        MarcRecord { tag }
    }

    fn value(&self) -> &str {
        "stub"
    }
}

#[pymodule]
fn _rmarc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_class::<MarcRecord>()?;
    Ok(())
}
