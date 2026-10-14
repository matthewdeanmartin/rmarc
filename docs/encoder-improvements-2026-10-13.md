# MARC serialization improvements and generated compatibility tests

The writer change is retained: repeated measurements show a useful improvement
over commit `1d37798`, which already contains the earlier decoder optimizations.
This speeds `Record.as_marc()`—assembling MARC21 bytes. Character encodings and
the per-field serialization protocol are unchanged.

## Changes

The native assembler previously formatted every directory entry into a new
String, copied field bytes into a growing buffer, copied that into another
buffer, then copied the whole result into Python bytes. It now writes decimal
directory lengths/offsets without allocating Strings and copies each field
directly into the final Python bytes allocation. Padding remains a minimum
width: oversized values are never silently truncated. Python also reuses an
already-normalized three-digit ASCII tag instead of converting it to an integer
and formatting it again.

Every field's `as_marc()` is still called in order, including subclass overrides
and `RawField`'s no-argument serializer. The leader's existing encoding update,
raw bytes, field/subfield order, and Python fallback remain in place.

## Measurements

Windows x64, release extensions, CPython 3.13.3 and 3.15.0. Each benchmark loads
the frozen baseline and changed extension into the same process, checks output
against each other and pymarc 5.4.0, warms each workload, then runs seven shuffled
rounds. Two final runs per interpreter produced the following ranges of median
speedup ratios (baseline time / changed time):

| Corpus and operation | Python 3.13 | Python 3.15 |
| --- | ---: | ---: |
| Real UTF-8 corpus: serialization only | 1.49× | 1.51–1.52× |
| Real UTF-8 corpus: read + serialize | 1.23× | 1.20–1.24× |
| Repeated MARC-8 fixture: serialization only | 1.41–1.57× | 1.56–1.60× |
| Repeated MARC-8 fixture: read + serialize | 1.01–1.37× | 1.19–1.27× |

The real corpus contains 10,725 records (14,346,341 bytes); the repeated fixture
contains 1,000 records (659,100 bytes). Serialization-only timings use records
parsed before timing; roundtrip timings include reading and serializing all
records. These are throughput workloads, not first-record latency measurements.

Machine load changed absolute timings substantially, including roughly doubling
both variants' times in one 3.13 run. Interleaving helps compare them under that
load; the real-corpus serialization ratios were consistent. The small 3.13
roundtrip workload was noisy, so do not promise a stable improvement for it.
Do not use these runs to compare Python versions or claim an overall victory
over mrrc. No competitor timing was repeated for this writer-only change.

Raw samples, corpus hashes, extension hashes, and module paths:

- [3.13 final](audits/2026-10-13-encoder/interleaved-final-313.json) and
  [repeat](audits/2026-10-13-encoder/interleaved-repeat-313.json).
- [3.15 final](audits/2026-10-13-encoder/interleaved-final-315.json) and
  [repeat](audits/2026-10-13-encoder/interleaved-repeat-315.json).
- [Initial 3.13 trial](audits/2026-10-13-encoder/interleaved-313.json), retained
  for completeness, preceded a semantics-preserving Clippy cleanup.

## Verification

[`test_hypothesis_codec.py`](../test_pymarc/test_hypothesis_codec.py) adds seven
property tests, each run with native acceleration and the Python fallback.
Each combination runs 150 successful examples: **2,100 generated examples per
interpreter**. The oracle is installed pymarc 5.4.0, not our copied source tree.

The properties cover Unicode writes/reads, ordered mutable lists and lookups,
legacy encoding bytes or exact errors, tags changed after construction, malformed
UTF-8 with five error handlers, raw binary fields, and reader chunk/error/stream
state. Explicit cases protect custom serializers, numeric width boundaries, and
oversized records. Hypothesis initially exposed an incorrect assumption in the
new test: empty records serialize but pymarc rejects reading them. The final
test explicitly verifies both behaviors. No rmarc discrepancy was found in the
completed generated run; this is bounded coverage, not a universal equivalence
claim.

Final validation:

- Python 3.13: **810 passed**, 12 subtests passed, including sample-app tests.
- Python 3.15 rebuilt/installed release wheel: **698 library tests passed**,
  12 subtests passed. Each suite reports 50 warnings from existing fixture cases.
- Rust: **33 passed**. Ruff, Pyright, Clippy, rustfmt, lock and diff checks pass.
- An additional one-off comparison checked 45 raw native-API combinations
  (short/Unicode tags and field sizes through 100,000) against the frozen
  extension; all bytes matched.
- Standalone mrrc suite: **12 passed, 10 deliberately failing reproductions**.
  The added case demonstrates read-ahead, labeled as an API tradeoff.

Hypothesis is now included in wheel-test and matrix-test dependencies; it was
already a development dependency. The 3.15 environment installed Hypothesis
6.169.0 from a published wheel; 3.13 used 6.168.5. No CI runs were dispatched.
Local Windows testing does not establish other-platform release-wheel support.

## Reproduction

Freeze the baseline package at `1d37798`, including its release extension built
for the Python being measured. The local copies used here are in the ignored
`target/encoder-baseline/rmarc/` directory. Rebuild the changed release extension
before timing. Run benchmarks alone, without simultaneous builds or tests:

```bash
.venv/Scripts/python.exe bench/compare_encoder.py \
  --baseline-package target/encoder-baseline/rmarc --baseline-label 1d37798 \
  --output target/encoder-comparison.json
.venv/Scripts/python.exe -m pytest test_pymarc/test_hypothesis_codec.py \
  --hypothesis-show-statistics
.venv/Scripts/python.exe -m pytest
cargo test
```

The larger corpus is optional and is skipped if absent. The small benchmark and
all generated tests use only repository fixtures or in-memory data. Hypothesis
prints a minimized failing example and retains examples in `.hypothesis` for
replay; a particular run can also be seeded with `--hypothesis-seed=315`.

The subsequent optional I/O batching implementation is documented in the
[batching contract and pymarc discussion](batching-compatibility.md). The writer
measurements above precede that addition; default reader behavior remains unchanged.
