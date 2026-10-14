# Optional I/O batching

`MARCReader(source, batch_bytes=256 * 1024)` enables byte read-ahead. The default
is `batch_bytes=0`, which keeps the original pymarc-compatible reader path.
The new keyword is rmarc-specific; it is not accepted by pymarc 5.4.0.

```python
from rmarc import MARCReader

reader = MARCReader(source, batch_bytes=256 * 1024)
try:
    for record in reader:
        if record is None:
            print(reader.current_exception)
        else:
            print(record.title)
finally:
    reader.close()
```

A positive integer selects the buffer capacity in bytes. This is **I/O
batching**, not eager parsing of a batch of records. The implementation uses
`io.BufferedReader`; a small adapter supports binary sources that have `read()`
and `close()` but no `readinto()`. Ordinary binary files and `BytesIO` use their
existing `readinto()` directly. There is no background thread or record queue.

## Getting maximum throughput

Start with **one buffer**, and measure a complete scan of your own data. In our
[Windows measurements](batching-measurements-2026-10-13.md), a 256 KiB buffer
improved reads from an unbuffered local file by about 19–20% for rmarc and 6–9%
for pymarc. Adding another buffer to an already-buffered file or `BytesIO` gave
no consistent benefit. Those results are starting points, not universal gains.

| Input or workload | Starting configuration |
| --- | --- |
| Local file, full scan | Set the buffer size on `open()`; keep `batch_bytes=0` |
| Unbuffered or expensive blocking source | Try rmarc `batch_bytes=256 * 1024` |
| Already-buffered file or stream | Keep its existing buffer; benchmark before adding another |
| `bytes` or `BytesIO` | Leave batching disabled; there is no external read latency to amortize |
| Read only a few records, then stop | Prefer the default or a smaller buffer to avoid unused read-ahead |

### Local files: the same recipe works in both libraries

Choose the buffer size when opening the file. This avoids stacking rmarc's
buffer on top of the buffer that normal binary `open()` already provides:

```python
from rmarc import MARCReader  # For pymarc, use: from pymarc import MARCReader

with open("records.mrc", "rb", buffering=256 * 1024) as source:
    reader = MARCReader(source)  # No batch_bytes keyword needed.
    count = sum(record is not None for record in reader)

print(count)
```

The example counts successfully decoded records. In production, handle `None`
results and inspect `reader.current_exception` as appropriate for your data.
Iteration keeps memory usage independent of the number of records; avoid
`list(reader)` unless you actually need to retain every record.

### Existing unbuffered sources: equivalent read-ahead

For rmarc, enable buffering on the reader:

```python
import rmarc

source = open("records.mrc", "rb", buffering=0)
reader = rmarc.MARCReader(source, batch_bytes=256 * 1024)
try:
    count = sum(record is not None for record in reader)
finally:
    reader.close()  # Also closes source.
```

For pymarc 5.4.0, wrap the source yourself. It does not accept `batch_bytes`:

```python
import io
import pymarc

source = open("records.mrc", "rb", buffering=0)
buffered = io.BufferedReader(source, buffer_size=256 * 1024)
reader = pymarc.MARCReader(buffered)
try:
    count = sum(record is not None for record in reader)
finally:
    reader.close()  # Closes buffered and source.
```

These examples use a raw file, which implements `readinto()`. For other source
types, Python's `BufferedReader` needs that interface. rmarc also adapts sources
with only binary `read()` and `close()` methods; pymarc users would need to supply
their own adapter or use a buffered interface provided by the source library.
Both approaches read ahead: use `reader.file_handle` for supported logical
position/seek operations, and leave the original source alone while reading.

### Tune the workload, not just the buffer size

Compare the default, 16 KiB, and 256 KiB on representative input. A larger
buffer means fewer source calls, but also more memory and more bytes fetched
before the first record is delivered. It does not accelerate field decoding.
Increase it further only if measurements justify the tradeoff.

Time repeated, complete scans that do the same work and verify the same record
count/output. Include your real processing in a second measurement: per-record
printing, database calls, or serialization can dominate any I/O improvement.
Keep per-record printing out of a parser-only benchmark. Separate warm-cache
results from cold storage or remote-source measurements; synthetic delays do
not establish real network performance.

The repository benchmark compares both libraries, two buffer sizes, and several
source types, including startup cost and early-stop read-ahead:

```bash
.venv/Scripts/python.exe bench/compare_batching.py --output target/batching.json
```

Run it without concurrent tests/builds. Its separate allocation-profiling phase
is slower than normal reading. The real corpus is used when available; otherwise
it falls back to the repository fixture.

## Behavior and ownership

- Each `next()` decodes one real Python `Record`. Mutable field and subfield
  lists, custom codec handlers, and reader decoding options work at that point,
  even if the bytes were fetched earlier. No future record's decoding warnings
  or handlers run early.
- `current_chunk`, `current_exception`, fatal-error termination, and recovery
  after nonfatal decoding errors still use the existing reader implementation.
- `file_handle` becomes the buffered stream. When supported, `tell()` reports
  the logical position and `seek()` works through that buffer. Do not
  read, seek, or replace the original source independently while buffering is
  active: its physical position may be ahead of the current record.
- The reader owns the buffer and its source. `close()` discards buffered bytes
  and closes the source; garbage collection of the buffer also closes it.
  Stopping early does not rewind the original source.
- Short reads are accumulated by the buffer. This intentionally differs from
  the unbuffered reader, which can treat a short read as a truncated record.
  Use blocking binary streams. I/O failures and their timing follow
  `BufferedReader`; they propagate instead of becoming MARC decoding errors.
- Extra memory consists primarily of the configured buffer and the current
  record. A record larger than the buffer is still read completely. No record
  count limit is needed because future Python record objects are not queued.
  The source may have its own buffering or already hold the whole input.
- Corrupt headers that cause negative read sizes follow `BufferedReader`'s
  errors, like ordinary buffered files. In particular, its rejection of reads
  below `-1` differs from `BytesIO`'s permissive negative-size behavior. The
  malformed header `00004` retains pymarc's `read(-1)` behavior and consumes
  the remainder of the source, so the memory bound for normal record framing
  does not apply to that case. The default reader is unchanged.

This option is useful for unbuffered sources or streams with expensive read
calls. It is not a promise of faster parsing on a normal buffered file or an
in-memory input. See the [measurements and validation](batching-measurements-2026-10-13.md)
and `bench/compare_batching.py` for measurements of those cases,
first-record latency, source calls, bytes fetched before early stop, and traced
Python allocation peaks. Timings are taken without instrumentation; the delayed
source in the benchmark is explicitly synthetic, not a network measurement.

## Does this make sense for pymarc?

Yes, as an I/O buffering option or documented recipe for costly streams. It
requires no change to record objects or to iteration. It is already possible
with pymarc's existing file-like input interface:

```python
import io
import pymarc

# raw_source must implement readinto(), as standard raw binary files do.
reader = pymarc.MARCReader(io.BufferedReader(raw_source, buffer_size=256 * 1024))
```

For local files, a user can also select the buffer size directly with
`open(path, "rb", buffering=256 * 1024)`. Ordinary `open(..., "rb")` already
buffers, so there may be little to gain. The upstream suggestion should start
with a buffering recipe and representative measurements, not a default change
or a claim that grouping Python parser calls makes decoding inherently faster.
A convenience keyword is worthwhile only if the documented stream behavior and
measured workloads justify it.

Primary references: [pymarc 5.4.0 reader source](https://gitlab.com/pymarc/pymarc/-/raw/v5.4.0/pymarc/reader.py)
and [Python buffered I/O documentation](https://docs.python.org/3/library/io.html#io.BufferedReader).
No upstream issue or message has been submitted.

## Difference from mrrc's parser batching

The inspected mrrc 0.9.2 checkout, commit
`b2e1140e7f1960d55ed47741ecc1d086afa60c3d`, collects record bytes, parses a batch
within one `py.detach`, and queues Rust outcomes with their source bytes in
[`batched_reader.rs`](../../mrrc/src-python/src/batched_reader.rs). Its limits are
200 records and a 300,000-byte threshold (the final record can exceed the byte
threshold). That amortizes transitions around Rust parsing. Neither pymarc's
Python decoder nor rmarc's direct Python-object construction can simply do the
same work without the GIL. A native batch parser would be a separate experiment.

Read-ahead is observable even when the record interface looks identical:
after one of three 42-byte records, pymarc leaves the caller's `BytesIO` at byte
42 while mrrc leaves it at byte 126. The standalone reproduction remains in
[`mrrc_compat_issues/test_api_differences.py`](../mrrc_compat_issues/test_api_differences.py).
The opt-in rmarc buffer also reads ahead, but reports the logical position
through `reader.file_handle` and leaves the default reader unchanged.

Tests in [`test_batch_reader.py`](../test_pymarc/test_batch_reader.py) cover
source ownership, logical positions/seeks, short reads, errors, early close,
lazy codec handlers, option changes, real mutable objects, and fixture parity.
Hypothesis varies batch boundaries, short reads, valid records, and damage in
both native and fallback modes. Compatibility for opt-in I/O behavior is with
pymarc over an equivalently buffered source; default behavior remains covered
separately.
