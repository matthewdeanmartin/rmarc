"""Compare moving bytes, framing records, and constructing compatible objects.

Warm-cache diagnostics, not interchangeable workloads or an additive profile.
Run alone: python bench/performance_floor.py --output target/performance-floor.json
"""

import argparse
import cProfile
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import rmarc
from rmarc._rmarc import decode_marc_fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/Computer.Files.2019.part01.utf8"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=9)
    args = parser.parse_args()
    assert rmarc.record._HAS_RUST_CODEC
    data = args.corpus.read_bytes()
    block_size = 256 * 1024
    chunks = []
    offset = 0
    while offset < len(data):
        size = int(data[offset : offset + 5])
        assert size >= 25 and offset + size <= len(data)
        chunk = data[offset : offset + size]
        assert chunk[-1] == 29
        chunks.append(chunk)
        offset += size
    assert offset == len(data)
    counts = {"records": 0, "fields": 0, "data_fields": 0, "subfields": 0, "value_characters": 0}
    for record in rmarc.MARCReader(data):
        assert record is not None
        counts["records"] += 1
        counts["fields"] += len(record.fields)
        for field in record.fields:
            if field.control_field:
                counts["value_characters"] += len(field.data)
            else:
                counts["data_fields"] += 1
                counts["subfields"] += len(field.subfields)
                counts["value_characters"] += sum(len(s.value) for s in field.subfields)
    assert counts["records"] == len(chunks)

    def readinto_blocks():
        buffer = bytearray(block_size)
        total = 0
        with args.corpus.open("rb", buffering=0) as stream:
            while size := stream.readinto(buffer):
                total += size
        return total

    def read_blocks():
        total = 0
        with args.corpus.open("rb", buffering=0) as stream:
            while block := stream.read(block_size):
                total += len(block)
        return total

    def read_all():
        return len(args.corpus.read_bytes())

    def copy_memory():
        # bytes(data) or BytesIO(data).read() can return the original object!
        # A memoryview forces a real copy into a new bytes allocation here.
        return len(bytes(memoryview(data)))

    def frame_memory():
        position = count = 0
        while position < len(data):
            length = int(data[position : position + 5])
            position += length
            count += 1
        assert position == len(data)
        return count

    def frame_file():
        count = 0
        with args.corpus.open("rb", buffering=block_size) as stream:
            while first5 := stream.read(5):
                length = int(first5)
                chunk = first5 + stream.read(length - 5)
                assert len(chunk) == length and chunk[-1] == 29
                count += 1
        return count

    def parse_memory(to_unicode=True):
        count = 0
        for record in rmarc.MARCReader(data, to_unicode=to_unicode):
            assert record is not None
            count += 1
        return count

    def parse_file():
        with args.corpus.open("rb", buffering=block_size) as stream:
            count = 0
            for record in rmarc.MARCReader(stream):
                assert record is not None
                count += 1
        return count

    def native_fields():
        count = 0
        for chunk in chunks:
            _, fields = decode_marc_fields(chunk, rmarc.Field, rmarc.Subfield, rmarc.Indicators)
            count += len(fields)
        return count

    definitions = {
        "file_readinto_256k": (readinto_blocks, len(data)),
        "file_read_256k": (read_blocks, len(data)),
        "file_read_all": (read_all, len(data)),
        "memory_copy": (copy_memory, len(data)),
        "memory_boundaries_only": (frame_memory, counts["records"]),
        "file_frame_chunks": (frame_file, counts["records"]),
        "memory_full_records": (parse_memory, counts["records"]),
        "file_full_records": (parse_file, counts["records"]),
        "memory_raw_records": (lambda: parse_memory(False), counts["records"]),
        "presplit_native_fields": (native_fields, counts["fields"]),
    }
    jobs = []
    for name, (operation, expected) in definitions.items():
        start = time.perf_counter()
        assert operation() == expected
        elapsed = time.perf_counter() - start
        iterations = min(200, max(1, math.ceil(0.05 / max(elapsed, 1e-9))))
        jobs.append((name, operation, expected, iterations, []))
    rng = random.Random(315)  # noqa: S311 - deterministic measurement order
    for _ in range(args.rounds):
        rng.shuffle(jobs)
        for _, operation, expected, iterations, samples in jobs:
            start = time.perf_counter()
            for _ in range(iterations):
                result = operation()
            samples.append((time.perf_counter() - start) / iterations)
            assert result == expected
    rows = []
    for name, _, _, iterations, samples in sorted(jobs):
        median = statistics.median(samples)
        rows.append({"operation": name, "iterations_per_round": iterations, "seconds": samples, "median_seconds": median, "MB_per_second": len(data) / median / 1e6})
    medians = {row["operation"]: row["median_seconds"] for row in rows}
    report = {
        "python": sys.version,
        "rmarc_path": rmarc.__file__,
        "corpus": {"path": str(args.corpus), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **counts},
        "benchmarks": rows,
        "diagnostic_ratios": {
            "bulk_read_floor_over_full_file_parse": medians["file_readinto_256k"] / medians["file_full_records"],
            "framing_over_full_file_parse": medians["file_frame_chunks"] / medians["file_full_records"],
            "memory_over_file_full_parse": medians["memory_full_records"] / medians["file_full_records"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({r["operation"]: round(r["median_seconds"] * 1000, 3) for r in rows}, indent=2), flush=True)
    print(json.dumps(counts), flush=True)
    # Profile after timing: these times are instrumented, not benchmark samples.
    profiler = cProfile.Profile()
    profiler.runcall(parse_memory)
    profiler.dump_stats(str(args.output.with_suffix(".prof")))


if __name__ == "__main__":
    main()
