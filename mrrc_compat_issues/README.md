# Small pymarc compatibility reproductions for mrrc

This folder can be copied into an empty directory and run on its own. It needs
only Python, pytest, pymarc, and mrrc. It does not import rmarc, download MARC data,
or read files outside this folder. Each example constructs its own tiny record.

Verified versions: pymarc 5.4.0 and mrrc 0.9.2, Windows CPython 3.13.3.
Use Python 3.13 for the pinned mrrc Windows wheel; 0.9.2 has no Windows 3.15 wheel.

```bash
cd mrrc_compat_issues
uv venv --python 3.13
uv pip install --only-binary :all: -r requirements.txt
uv run --no-project pytest -v
```

Every test runs twice, labeled `[pymarc]` and `[mrrc]`. Assertions express pymarc
behavior. Failures on mrrc are intentional reproductions, not installation errors
or expected-failure markers.

Verified outcome: **11 passed, 9 failed**: all ten pymarc cases pass, plus the
mrrc direct-assignment control. The nine failures are the differences below.

To inspect one issue:

```bash
uv run --no-project pytest -v test_behavior.py -k title_includes_subtitle
```

| Reproduction | Observed mrrc 0.9.2 behavior | Why it matters |
| --- | --- | --- |
| Title includes subtitle | Returns 245$a without 245$b | Silently shortened display title |
| Selector order | Groups by requested tags | Order-sensitive processing changes |
| Repeated selector | Duplicates returned fields | Double-processing or duplicate exports |
| Missing subfield | Returns None | Exception-based handling no longer runs |
| Binary roundtrip order | Groups repeated data tags | Serialized field order changes |
| Legacy encoding flag | Keeps the blank flag; pymarc writes `a` | Exact serialization differs; this ASCII example does **not** demonstrate data corruption |

`test_api_differences.py` separately documents mutable-list APIs. mrrc exposes
`fields` and `subfields` as methods, so code using pymarc's lists does not work.
These may be intentional migration differences rather than bugs to fix.
`test_direct_subfield_assignment_updates_record` is a passing control: do not
claim all mrrc field mutations are lost.

For a maintainer report, copy the relevant test function, its failure, and the
version header. State the expected behavior and whether exact pymarc compatibility
is intended. No issue or message has been submitted automatically.
