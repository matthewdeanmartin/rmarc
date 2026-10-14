"""Reproducible release investigation; run from the repository root.

Uses time.perf_counter directly to avoid platform CPU-discovery overhead.
Does not change production code. Output includes raw, interleaved samples.
"""

import argparse
import cProfile
import hashlib
import importlib
import importlib.metadata
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--libraries", nargs="+", default=["pymarc", "rmarc", "mrrc"])
    parser.add_argument("--rounds", type=int, default=7)
    args = parser.parse_args()
    modules = {name: importlib.import_module(name) for name in args.libraries}
    if "rmarc" in modules:
        assert modules["rmarc"].record._HAS_RUST_CODEC, "Build the release Rust extension before benchmarking"
    corpora = {"repeated-1000": Path("test_pymarc/test.dat").read_bytes() * 100}
    real = Path("data/Computer.Files.2019.part01.utf8")
    if real.exists():
        corpora["loc-computer-files"] = real.read_bytes()
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "versions": {name: importlib.metadata.version(name) for name in modules},
        "module_paths": {name: module.__file__ for name, module in modules.items()},
        "corpora": {},
        "benchmarks": [],
    }
    jobs = []
    for corpus, data in corpora.items():
        expected = list(modules["pymarc"].MARCReader(data))
        assert all(rec is not None for rec in expected)
        report["corpora"][corpus] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "records": len(expected),
        }
        expected_titles = [rec.title for rec in expected]
        expected_marc = [rec.as_marc() for rec in expected]
        for name, module in modules.items():
            records = list(module.MARCReader(data))
            assert len(records) == len(expected) and all(rec is not None for rec in records)
            titles_equal = [rec.title for rec in records] == expected_titles
            roundtrip_equal = [rec.as_marc() for rec in records] == expected_marc
            if name == "rmarc":
                assert titles_equal and roundtrip_equal, "rmarc output differs from pymarc"
            for operation in ["read", "title", "roundtrip"]:

                def run(module=module, data=data, operation=operation):
                    total = 0
                    for record in module.MARCReader(data):
                        if record is None:
                            raise AssertionError("reader silently dropped a record")
                        if operation == "read":
                            total += 1
                        elif operation == "title":
                            total += len(record.title or "")
                        else:
                            total += len(record.as_marc())
                    return total

                result = run()  # warmup, outside timing
                entry = {
                    "corpus": corpus,
                    "library": name,
                    "operation": operation,
                    "titles_equal_pymarc": titles_equal,
                    "roundtrip_equal_pymarc": roundtrip_equal,
                    "result": result,
                    "seconds": [],
                }
                jobs.append((run, entry))
            del records
        del expected
    randomizer = random.Random(315)  # noqa: S311 - reproducible benchmark order
    for _ in range(args.rounds):
        randomizer.shuffle(jobs)
        for run, entry in jobs:
            start = time.perf_counter()
            result = run()
            elapsed = time.perf_counter() - start
            assert result == entry["result"]
            entry["seconds"].append(elapsed)
    for _, entry in jobs:
        entry["median_seconds"] = statistics.median(entry["seconds"])
        n = report["corpora"][entry["corpus"]]["records"]
        entry["records_per_second"] = n / entry["median_seconds"]
        report["benchmarks"].append(entry)
    report["benchmarks"].sort(key=lambda x: (x["corpus"], x["operation"], x["library"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for row in report["benchmarks"]:
        print(
            row["corpus"],
            row["operation"],
            row["library"],
            f"{row['median_seconds'] * 1000:.3f} ms",
            f"{row['records_per_second']:,.0f} records/s",
            "titles match:",
            row["titles_equal_pymarc"],
        )
    if "rmarc" in modules:
        profile = cProfile.Profile()
        profile.runcall(lambda: list(modules["rmarc"].MARCReader(corpora["repeated-1000"])))
        profile.dump_stats(str(args.output.with_suffix(".prof")))


if __name__ == "__main__":
    main()
