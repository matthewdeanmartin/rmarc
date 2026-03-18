"""Compatibility entrypoint for the historical contest benchmark.

The actual benchmark now lives in bench/bench_contest.py so it can be run
through pytest-benchmark and included in the normal perf workflow.
"""

from __future__ import annotations

import pytest


def main() -> int:
    return pytest.main(["bench/bench_contest.py", "--benchmark-only", "-v"])


if __name__ == "__main__":
    raise SystemExit(main())
