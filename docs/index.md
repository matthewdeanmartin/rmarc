# rmarc

A pymarc-compatible MARC21 record library with a Rust core for high performance, roughly 2x faster.

For full documentation, see the [README](https://github.com/matthewdeanmartin/rmarc/blob/main/README.md).

## Overview

This is a fork of [pymarc](https://pypi.org/project/pymarc). Significant use of LLMs to write the Rust speedups.
License is the same MIT.

## Installation

```bash
pip install rmarc
```

For faster JSON and XML processing, install the optional fast backends:

```bash
pip install "rmarc[fast]"        # orjson (JSON) + lxml (XML)
pip install "rmarc[fast-json]"   # orjson only
pip install "rmarc[fast-xml]"    # lxml only
```

## Quick Start

```python
from rmarc import MARCReader, MARCWriter, Record, Field, Indicators, Subfield

# Read a MARC file
with open("records.mrc", "rb") as fh:
    for record in MARCReader(fh):
        print(record.title)

# Write a MARC file
with open("out.mrc", "wb") as fh:
    writer = MARCWriter(fh)
    writer.write(record)
    writer.close()
```

## Links

- [GitHub](https://github.com/matthewdeanmartin/rmarc)
- [PyPI](https://pypi.org/project/rmarc/)
