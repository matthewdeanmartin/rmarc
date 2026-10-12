# Wheels for upcoming Python versions

Recommendation from the 2026-10-04 verification: publish an opt-in package preview, for example `5.3.2rc1`, once PyO3 supports the upcoming Python release. Start with the platform needed for verification (Windows x64 here), rather than repeatedly running a broad matrix with known missing dependency wheels.

This is release engineering for rmarc's own extension. Published rmarc 5.3.1 currently lacks a usable Windows Python 3.15 wheel; lxml/orjson extras are not the blocker. Consumers should never have to compile rmarc during compatibility verification.

Suggested human-operated release procedure:

1. Build the intended wheel once using the supported PyO3 version and Python prerelease. Keep native builds out of dependency-verification runs.
2. Install that wheel in a fresh environment with `--only-binary :all: --no-cache`, then run core tests from the installed package outside the checkout. Separate optional competitor benchmarks.
3. Publish only tested artifacts under an explicit preview version. Do not label an untested prerelease build as stable support.
4. Document the interpreter/platform coverage and opt-in command: `pip install --pre --only-binary :all: rmarc` (or uv's explicit prerelease policy).
5. Revalidate against final Python before claiming final-release support.

The existing release workflow listens to `release: types: [released]`. Do not assume it supplies a preview publication path; designing a separate manual preview workflow is future work. No release workflow was dispatched and no package was published during verification.

A separate investigation should assess PyO3's `abi3` feature. rmarc currently enables `extension-module` but no stable-ABI feature, producing version-specific binaries. A suitable stable-ABI wheel can span multiple Python versions and reduce build work. Check rmarc's API use, supported platforms, performance, and separate free-threaded requirements before switching; no abi3 compatibility or performance claim has been tested here.

References: [PyO3 building and distribution](https://pyo3.rs/main/building-and-distribution), [PyPA prerelease installation](https://packaging.python.org/en/latest/tutorials/installing-packages/).

Publishing releases and filing upstream bugs are human-operator decisions. This document is a recommendation, not authorization to publish.
