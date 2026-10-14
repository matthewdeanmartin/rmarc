# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Stateful differential editing histories and targeted I/O fault-injection tests.
- Executable typed book-catalog examples checked during builds and CI.
- Local-only pytest-benchmark regression targets with saved baselines.
- Release regressions for optional XML/JSON backends, malformed directories,
  native panic boundaries, MARC-8 state isolation, and decimal encoding limits.
- Pyrefly checks and maintained lxml stubs in development dependencies and CI.
- Optional `MARCReader(..., batch_bytes=N)` I/O read-ahead, with lazy decoding
  and unchanged default reader behavior; supports binary read-only streams.
- Hypothesis differential tests for serialization, decoding, mutable lists,
  encoding errors, raw bytes, tags, and reader state against pymarc 5.4.0.
- Self-contained pytest reproductions of mrrc 0.9.2 compatibility differences.
- Differential encoding and mutation regressions against pymarc 5.4.0.
- Benchmark and deathmatch performance comparison script
- Performance documentation comparing parsing implementations
- Official support for Python 3.14 and 3.15, including binary wheels

### Changed
- Check unannotated function bodies with mypy; run pytest (including Hypothesis)
  from the coverage Makefile target. Exercise optional backend wheels in CI.
- Assemble MARC output directly in its final bytes buffer and avoid per-field
  directory formatting allocations; retain custom field serialization hooks.
- Decode MARC records directly into Python Field/Subfield objects, avoiding an
  intermediate tuple tree; borrow valid UTF-8 and fast-path printable MARC-8 ASCII.
- Adopt pymarc 5.4's single-pass lookups and tag normalization while preserving
  mutable field/subfield lists and record order.
- Improve internal build and CI configuration
- Requires Python 3.11 or newer; Python 3.10 is no longer supported.
- Matrix CI installs maturin, pytest and the pinned pymarc reference so prerelease Pythons are not blocked by
  dev-only tooling without wheels

### Fixed
- Preserve valid replacement characters with UTF-8 `ignore`, honor custom/error
  handlers, and retain exact decoding exceptions and partially decoded records.
- Decode explicit UTF-8 and legacy control fields with pymarc's encoding semantics.
- Preserve Python error behavior for trailing MARC-8 escape sequences.
- Compare equivalent field/XML work in benchmarks and skip non-equivalent outputs;
  install the `cpuinfo` provider required by pytest-benchmark's JSON reports.
- Enable cibuildwheel's `cpython-prerelease` so `cp315-*` wheels are actually
  built instead of silently skipped
- Compare PEP 440 normalized versions when verifying the sdist, so SemVer
  prerelease tags such as `5.4.0-rc.1` no longer fail the release

## [5.3.1] - 2026-03-19
### Added
- Fast JSON and XML parsing (Rust implementation)
- Performance optimization and improvements
- Comprehensive testing and CI setup
- Code review fixes and improvements

### Fixed
- Path handling and Mac compatibility

[Unreleased]: https://github.com/matthewdeanmartin/rmarc/compare/v5.3.1...HEAD
[5.3.1]: https://github.com/matthewdeanmartin/rmarc/compare/v5.3.1...v5.3.1
