# Release test and typing audit — 2026-10-13

Local validation on Windows, against pymarc 5.4.0. These are unpublished
working-tree changes; no release or remote CI was dispatched.

## Results

| Check | Result |
| --- | --- |
| Rust unit tests | 38 passed, including 5 new tests |
| Python 3.13.3, full repository | 881 passed, 12 subtests passed |
| Rebuilt release wheel, Python 3.15.0, library suite | 769 passed, 12 subtests passed |
| Python statement/branch coverage | 95%, previously about 94% |
| XML module coverage | 100%, previously about 90% |
| mypy, Pyright, Pyrefly | All pass for `python/rmarc` |
| Cargo formatting and Clippy | Pass |

Both Python runs report the same 52 expected malformed-input warnings. The
full repository includes 112 sample application tests omitted from the 3.15
library-only run. Optional lxml/orjson runtimes were installed from published
wheels; tests explicitly select both accelerated and standard-library paths.
Rust coverage was not measured; Python coverage does not measure native code.
Other operating systems still require the normal release matrix.

## New tests and why they matter

- `test_pymarc/test_release_backends.py`: namespace/schema declarations,
  strict namespace filtering, Unicode normalization, repeated subfields, XML
  escaping, callback order across files, collection writer round trips, and
  conversion of raw MARC-8 values. Each XML case runs with both backends.
  An isolated optional-module import tests absent accelerators without leaking
  global state, plus orjson's fallback for literal JSON control characters.
- `test_pymarc/test_release_codec_boundaries.py`: directory lengths and offsets
  outside record bounds, preserving the following record with three buffer
  sizes; 300 arbitrary byte strings and 200 numeric directory mutations via
  Hypothesis. A PyO3 panic inherits `BaseException`, so it cannot be swallowed
  by the tests' handling of ordinary Python exceptions.
- Rust: decimal encoding is compared with standard formatting for every value
  from 0 through 100,000 at widths four and five, retaining an existing buffer
  prefix. MARC-8 tests verify borrowed ASCII output, every non-printable byte
  avoiding that fast path, truncated CJK replacement, and isolated charset and
  combining-mark state across calls.

The directory tests intentionally preserve pymarc's forgiving slice behavior:
invalid bounds can still produce a record. They verify the native decoder's
fallback, rather than imposing stricter validation on the public API.
No new codec runtime defect was demonstrated by this pass.

## Typing findings and changes

Pyrefly was not previously configured or part of CI. The existing mypy setup
was not strict: it skipped unannotated function bodies. Missing lxml stubs
initially blocked it. Adding complete stubs and checking those bodies exposed
12 errors: optional module assignment, a dead assignment mixing integer and
string types, reader exception-state inference, and a callback assigned over
a method. Pyrefly additionally exposed optional-module and cross-backend XML
element typing problems.

These findings are fixed. XML factories now retain their backend's element
type through a generic builder. `XMLWriter` retains its existing ElementTree
serialization and byte formatting; a documented cast describes lxml's compatible
structural element interface. Reader state properties explicitly expose
`bytes | None` and `Exception | None`.

The development dependencies now use
[types-lxml](https://pypi.org/project/types-lxml/), the maintained replacement
for `lxml-stubs`, and Pyrefly. Do not install both lxml stub packages together.
Pyrefly has its own configuration in `pyproject.toml`; it no longer relies on
importing the Pyright configuration.

This is stronger checking, not a claim of complete public typing. Many APIs
remain unannotated/dynamic, and RawField's inherited text-oriented annotations
still do not fully describe its bytes values. The native extension already
has a `.pyi` and the package has `py.typed`. Tightening public input and return
types, with typed consumer examples, remains useful follow-up work.

## Repeatable checks

Use the project virtual environment (on Windows, `.venv/Scripts/python.exe`).

```bash
make rust-test
make test-coverage
make lint-mypy lint-pyright lint-pyrefly
```

`test-coverage` now discovers pytest/Hypothesis tests, replacing its old
unittest-only discovery. `make ci` and `make check-all` include all three type
checkers. The CI test job installs published optional backend wheels so the
accelerated tests do not silently skip; the parameterized tests also exercise
the standard-library implementations.
