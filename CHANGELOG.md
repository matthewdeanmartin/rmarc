# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Benchmark and deathmatch performance comparison script
- Performance documentation comparing parsing implementations
- Official support for Python 3.14 and 3.15, including binary wheels

### Changed
- Improve internal build and CI configuration
- Test matrix now covers Python 3.10, 3.13, 3.14 and 3.15
- CI installs only maturin and pytest so prerelease Pythons are not blocked by
  dev-only tooling without wheels

### Fixed
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
