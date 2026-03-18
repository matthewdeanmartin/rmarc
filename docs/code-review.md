# rmarc code review

Scope: Rust in `src\` and Python in `python\rmarc\`, reviewed against the stated goal of delivering Rust speedups while remaining a drop-in replacement for `pymarc`.

Validation baseline:

- `cargo test` passed.
- `pytest test_pymarc -q` passed: `564 passed`.

That baseline is useful, but it does **not** eliminate several compatibility and robustness risks. The findings below focus on issues that can still matter in production even with the current suite passing.

## Executive summary

The codebase does a good job of preserving a large amount of `pymarc` behavior, and the Rust/Python split is generally sensible: parsing and MARC-8 conversion are pushed down into Rust while object construction and the API surface remain in Python.

The biggest problems are not in the normal happy path. They are in the edges that matter for a library promising drop-in compatibility:

1. The advertised pure-Python fallback is not actually usable as a package-level fallback.
2. The Rust codec can raise `PanicException` on malformed input instead of surfacing ordinary Python exceptions.
3. A few fallback and I/O paths behave differently from what their API suggests.

## Findings

### 1. Pure-Python fallback is not actually available at package import time

Severity: **Critical**

Why it matters:

The README explicitly says pure Python fallbacks are included for platforms where the Rust extension cannot be built, but the package-level import path still hard-depends on the extension. That breaks the drop-in replacement story on exactly the platforms where the fallback is supposed to help.

Evidence:

- `README.md:7-9` says pure Python fallbacks are included when the Rust extension cannot be built.
- `python\rmarc\__init__.py:3-15` unconditionally imports `version` from `rmarc._rmarc` and then immediately calls it for `__version__`.
- `pyproject.toml:105-112` uses `maturin` as the build backend and defines the extension module as `rmarc._rmarc`, with no separate pure-Python build path.

Impact:

- `import rmarc` fails if `rmarc._rmarc` is unavailable, even though lower-level modules like `record.py` and `marc8.py` contain `ImportError` guards.
- This means the current packaging/import design does not match the documented fallback behavior.

Observed behavior:

- A simulated import where `rmarc._rmarc` was blocked failed immediately with `ImportError` before the guarded fallback paths could help.

### 2. Rust decode path can panic on zero-length directory entries

Severity: **Critical**

Location:

- `src\marc_codec.rs:134-139`

Why it matters:

Malformed MARC should produce a normal Python exception, not a Rust panic crossing the FFI boundary. A `PanicException` is much less compatible with `pymarc` error handling and is much riskier in bulk ingestion workloads.

Details:

- `field_end` is computed as `base_address + entry_offset + entry_length - 1`.
- If `entry_length == 0`, then `field_end < field_start`.
- The next slice, `&data[field_start..field_end]`, panics instead of returning a structured error.

Observed behavior:

- A crafted record with a `245` directory entry of length `0000` triggered:
  - `PanicException 'slice index starts at 37 but ends at 36'`

Compatibility concern:

- This is exactly the sort of malformed-record edge where drop-in compatibility matters. A parser replacement should fail in the same general shape as `pymarc`, not with Rust slice panics.

### 3. Rust encode path trusts leader shape too much and can panic on invalid strings

Severity: **High**

Location:

- `src\marc_codec.rs:316-321`
- Called from `python\rmarc\record.py:440-441`

Why it matters:

The Rust encoder slices `leader` using Rust string byte indices:

- `&leader[5..12]`
- `&leader[17..]`

That assumes the leader is long enough and ASCII-safe for those exact byte boundaries. When that assumption is violated, the Rust extension raises `PanicException`.

Observed behavior:

- Direct calls to `encode_marc_raw("short", [])` raised:
  - `PanicException 'byte index 12 is out of bounds of \`short\`'`
- Direct calls to `encode_marc_raw("é" * 24, [])` raised:
  - `PanicException` complaining that byte index `5` is not a char boundary.

Why this matters even if normal callers usually pass valid leaders:

- The function is exported as a Python-visible API.
- `Record.as_marc()` routes through it whenever Rust is available.
- `Record.leader` can be replaced by user code with a plain string, so malformed leader data can escape Python validation and hit the Rust panic path.

Additional note:

- For some malformed-but-long-enough leader strings, the code does not panic; it silently serializes a malformed leader instead. That is safer than panicking, but still weakens input validation at an FFI boundary.

### 4. `JSONReader` ignores its `encoding=` argument when given a file path

Severity: **Medium**

Location:

- `python\rmarc\reader.py:147-155`

Why it matters:

The API accepts `encoding`, but when `marc_target` is a filesystem path it does:

- `self.file_handle = open(marc_target)`

That uses the process default text encoding instead of the caller-supplied encoding.

Impact:

- Non-UTF-8 JSON files can be mis-decoded into mojibake even when the caller explicitly requested the correct encoding.
- This is a real compatibility problem for library users depending on the parameter contract.

Observed behavior:

- A `cp1251` JSON file read via `JSONReader(path, encoding="cp1251")` produced mojibake (`Ïðèâåò`) rather than the intended Cyrillic text.

### 5. The pure-Python MARC-8 fallback does not fully honor `hide_utf8_warnings`

Severity: **Medium**

Location:

- `python\rmarc\marc8.py:29-49`
- `python\rmarc\marc8.py:108-113`

Why it matters:

`hide_utf8_warnings=True` is meant to suppress noisy decode diagnostics. The fallback converter sets `quiet`, but truncated multibyte handling still writes directly to `stderr` without checking `self.quiet`.

Impact:

- Rust and Python fallback behavior diverge.
- On environments without the extension, callers can still get warning output even when they explicitly asked not to.

Observed behavior:

- Calling `_marc8_to_unicode_python(..., hide_utf8_warnings=True)` on truncated multibyte data still emitted:
  - `"Multi-byte position ... exceeds length of marc8 string ..."`

Why this matters for the project goal:

- The project promise is not just speed; it is compatible replacement behavior. Silent divergence between Rust and fallback paths weakens that promise.

## Lower-priority observations

### 6. The README quickstart test command appears stale

Severity: **Low**

Evidence:

- `README.md:63-65` says `uv run pytest tests/`
- The repository test suite is centered on `test_pymarc\`, and `pyproject.toml:141-144` points pytest at `test` and `test_pymarc`

Why it matters:

- This is not a runtime bug, but it does make validation less clear for contributors and can slow down review of compatibility issues.

## Things that look solid

- The Python API layer tracks upstream `pymarc` closely in structure and naming. That is a good choice for compatibility.
- The Rust MARC-8 converter is well covered and cross-checked against the Python tables through `test_pymarc\test_suite_marc8.py`.
- The baseline test suite is strong enough to give confidence in common read/write flows and many compatibility paths.
- Handling for unknown record encodings is intentionally delegated back to Python, which is a reasonable design for preserving codec flexibility.

## Overall assessment

`rmarc` is already fairly close to its stated goal on the happy path: the current tests suggest that common `pymarc` compatibility behavior is preserved while the hot paths are accelerated in Rust.

The main remaining risks are boundary risks:

- packaging/import fallback,
- malformed-input panic behavior in Rust,
- and a few API contracts that do not match their implementation details.

Those issues are important because they affect trust in `rmarc` as a drop-in replacement. For a library in this role, edge-case behavior and failure shape are just as important as benchmark wins.
