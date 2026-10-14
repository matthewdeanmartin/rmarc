# Compatibility, consumer examples, and local performance checks

## Stateful compatibility and I/O failures

`test_pymarc/test_stateful_compat.py` uses Hypothesis state machines to compare
pymarc and rmarc after each operation in an editing history. Actions add/remove
fields, retain and edit field/list references, change leader status, replace
subfields through slices, and serialize/reload records. Old references remain
under observation after removals and reloads. Both native and fallback codecs
run 80 generated histories with up to 35 steps each. Failures produce a minimized
sequence that can become a small regression test.

`test_pymarc/test_io_faults.py` checks eleven ordinary failure scenarios:
read errors at record headers/bodies, with and without buffering; a disk-full
write before output or partway through the second record; and a close failure.
Assertions cover exception propagation, reader state, written prefixes, and
stream ownership. Buffered pymarc uses `io.BufferedReader` as its reference.

Both files run in ordinary pytest/CI. They add no runtime dependencies.

## Typed examples

Yes: consumer typing tests are checks of realistic example code. The existing
book-tracking GUI already has application tests. `examples/book_catalog.py`
adds small standalone book workflows that need no GUI, network, or sample-app
installation: create records, replace subjects, import with error reporting,
and export while retaining caller-owned streams.

```bash
make check-examples
```

This runs strict mypy on the examples, Pyright, Pyrefly, and three behavioral
tests of those same examples. The checks are included in `make ci`, `make all`,
`make check-all`, `make build`, `make build-release`, and the CI lint job.
MARCReader's iteration annotations now expose `Record | None` to consumers.
The library as a whole is not yet strictly typed.

## Local performance regression gate

Use the existing **pytest-benchmark** dependency; no new performance library
or custom timing/comparison engine is introduced. The nearby pycodetags project
provided a useful example of local repeated measurements; this gate uses
pytest-benchmark's own saved baselines and median regression checks.

First build a known-good version in release mode and record a baseline:

```bash
uv run maturin develop --release --skip-install
make perf-baseline
```

After changing code, rebuild and compare:

```bash
uv run maturin develop --release --skip-install
make perf-check
```

Four workloads cover decoding, decoding with `batch_bytes`, encoding, and
read/write round trips over 1,000 records from the checked-in fixture. Each
uses three warmup rounds and fifteen measured rounds of three iterations.
This is a small repeatable gate, not a substitute for the larger real-corpus
benchmarks or a measure of cold storage speed.

The default gate fails when a median is more than **15% slower**. Baselines are
saved under ignored `target/performance/`; checks use the latest saved baseline
for the current platform, without replacing it. To select a particular saved
run, use the number printed by pytest-benchmark:

```bash
make perf-check PERF_BASELINE=0002
```

`PERF_OPTIONS` passes additional pytest-benchmark options. A missing baseline
fails rather than silently accepting the current run. Baselines from a different
machine, Python, selected CPU, or fixture are rejected. Bump the workload version
in `bench/regression/conftest.py` when changing what is measured.

Run on an idle machine with a consistent power mode and the same release-build
settings. The benchmark process pins itself to the first allowed logical CPU
on Windows/Linux, preventing migration between different core types. This only
affects that process and its children. Other platforms currently run without
pinning. Frequency/power changes and competing work can still affect timings;
a failure warrants investigation, not automatic baseline replacement.

These timing targets are **excluded from normal tests and all CI/build quality
gates**. The regression suite explicitly rejects GitHub Actions and xdist workers.
No timing tests were added to GitHub workflows.

## Local validation, 2026-10-13

- Stateful, fault-injection, and example tests: 16 passed.
- Full Python 3.13 suite: 897 passed plus 12 subtests.
- Rebuilt Python 3.15 release wheel: 785 library tests passed plus 12 subtests.
- Both complete runs emitted the same 52 expected malformed-input warnings.
- Examples: mypy, Pyright, and Pyrefly passed.
- Local performance gate: all four workloads passed against a same-build,
  CPU-pinned baseline; median differences were approximately 1–5%.
- An intentionally impossible baseline failed the gate as expected.
- The GitHub Actions guard rejected collection before any timing ran.

Initial unpinned runs varied substantially on this hybrid-core Windows machine.
Pinning stabilized this comparison without raising the 15% threshold. The local
baseline is deliberately not committed as a universal speed requirement.
