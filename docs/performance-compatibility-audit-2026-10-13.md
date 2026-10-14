# Python 3.15 release: performance and compatibility audit

Follow-up: the first three steps below are now implemented. See the
[implementation results](decoder-improvements-2026-10-13.md). This document retains
the original baseline measurements and pre-fix findings.

## Decision

rmarc is substantially faster than current pymarc, but does not yet exactly
match its behavior. Fix the confirmed encoding problems before claiming full
pymarc compatibility for the release. Keep Python's mutable Record/Field model
as the default. mrrc is faster, but its behavior is observably different.

This investigation changes no production implementation. It adds reproducible
audit scripts and records measurements, counterexamples, and an implementation
plan. The lookup experiment is an in-process prototype only.

## Versions and validation

- Checkout: `d1cd1f6`, rmarc 5.3.1; PyPI also reports 5.3.1.
- Latest PyPI pymarc: **5.4.0**, installed and used as the reference. The bundled
  `pymarc_src` is **5.3.1** and is insufficient to establish latest compatibility.
- Latest PyPI mrrc: **0.9.2**, installed published Windows CPython 3.13 wheel.
- Competitor cloned to `C:/github/mrrc`, inspected at
  `b2e1140e7f1960d55ed47741ecc1d086afa60c3d`. This is a source-inspection reference;
  performance measurements use the published wheel, not a build of HEAD.
- Windows 11 AMD64; existing `.venv`: CPython **3.13.3**. Rebuilt rmarc's extension
  with `maturin develop --release --skip-install` before measurements.
- Separate `C:/github/rmarc-audit-315/.venv`: CPython **3.15.0**. Built and installed
  this checkout's release wheel. Dependencies installed with `--only-binary :all:`.
  This is a local project build, not evidence that a published cp315 wheel exists.
- No published Windows cp315 mrrc wheel was available. No competitor source build
  or PyO3 override was attempted. All three-way comparisons use the same 3.13 VM.
- 721 repository Python tests passed on 3.13, including the sample app;
  609 library tests passed against the installed 3.15 wheel (12 subtests also
  passed in each run). `make rust-test`: 37 passed.
- Downloaded pymarc 5.4.0's actual sdist, copied its tests outside this checkout,
  and redirected imports to rmarc. On both 3.13 and 3.15: 174 tests passed;
  three subtest failures came from reopening `NamedTemporaryFile` on Windows.
  Running the original suite against pymarc reproduced the same three failures.
  These are a shared platform-test issue, not evidence of a rmarc regression.
- Linux/macOS wheels, free-threaded builds, optional accelerator combinations,
  and the full interpreter matrix were not validated in this investigation.

Sources: [pymarc release](https://pypi.org/project/pymarc/5.4.0/),
[mrrc release](https://pypi.org/project/mrrc/0.9.2/),
[mrrc source](https://github.com/dchud/mrrc),
[rmarc release](https://pypi.org/project/rmarc/5.3.1/).

## Measured speed

Seven samples per job, one warmup, reproducibly shuffled/interleaved job order,
median wall-clock time. Each job starts a new reader and consumes every record;
roundtrip means read and serialize every record. Data is already in memory, so
these isolate processing from filesystem variability. GC remains enabled.
These are local measurements, not portable guarantees or confidence intervals.
There are noticeable scheduling outliers; raw samples are retained.

The real corpus is `data/Computer.Files.2019.part01.utf8`: 10,725 distinct records,
14,346,341 bytes, all UTF-8 leaders. The synthetic corpus repeats the ten records
in `test.dat` 100 times: 1,000 records, 659,100 bytes, all MARC-8 leaders. Hashes
are in the JSON. Repetition, encoding, and record shape all affect the results.

### Real corpus, Python 3.13

| Workload | pymarc 5.4 | rmarc | mrrc 0.9.2 | pymarc / rmarc time |
| --- | ---: | ---: | ---: | ---: |
| Read all | 648.0 ms | 336.2 ms | 91.2 ms | 1.93x |
| Read + title | 671.0 ms | 361.3 ms | 94.0 ms* | 1.86x |
| Read + serialize | 1,116.0 ms | 599.8 ms | 141.7 ms* | 1.86x |

rmarc reads 31,904 records/s; mrrc reads 117,623 records/s, or 3.69x rmarc.
For the repeated MARC-8 corpus, read times are 140.4 / 36.0 / 6.2 ms respectively:
rmarc is 3.90x pymarc; mrrc is 5.78x rmarc. One headline ratio is misleading.

`*` These operations do not return identical results in mrrc; see below.
Do not market their timings as equivalent-output speedups.

### Python 3.15, same rmarc source and pymarc version

| Workload | pymarc | rmarc | Speedup |
| --- | ---: | ---: | ---: |
| Real corpus: read | 677.6 ms | 315.0 ms | 2.15x |
| Real corpus: read + title | 681.5 ms | 332.7 ms | 2.05x |
| Real corpus: roundtrip | 1,106.4 ms | 568.8 ms | 1.95x |
| Repeated MARC-8: read | 131.9 ms | 34.9 ms | 3.78x |

Do not infer a precise interpreter speedup from separate runs with this noise.
The useful conclusion is that the native speed advantage survives 3.15.

## Compatibility: what really matches

rmarc matched pymarc's titles and serialized bytes for all 10,725 real-corpus
records and all ten source records in the synthetic corpus.

The differential fixture audit compares record dictionaries, serialized-byte
hashes, warning category/message, exception type, and UnicodeDecodeError details
across 20 binary fixtures and six reader configurations. **110/120 combinations
match exactly**. All ten failures in this fixture matrix are exception-detail
differences, not different successfully decoded field values. Logging/stderr
text and all possible mutations are outside that fixture comparison.

Passing these fixtures and upstream tests is not sufficient: targeted probes
found the following gaps in the current accelerated implementation, reproduced
on both 3.13 and 3.15:

| Case | pymarc 5.4 | rmarc | Priority |
| --- | --- | --- | --- |
| UTF-8 `ignore`, legitimate U+FFFD plus invalid byte | Keeps legitimate U+FFFD | Deletes it | Before release: data loss |
| `backslashreplace` / `surrogateescape` | Requested Python codec behavior | Behaves like `replace` | Before release: silent substitution |
| `file_encoding="utf-8"`, leader lacks `a` | Unicode subfield text | Raw `bytes` inside Unicode Field | Before release: wrong public type |
| Non-ASCII control field with default legacy encoding | Latin-1 decoded control data | MARC-8 conversion; probe `é` becomes empty | Before release: data loss |
| Strict UTF-8 / invalid directory errors | Correct `.object`, `.start`, `.end`, `.reason` | Synthetic positions and different error payload | Compatibility repair |
| `Field(tag="+01")` or `" 1"` | Preserves string | Normalizes to `"001"` | Sync with 5.4 behavior |
| `Field(tag=None)` | Tag `"None"` | TypeError | Sync with 5.4 behavior |

Relevant implementation: `src/marc_codec.rs::decode_utf8` removes *every* U+FFFD
for ignore, and treats all other handler names as replacement. Its mode selection
recognizes UTF-8 from the leader/force flag, but not the explicit encoding alone.
The control-field branch uses the subfield MARC-8 mode. Python's adapter then
decides that UTF-8 values need no further decoding. `record.py` manufactures
UnicodeDecodeError payloads from Rust error strings.

The safest first repair is an exact Python-codec slow path for unusual/error
cases, with the normal valid-byte path kept fast. Unknown/custom error handlers
must follow Python's codec registry. Add focused differential regressions before
changing the Rust branches; preserve reader recovery and `current_exception`.

## mrrc: same-looking API, different semantics

Confirmed against the published 0.9.2 wheel, not inferred merely from Rust:

| Operation | pymarc and rmarc | mrrc |
| --- | --- | --- |
| `get_fields("650", "245")` | Record order | Groups by selector order |
| `get_fields("650", "650")` | Each matching field once | Duplicated results |
| Missing `field["z"]` | KeyError | None |
| `record.fields` | Mutable list | Method |
| `field.subfields` | Mutable list | Method |
| `get_fields()` | The actual fields list | Newly assembled handles |
| `record["245"]["a"] = value` | Updates record | Also updates record |
| Title with 245$a and $b | Includes subtitle | Probe omits $b |

mrrc title results differed on 3/10 synthetic source records and 3,436/10,725 real
records. For example, pymarc/rmarc return `Perl : programmer's reference /`;
mrrc returns `Perl :`.

mrrc serialization differed on all ten synthetic source records (leader encoding
flag) and 3,913 real records. Re-decoding the real outputs with pymarc and comparing
field multisets showed **field ordering only** in all 3,913 cases, not lost field
contents. This still matters to exact roundtrip and order-sensitive consumers.

The source now has live field handles; it would be wrong to claim that *all*
mutations are lost. These confirmed differences establish that it is not a
behaviorally identical drop-in replacement. Some are deliberate API choices,
and Rust itself does not require any of them.

## Where the time goes, and what is already optimized

Already present: bypassing Field constructors with `__new__`, interning tags and
subfield codes in Rust, Rust MARC-8 decoding, optional orjson/lxml, direct list
iteration during serialization. Recommending these again would not help.

Remaining work visible in `record.py::_decode_marc_rust` and `marc_codec.rs`:
Rust creates nested Python tuples/lists, then Python walks them again to allocate
Fields, Indicators and Subfields. The adapter repeats leader validation and
checks uncommon encoding/code cases inside the normal subfield loop.

Unprofiled single-record microbenchmarks on 3.13: full Record ~42.8 us versus
raw codec ~25.8 us. Raw codec omits final objects and validation, so it is a
lower-work diagnostic, **not a replacement-library benchmark**. It suggests a
material adapter cost but not that all that cost can disappear.

cProfile on 1,000 records places ~76 of ~83 instrumented ms inside the Rust
decode adapter, with ~21 ms in its raw native call. Instrumentation inflates
Python costs; these percentages are not an unprofiled Amdahl estimate. File-read
calls are small in this BytesIO profile, so batching is not the first hypothesis.

Borrowing pymarc 5.4's six generic lookup methods in an isolated experiment
reduces preparsed-title access from 1.77 to 0.57 us on 3.13, and 1.53 to 0.44 us
on 3.15. Read-plus-title improves only ~1% / ~0.5% in these microbenchmark medians,
inside the noise. Treat lookup adoption as a proven micro-optimization, not a
proven bulk throughput win.

mrrc's inspected architecture provides useful ideas:

- `src-python/src/batched_reader.rs`: bounded batches, one GIL detach per batch.
- `src-python/src/backend.rs`: native buffered path I/O and borrowed immutable
  bytes, avoiding a whole-input copy at reader creation.
- `mrrc/__init__.py`: native title/access operations and field handles produced
  on access, instead of eagerly building every Python field during reading.

These explain plausible advantages; this audit did not independently measure
the contribution of each technique.

## Ordered implementation plan

1. **Make correctness and measurement the gate.** Fix the encoding/type failures
   above, sync 5.4 tag normalization, and add differential tests. Refresh upstream
   tests with provenance. Keep reference cases for mutation aliases, field order,
   RawField, duplicate selectors, custom handlers, and malformed-record recovery.
   Correct the existing deathmatch: field access compares `str(field)` with
   `field.value()`; XML includes file opening for two libraries but not mrrc;
   title assertions check length only. Its JSON-output run also currently fails
   importing `cpuinfo`, after benchmark execution. Resolve that dependency issue.

2. **Adopt upstream's single-pass lookup implementations.** Small reviewable
   change, established semantics, measured ~3x title-access microbenchmark win.
   Test subclass overrides and aliasing; don't add a tag index that can go stale
   when callers mutate the public lists directly. No promised bulk gain.

3. **Reduce decoder allocation with the same public objects.** First prototype
   a printable-ASCII MARC-8 shortcut (only bytes 0x20..0x7e, no escapes/controls),
   and borrowed valid-UTF-8 decoding without `data.to_vec()`/intermediate owned
   String. Current MARC-8 always traverses mapping tables and normalizes even
   printable ASCII. Then prototype returning actual Python Fields/Subfields
   directly from native decoding, eliminating intermediate tuple trees and a
   second walk. Keep unusual encodings and malformed input on a proven fallback.
   Benchmark each independently; Python object creation via PyO3 can still be
   expensive, so moving the loop alone is not proof of a win.

4. **Improve writing separately.** `Record.as_marc()` still calls every Python
   `Field.as_marc()` and constructs per-field bytes; Rust only assembles the
   directory/record. Prototype one buffered native encode pass for standard
   Fields, preserving custom Field serialization overrides and RawField behavior.
   Verify exact bytes and mutations before accepting the fast path.

5. **Only then investigate bounded batching or lazy decoding.** Start with an
   explicit bulk/projection API or immutable bytes input. Reading ahead changes
   stream position, latency, `current_chunk`, and when errors are observed;
   a lazy fields proxy changes list identity, direct edits, and exception timing.
   Do not trade away the drop-in contract to win a count-only benchmark. A
   separate opt-in scan API can compete on those workloads without redefining
   Record/Field semantics.

Acceptance targets are engineering gates, not forecast gains: seek at least 10%
less end-to-end time on the relevant real workload, repeat across three fresh
processes on 3.13 and 3.15, and investigate any >5% regression elsewhere. For the
ASCII shortcut, require a clear improvement on MARC-8 data and no meaningful
UTF-8 regression. Gate every optimization on exact expected outputs, not count
alone. Track peak memory and first-record latency for batching/laziness.

Before publishing broader speed claims, add non-ASCII MARC-8, a second real
collection, large/repeated-field records, edit-and-write jobs, actual file streams,
optional-accelerator modes, and allocation/RSS measurements. The current audit
supports the ranking on two corpora, not a universal fastest-library claim.

## Reproduction and evidence

Run from the repository root in Git Bash. Use a release extension, not `make dev`'s
debug build. Do not benchmark concurrently with compiler/test jobs.

```bash
VIRTUAL_ENV="$PWD/.venv" .venv/Scripts/python.exe -m maturin develop --release --skip-install
.venv/Scripts/python.exe bench/audit_release.py --output target/audit-313.json
.venv/Scripts/python.exe bench/audit_compat.py --output target/audit-compat-313.json
.venv/Scripts/python.exe bench/audit_hypotheses.py --output target/audit-hypotheses-313.json

# Existing isolated 3.15 environment, after installing the local release wheel:
../rmarc-audit-315/.venv/Scripts/python.exe bench/audit_release.py --libraries pymarc rmarc --output target/audit-315.json
../rmarc-audit-315/.venv/Scripts/python.exe bench/audit_compat.py --libraries pymarc rmarc --output target/audit-compat-315.json
```

Raw timing samples, interpreter metadata, fixture hashes, compatibility failures,
and prototype results are saved in [audits/2026-10-13](audits/2026-10-13/).
`audit-parity-313.json` and `audit-mrrc-roundtrip-313.json` additionally record
full-corpus output comparisons; the latter classifies differences after reparsing
mrrc output with pymarc and comparing field multisets.

The 3.15 build command used the 3.15 environment's own maturin entry point:

```bash
../rmarc-audit-315/.venv/Scripts/python.exe -m maturin build --release -i C:/github/rmarc-audit-315/.venv/Scripts/python.exe --out target/audit-wheels
uv pip install --python ../rmarc-audit-315/.venv/Scripts/python.exe --only-binary :all: target/audit-wheels/rmarc-5.3.1-cp315-cp315-win_amd64.whl
../rmarc-audit-315/.venv/Scripts/python.exe -m pytest test_pymarc -q
```
