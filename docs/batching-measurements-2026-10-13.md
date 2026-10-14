# Optional buffering: measurements and validation

`MARCReader(..., batch_bytes=N)` batches source reads and decodes records lazily.
It is retained as an opt-in I/O optimization; `N=0` remains the default. The
[API contract](batching-compatibility.md) documents ownership, positions, short
reads, error timing, and the distinction from mrrc's native parser batching.

## Throughput

Windows x64 release builds, CPython 3.13.3 and 3.15.0, pymarc 5.4.0. The real
UTF-8 corpus contains 10,725 records / 14,346,341 bytes. These are warm-cache,
whole-file reading tests, not cold-disk throughput or read/write roundtrips.
The unchanged decoder does all parsing in every variant.

Each process warms the workloads and runs seven shuffled rounds with buffering
disabled, 16 KiB, and 256 KiB. Median speedup at 256 KiB (unbatched time / batched
time):

| Source | rmarc 3.13 | rmarc 3.15 | pymarc 3.13 | pymarc 3.15 |
| --- | ---: | ---: | ---: | ---: |
| Unbuffered local file | 1.191× | 1.203× | 1.087× | 1.056× |
| Normally buffered local file | 1.044× | 0.981× | 1.021× | 0.996× |
| BytesIO | 0.994× | 0.988× | 1.002× | 0.997× |

For rmarc's unbuffered file case, medians were 300.69 → 252.49 ms on 3.13 and
232.76 → 193.52 ms on 3.15. The 16 KiB buffer also improved that case, by
1.127× and 1.179× respectively. There is no consistent gain for already-buffered
sources, and an extra buffer can slightly reduce throughput. This supports
keeping the feature opt-in rather than changing normal reads.

The pymarc cases use its existing `MARCReader` with an explicitly wrapped
`io.BufferedReader`. No pymarc parser changes are required. For sources lacking
`readinto()`, the benchmark shares rmarc's private read adapter as a prototype;
it does not substitute rmarc's parser. The practical upstream suggestion is a
buffering recipe, followed by an optional convenience API only if warranted by
their own workloads. Grouping pure-Python record parsing does not acquire the
GIL-transition savings of mrrc's Rust batch parser.

## Read calls, early stopping, and memory

Source-interface reads for the real corpus fall from **21,451** to **877** at
16 KiB and **56** at 256 KiB, in both libraries. These counts are measured in a
separate instrumented scan: they are not OS syscall counts, especially when the
source already buffers internally. Timed scans contain no counting wrapper.

Stopping after the first record fetched 1,729 bytes from the source interface
with buffering disabled, versus 262,144 bytes with a 256 KiB buffer. First-record
timings, including source creation/opening and close, are recorded in the JSON;
they are noisy and show no consistent startup-latency improvement. Read-ahead
can cost extra work when callers stop early.

Peak traced Python allocation measurements are also separate from timing. The
3.15 comparisons added approximately 256 KiB at a 256 KiB setting. Absolute peaks
vary with source/interpreter state; one 3.13 unbuffered-file measurement was an
outlier at approximately 1.2 MiB. Keep the raw observations rather than treating
these as hard memory limits or process RSS. Native allocations are not fully
covered by `tracemalloc`. There is no queue of decoded records.

An additional **synthetic** source charges `time.sleep(0.0001)` per read of a
200-record MARC-8 corpus. Its source calls drop from 401 to 2 at 256 KiB. It
shows large gains (rmarc 53.7–55.3×, pymarc 7.1–9.7×), but these are deliberately
constructed read-latency results, not network benchmarks. Windows scheduling
can make each sleep longer than the requested 100 microseconds. Do not advertise
those ratios as general parser speedups.

## Tests and reproduction

- **853 tests passed on 3.13**, including sample-app tests; **741 library tests
  passed on the rebuilt/installed 3.15 release wheel**. Both report 12 passing
  subtests and 52 warnings from intentionally malformed fixtures.
- The new batching module contributes **43 tests** and **450 successful
  Hypothesis examples per interpreter**, on top of the prior 2,100 generated
  codec examples. Tests cover default behavior, buffering boundaries, short
  reads, records larger than the buffer, existing fixtures, malformed records,
  fatal/nonfatal errors, lazy decoding, option changes, ownership/close, logical
  seeking, real mutable objects, and custom stream `read()` overrides.
- Pyright and Ruff pass. Rust parsing and serialization were not changed in
  this step; the preceding encoder work passed 33 Rust tests. No CI was
  dispatched and this does not establish other-platform wheel support.

Raw measurements: [Python 3.13](audits/2026-10-13-batching/interleaved-313.json)
and [Python 3.15](audits/2026-10-13-batching/interleaved-315.json). Files contain
individual rounds, hashes and sizes of the corpora, first-record timings,
source-call counts, and traced allocation peaks. The benchmark preceded a small
constructor hardening change to preserve subclasses' `read()` overrides; the
measured built-in stream types and adapter paths retain the same behavior.

From Git Bash, with the release extension installed:

```bash
.venv/Scripts/python.exe bench/compare_batching.py --output target/batching.json
.venv/Scripts/python.exe -m pytest test_pymarc/test_batch_reader.py \
  --hypothesis-show-statistics
.venv/Scripts/python.exe -m pytest
```

The benchmark uses the real corpus if present and otherwise uses `test.dat`.
Run it without concurrent builds or tests. Its allocation profiling phase is
substantially slower than ordinary reading. The generated tests require no
external corpus or network.
