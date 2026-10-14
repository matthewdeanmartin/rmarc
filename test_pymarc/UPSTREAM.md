# pymarc test provenance

The compatibility target is **pymarc 5.4.0**, published on PyPI. The historical
`pymarc_src` snapshot remains 5.3.1; it is not the current compatibility oracle.

Compared all eleven upstream `test/test_*.py` modules in the 5.4.0 source archive
with the bundled upstream snapshot. The behavioral test additions are exactly
three methods in `test_field.py`: numeric string padding, preservation of a
padded tag, and integer tag padding. Those three are now included here. The
other changed module, `test_writer.py`, only changes formatting. Existing local
import, fixture-path, and Windows temporary-file adaptations remain in place.

Source archive:
https://files.pythonhosted.org/packages/19/77/f0e5774845a3c60b26da5dab344e391e9941eeb811a1685fb2ff01ae90c7/pymarc-5.4.0.tar.gz

Upstream tests retain their existing license headers. The single-pass lookup
implementations and tag handling in `record.py` / `field.py` follow this release.

`test_codec_compatibility.py` adds targeted encoding and mutation regressions and
runs the twenty local binary fixtures through both libraries under six reader
configurations. It runs rmarc's Rust and Python paths. CI wheel/matrix tests install
the pinned reference version; without pymarc the differential cases explicitly
skip, while the self-contained regression assertions still run.

During the audit, the unmodified 5.4.0 suite and its import-redirected rmarc copy
both passed 174 tests and failed the same three Windows NamedTemporaryFile
subtests. That platform-test limitation is documented in the audit, not counted
as a rmarc compatibility regression.
