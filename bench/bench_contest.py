"""Benchmarks based on the historical contest.py comparison script.

Run with:
    uv run pytest bench/bench_contest.py --benchmark-only -v
"""

from __future__ import annotations

from collections.abc import Callable

import pytest


def _import_pymarc():
    return pytest.importorskip("pymarc", reason="pymarc is required for comparison benchmarks")


@pytest.mark.parametrize(
    ("module_name", "module_loader"),
    [
        ("rmarc", lambda: pytest.importorskip("rmarc")),
        ("pymarc", _import_pymarc),
    ],
)
def test_bench_contest_binary_read_iterate(
    benchmark, contest_marc_path, contest_marc_expected_count, module_name, module_loader
):
    """Benchmark MARC binary record iteration on the larger contest dataset."""
    marc = module_loader()

    def iterate() -> int:
        count = 0
        with open(contest_marc_path, "rb") as fh:
            for record in marc.MARCReader(fh):
                if record:
                    count += 1
        return count

    benchmark.group = "contest-binary"
    benchmark.name = f"{module_name}-binary-read-iterate"
    result = benchmark.pedantic(iterate, rounds=3, warmup_rounds=1)
    assert result == contest_marc_expected_count


@pytest.mark.parametrize(
    ("module_name", "module_loader"),
    [
        ("rmarc", lambda: pytest.importorskip("rmarc")),
        ("pymarc", _import_pymarc),
    ],
)
def test_bench_contest_xml_parse_title_access(
    benchmark,
    contest_xml_path,
    contest_xml_expected_count,
    module_name,
    module_loader,
):
    """Benchmark MARCXML parse plus title access on the larger contest dataset."""
    marc = module_loader()
    parse_xml_to_array: Callable[..., list] = marc.parse_xml_to_array

    def parse_and_touch_titles() -> int:
        records = parse_xml_to_array(contest_xml_path)
        count = 0
        for record in records:
            if record:
                _ = record.title
                count += 1
        return count

    benchmark.group = "contest-xml"
    benchmark.name = f"{module_name}-xml-parse-title"
    result = benchmark.pedantic(parse_and_touch_titles, rounds=3, warmup_rounds=1)
    assert result == contest_xml_expected_count
