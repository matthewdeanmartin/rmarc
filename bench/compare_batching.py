"""Measure opt-in I/O batching and the equivalent buffering recipe for pymarc.

Run alone: python bench/compare_batching.py --output target/batching.json
Timings do not include instrumentation, corpus validation, or tracemalloc.
The delayed source is synthetic: 100 microseconds charged per read call.
"""

import argparse
import hashlib
import importlib.metadata
import io
import json
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import pymarc
import rmarc
from rmarc.reader import _ReadAdapter


class CountedSource:
    def __init__(self, stream, delay=0):
        self.stream = stream
        self.delay = delay
        self.calls = 0
        self.bytes_read = 0

    def read(self, size=-1):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        data = self.stream.read(size)
        self.bytes_read += len(data)
        return data

    def close(self):
        self.stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=7)
    args = parser.parse_args()
    assert rmarc.record._HAS_RUST_CODEC
    path = Path("data/Computer.Files.2019.part01.utf8")
    if not path.exists():
        path = Path("test_pymarc/test.dat")
    data = path.read_bytes()
    delayed_data = Path("test_pymarc/test.dat").read_bytes() * 20
    variants = (0, 16 * 1024, 256 * 1024)
    cases = ("bytesio", "buffered_file", "unbuffered_file", "synthetic_delayed_read")

    def source(case):
        if case == "buffered_file":
            return path.open("rb")
        if case == "unbuffered_file":
            return path.open("rb", buffering=0)
        if case == "synthetic_delayed_read":
            return CountedSource(io.BytesIO(delayed_data), delay=0.0001)
        return io.BytesIO(data)

    def reader(module, stream, batch_bytes):
        if module is rmarc:
            return module.MARCReader(stream, batch_bytes=batch_bytes)
        if batch_bytes:
            raw = stream if isinstance(stream, (io.BufferedIOBase, io.RawIOBase)) else _ReadAdapter(stream)
            stream = io.BufferedReader(raw, buffer_size=batch_bytes)
        return module.MARCReader(stream)

    def scan(module, case, batch_bytes, first_only=False, counted=False):
        stream = source(case)
        if counted:
            stream = CountedSource(stream)
        current = reader(module, stream, batch_bytes)
        count = 0
        try:
            for record in current:
                assert record is not None
                count += 1
                if first_only:
                    break
        finally:
            current.close()
        if counted:
            return count, stream.calls, stream.bytes_read
        return count

    # Validate exact output against pymarc before timing any variants.
    for corpus in (data, delayed_data):
        expected = [r.as_marc() for r in pymarc.MARCReader(corpus)]
        for size in variants:
            assert [r.as_marc() for r in rmarc.MARCReader(corpus, batch_bytes=size)] == expected

    jobs = []
    for module in (rmarc, pymarc):
        for case in cases:
            for size in variants:
                count = scan(module, case, size)
                jobs.append(
                    (
                        module,
                        case,
                        size,
                        {
                            "library": module.__name__,
                            "source": case,
                            "batch_bytes": size,
                            "records": count,
                            "seconds": [],
                        },
                    )
                )
    rng = random.Random(315)  # noqa: S311 - reproducible benchmark order
    for _ in range(args.rounds):
        rng.shuffle(jobs)
        for module, case, size, row in jobs:
            start = time.perf_counter()
            count = scan(module, case, size)
            row["seconds"].append(time.perf_counter() - start)
            assert count == row["records"]

    for module, case, size, row in jobs:
        first_times = []
        for _ in range(args.rounds):
            start = time.perf_counter()
            scan(module, case, size, first_only=True)
            first_times.append(time.perf_counter() - start)
        row["first_record_seconds"] = first_times
        # Counts and memory are measured separately: wrappers/profilers distort timings.
        _, row["source_read_calls"], row["source_bytes_read"] = scan(module, case, size, counted=True)
        _, row["first_record_source_reads"], row["first_record_source_bytes"] = scan(
            module, case, size, counted=True, first_only=True
        )
        tracemalloc.start()
        scan(module, case, size)
        _, row["peak_traced_python_bytes"] = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"Measured {module.__name__}: {case}, batch_bytes={size}", flush=True)

    rows = sorted([row for _, _, _, row in jobs], key=lambda r: (r["library"], r["source"], r["batch_bytes"]))
    medians = {(r["library"], r["source"], r["batch_bytes"]): statistics.median(r["seconds"]) for r in rows}
    for row in rows:
        row["speedup"] = medians[row["library"], row["source"], 0] / statistics.median(row["seconds"])
    report = {
        "python": sys.version,
        "pymarc_version": importlib.metadata.version("pymarc"),
        "rmarc_version": rmarc.__version__,
        "corpus": {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "synthetic_corpus": {
            "bytes": len(delayed_data),
            "sha256": hashlib.sha256(delayed_data).hexdigest(),
            "delay_seconds_per_read": 0.0001,
        },
        "benchmarks": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(
            row["library"],
            row["source"],
            row["batch_bytes"],
            f"{row['speedup']:.3f}x",
            f"{row['source_read_calls']} reads",
        )


if __name__ == "__main__":
    main()
