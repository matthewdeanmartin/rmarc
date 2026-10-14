# Compatibility and decoder implementation

This follows the [release audit](performance-compatibility-audit-2026-10-13.md)
and implements its first three steps. Changes remain uncommitted.

## What changed

1. **Compatibility.** UTF-8 `ignore` preserves legitimate replacement characters;
   Python handles invalid UTF-8 and its registered error handlers. Explicit UTF-8
   file encoding produces strings. Legacy control fields use Latin-1. Failed
   decoding preserves the exact Python exception payload and the fields decoded
   before the failure. Unusual encodings, custom handlers, malformed indicators,
   non-ASCII subfield codes and trailing MARC-8 escapes use the Python path.
   Tag normalization and upstream regression additions now follow pymarc 5.4.0.
2. **Lookups.** Record/Field lookups stop at the first match. Multi-tag selection
   preserves record order, repeated selectors do not duplicate fields, and list
   mutation cannot invalidate a hidden tag index because no index is introduced.
   Related upstream deletion, assignment and formatting improvements are included.
3. **Decoding.** Rust creates the actual Python Field, RawField, Subfield and
   Indicators objects directly. It no longer creates a temporary nested tuple tree
   for Python to unpack into those objects. Valid UTF-8 is borrowed until the
   Python string is created; printable MARC-8 ASCII skips mapping/normalization;
   splitting subfields uses an iterator instead of allocating a vector.

Types are passed into the native call, rather than cached globally. Results are
fully materialized ordinary Python objects. Existing field-list references remain
valid; subclass `add_field` hooks take the Python path. There is no lazy proxy,
read-ahead, or new public reader API.

The lower-level `decode_marc_raw` entry point remains available. Five old Rust
UTF-8 helper tests were replaced with Python-level tests of real codec behavior,
including custom handlers, surrogates, exact errors and literal U+FFFD.

## Maintainer reproductions

[`mrrc_compat_issues`](../mrrc_compat_issues/README.md) is independently runnable:
requirements, pytest config, a tiny two-library fixture and ten examples. It
needs no rmarc installation or external MARC files. The expected result for
pymarc 5.4.0 / mrrc 0.9.2 is **11 passed, 9 failed**. The failures deliberately
expose the differences; the direct-assignment control passes for both libraries.
Documented method/list API differences are separated from behavioral differences.
No upstream issue or maintainer message was sent.

## Measurement method

The final **same-process, interleaved** confirmation gives the following speedups
over the original rmarc. This is the preferred summary after detecting load drift
in a separate-process check:

| Workload | Python 3.13 | Python 3.15 |
| --- | ---: | ---: |
| Real UTF-8 corpus: read | 1.77x | 1.63x |
| Real UTF-8 corpus: read + title | 1.71x | 1.58x |
| Real UTF-8 corpus: read + serialize | 1.32x | 1.35x |
| Repeated MARC-8 corpus: read | 2.44x | 2.59x |
| Repeated MARC-8 corpus: read + title | 2.66x | 2.66x |
| Repeated MARC-8 corpus: read + serialize | 1.58x | 1.79x |

Seven shuffled rounds in one process per interpreter, with both extensions loaded
and exact title/byte equality checked before timing. All these workloads improve.

Initial median of the first three paired speedups (**new rmarc versus old rmarc**, not versus
pymarc), with five samples per process:

| Workload | Python 3.13 | Python 3.15 |
| --- | ---: | ---: |
| Real UTF-8 corpus: read | 1.56x | 1.83x |
| Real UTF-8 corpus: read + title | 1.64x | 1.64x |
| Real UTF-8 corpus: read + serialize | 1.26x | 1.47x |
| Repeated MARC-8 corpus: read | 2.51x | 3.12x |
| Repeated MARC-8 corpus: read + title | 2.53x | 2.80x |
| Repeated MARC-8 corpus: read + serialize | 1.78x | 1.85x |

Every workload in those first three pairs improved; these jobs do not establish performance of the
unusual-input fallback. Raw samples, module paths (in the newer harness runs),
corpus hashes, individual ratios and fixed compatibility results are retained in
[the implementation evidence](audits/2026-10-13-implementation/).

The original `d1cd1f6` Python files and already-built release extensions were
frozen under the ignored `target/audit-baseline/python/rmarc`. Baseline runs set
PYTHONPATH to that directory. Optimized 3.13 runs use the editable release build;
optimized 3.15 runs use the installed release wheel in the isolated environment.
All third-party installs require wheels. No mrrc source build was needed.

Each process uses five shuffled rounds after warmup, on the same two corpora as
the audit. Baseline and optimized processes run sequentially, three pairs per
interpreter; a fourth 3.13 pair exercises the final rare-input guards. The harness
checks that Rust is active and validates titles and serialized bytes against
pymarc before timing. The earlier three 3.13 pairs predate those extra harness
assertions; the final pair includes them. Raw data records this distinction.

Results are local wall-clock measurements on a shared Windows machine. Use paired
ratios, not a comparison of absolute times with the earlier audit: background
load changed appreciably. They establish gains on these workloads, not every
MARC dataset. No memory or cross-platform performance claim is made.

The fourth 3.13 pair is **confounded by load drift**: unchanged pymarc's real-corpus
read time rose from 0.744 to 1.510 seconds between the two processes. Its raw rmarc
ratios include apparent regressions (0.95x read, 0.71x roundtrip); do not hide or
interpret those as an isolated code effect. Both original files are retained.
`bench/compare_decoder.py` was added to check this: it imports a namespaced copy
of the original package alongside the changed package in one process and shuffles
both versions' jobs within each of seven rounds. It verifies exact title/byte
equality before timing. Only the baseline's Python import namespace is changed;
its original native extension is copied intact.

The initial before-1/before-2/before-3 exploratory files in `target/` are **not**
evidence: their live source could change between processes. Only the frozen-source
`baseline-*` and matching `optimized-*` artifacts belong in the results.

To reproduce a pair using the preserved local environments:

```bash
PYTHONPATH=C:/github/rmarc/target/audit-baseline/python .venv/Scripts/python.exe bench/audit_release.py --libraries pymarc rmarc --rounds 5 --output target/baseline-repeat.json
.venv/Scripts/python.exe bench/audit_release.py --libraries pymarc rmarc --rounds 5 --output target/optimized-repeat.json
```

For another checkout, build `d1cd1f6` and the changed revision with `maturin
develop --release` in separate environments, then run the same harness with each
environment's Python. Keep compiler/test processes out of the timing runs.

For the interleaved check (the script copies the frozen package into an ignored
target directory and rewrites only its Python import namespace):

```bash
.venv/Scripts/python.exe bench/compare_decoder.py --baseline-package target/audit-baseline/python/rmarc --output target/interleaved-313.json
../rmarc-audit-315/.venv/Scripts/python.exe bench/compare_decoder.py --baseline-package target/audit-baseline/python/rmarc --output target/interleaved-315.json
```

## Benchmark corrections

The deathmatch now calls `field.value()` for every library, loads XML input before
timing for every library, and checks title/field/JSON/XML results against pymarc.
Non-equivalent outputs are explicitly skipped rather than ranked as speedups.
The `py-cpuinfo` development dependency supplies the `cpuinfo` module that
pytest-benchmark 5.3 imports when saving JSON; its declared `py-cpuinfo2` dependency
does not supply that module in these environments.

## Validation

- Python 3.13 repository suite: **786 passed**, plus 12 subtests.
- Installed Windows Python 3.15 release wheel: **674 library tests passed**, plus
  12 subtests. This excludes the separate sample-app tests, explaining the count.
- Rust: **32 passed**. Ruff, Pyright (with the explicit .venv interpreter),
  rustfmt and Clippy pass.
- Differential audit: **120/120 fixture/option combinations match** on both
  interpreters, including exception details; targeted encoding/mutation
  regressions also pass on Rust and Python paths.
- The benchmark's full-corpus validation matches pymarc titles and serialized
  bytes for both corpora. No Linux/macOS or free-threaded validation was performed.
- The maintainer suite was copied into a separate directory and rerun without
  rmarc imports or external fixtures: **11 passed, 9 intended mrrc failures**.
- Corrected deathmatch (excluding the large-file scenario): **14 passed, 4 skipped**
  for non-equivalent mrrc outputs, with a successfully saved benchmark JSON report.

“Encoding” means converting a Record back into MARC bytes, usually through
`record.as_marc()`. A separate encoder optimization was step four; this work changes
decoding. Read-and-write jobs can still get faster because their read half is faster.
