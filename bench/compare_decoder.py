"""Interleave old/new release decoders in one process to reduce machine-load drift.

--baseline-package points to a frozen rmarc package with its original extension.
It is copied under a different import namespace; record data is never changed.
Run from the repository root, with no concurrent benchmark/build/test jobs.
"""

import argparse
import importlib
import json
import random
import shutil
import statistics
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = Path("target/decoder-comparison/rmarc_baseline")
    directory.mkdir(parents=True, exist_ok=True)
    for source in args.baseline_package.iterdir():
        if source.suffix == ".py":
            text = (
                source.read_text(encoding="utf-8")
                .replace("from rmarc", "from rmarc_baseline")
                .replace("import rmarc", "import rmarc_baseline")
            )
            (directory / source.name).write_text(text, encoding="utf-8")
        elif source.suffix in (".pyd", ".so"):
            shutil.copy2(source, directory / source.name)
    sys.path.insert(0, str(directory.parent.resolve()))
    modules = {"before": importlib.import_module("rmarc_baseline"), "after": importlib.import_module("rmarc")}
    for module in modules.values():
        assert module.record._HAS_RUST_CODEC
    corpora = {"repeated-1000": Path("test_pymarc/test.dat").read_bytes() * 100}
    real = Path("data/Computer.Files.2019.part01.utf8")
    if real.exists():
        corpora["loc-computer-files"] = real.read_bytes()

    def process(module, data, operation):
        total = 0
        for record in module.MARCReader(data):
            assert record is not None
            if operation == "read":
                total += 1
            elif operation == "title":
                total += len(record.title or "")
            else:
                total += len(record.as_marc())
        return total

    jobs = []
    for corpus, data in corpora.items():
        expected = [(r.title, r.as_marc()) for r in modules["before"].MARCReader(data)]
        actual = [(r.title, r.as_marc()) for r in modules["after"].MARCReader(data)]
        assert actual == expected
        for operation in ("read", "title", "roundtrip"):
            for variant, module in modules.items():
                process(module, data, operation)  # warmup
                jobs.append(
                    (module, data, {"corpus": corpus, "operation": operation, "variant": variant, "seconds": []})
                )
    rng = random.Random(315)  # noqa: S311 - deterministic benchmark order
    for _ in range(7):
        rng.shuffle(jobs)
        for module, data, row in jobs:
            start = time.perf_counter()
            process(module, data, row["operation"])
            row["seconds"].append(time.perf_counter() - start)
    rows = sorted([row for _, _, row in jobs], key=lambda r: (r["corpus"], r["operation"], r["variant"]))
    medians = {(r["corpus"], r["operation"], r["variant"]): statistics.median(r["seconds"]) for r in rows}
    speedups = {
        f"{corpus} / {operation}": medians[corpus, operation, "before"] / medians[corpus, operation, "after"]
        for corpus in corpora
        for operation in ("read", "title", "roundtrip")
    }
    report = {
        "python": sys.version,
        "module_paths": {k: v.__file__ for k, v in modules.items()},
        "benchmarks": rows,
        "speedups": speedups,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(speedups, indent=2))


if __name__ == "__main__":
    main()
