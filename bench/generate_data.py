#!/usr/bin/env python3
"""Generate benchmark data files by repeating test records."""
import os


def generate(src, dst, target_records):
    with open(src, "rb") as f:
        data = f.read()
    # each record in MARC is self-delimiting (ends with 0x1D)
    records = []
    pos = 0
    while pos < len(data):
        length = int(data[pos : pos + 5])
        records.append(data[pos : pos + length])
        pos += length
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        for i in range(target_records):
            f.write(records[i % len(records)])
    size_mb = os.path.getsize(dst) / (1024 * 1024)
    print(f"  {dst}: {target_records} records, {size_mb:.1f} MB")


if __name__ == "__main__":
    print("Generating benchmark data...")
    generate("test_pymarc/test.dat", "bench_data/medium.dat", 1_000)
    generate("test_pymarc/test.dat", "bench_data/large.dat", 100_000)
    print("Done.")
