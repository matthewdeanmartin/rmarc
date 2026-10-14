"""Measure lookup backports and the raw-codec cost without editing rmarc.

The prototype temporarily borrows pymarc 5.4's generic lookup methods only.
It is an experiment, not a supported runtime configuration.
"""

import argparse
import json
import random
import statistics
import sys
import timeit
from pathlib import Path

import pymarc
import rmarc
from rmarc._rmarc import decode_marc_raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = Path("test_pymarc/test.dat").read_bytes()
    one = data[: int(data[:5])]
    record = rmarc.Record(one)
    baseline = {
        (cls, method): getattr(cls, method)
        for cls, methods in [
            (rmarc.Record, ["get", "__getitem__", "get_fields"]),
            (rmarc.Field, ["get", "__getitem__", "get_subfields"]),
        ]
        for method in methods
    }
    prototypes = {(cls, method): getattr(getattr(pymarc, cls.__name__), method) for cls, method in baseline}

    def install(methods):
        for (cls, name), implementation in methods.items():
            setattr(cls, name, implementation)

    jobs = [
        ("title-preparsed", lambda: record.title, 100_000),
        ("read-title-10", lambda: [r.title for r in rmarc.MARCReader(data)], 500),
        ("full-record", lambda: rmarc.Record(one), 5_000),
        ("raw-codec-lower-bound", lambda: decode_marc_raw(one), 5_000),
    ]
    samples = {name: {"baseline": [], "lookup-prototype": []} for name, _, _ in jobs}
    rng = random.Random(315)  # noqa: S311 - reproducible benchmark order
    try:
        for _ in range(9):
            trials = [(job, variant) for job in jobs for variant in samples[job[0]]]
            rng.shuffle(trials)
            for (name, fn, number), variant in trials:
                install(baseline if variant == "baseline" else prototypes)
                if name == "read-title-10":
                    assert fn() == [r.title for r in pymarc.MARCReader(data)]
                samples[name][variant].append(timeit.timeit(fn, number=number) / number)
    finally:
        install(baseline)
    report = {
        "python": sys.version,
        "samples_seconds": samples,
        "medians_seconds": {
            name: {variant: statistics.median(values) for variant, values in variants.items()}
            for name, variants in samples.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["medians_seconds"], indent=2))


if __name__ == "__main__":
    main()
