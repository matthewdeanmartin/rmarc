### 3-Way Performance Deathmatch

rmarc vs pymarc vs [mrrc](https://pypi.org/project/mrrc/) on Windows 11, Python 3.14, AMD64.

| Benchmark | mrrc | rmarc | pymarc | Winner |
|---|---|---|---|---|
| Read 10 records | **227 us** (1.0x) | 746 us (3.3x) | 3,795 us (16.7x) | mrrc |
| Read 1,000 records | **21.7 ms** (1.0x) | 77.7 ms (3.6x) | 358.7 ms (16.5x) | mrrc |
| Read 100,000 records | **2.16 s** (1.0x) | 7.67 s (3.6x) | 20.1 s (9.3x) | mrrc |
| Title access (10 records) | **136 us** (1.0x) | 771 us (5.7x) | 3,420 us (25.2x) | mrrc |
| Field access (1 record) | 32.7 us (3.2x) | 11.7 us (1.1x) | **10.2 us** (1.0x) | pymarc |
| JSON serialize (10 records) | **317 us** (1.0x) | 645 us (2.0x) | 2,275 us (7.2x) | mrrc |
| XML parse (batch) | 1,797 us (1.6x) | **1,148 us** (1.0x) | 1,324 us (1.2x) | rmarc |

Reproduced via `make perf`. See `bench/bench_deathmatch.py`.

### Choosing a library

**pymarc** is the standard. It has been around for 20 years, is battle-tested in production at hundreds of institutions, and has the largest community. It is pure Python with no compiled dependencies, which means it installs everywhere and is easy to debug. If you are writing a one-off migration script, maintaining an existing ILS integration, or need rock-solid stability and broad platform support, pymarc is the safe choice. You pay for that with speed: it is 5-17x slower than the Rust-backed alternatives on bulk reads.

**rmarc** is a drop-in replacement for pymarc. Same API, same module layout, same tests -- you can swap `import pymarc` for `import rmarc` and your code should just work. The Rust core accelerates binary MARC decoding and MARC-8 conversion while keeping everything else in Python, so the objects you get back behave exactly like pymarc objects. This means field access and manipulation are still at Python speed (which is fine -- those operations are already fast). rmarc is the right choice when you want pymarc compatibility with a 3-5x throughput boost and you rely on the full pymarc ecosystem of patterns, tutorials, and community answers. It also wins on XML parsing thanks to lxml integration.

**mrrc** is the speed king. It does the most work in Rust before crossing into Python, which is why it dominates on read/iterate benchmarks by 3-4x over rmarc and 9-17x over pymarc. The tradeoff is that it is a younger project (self-described as experimental/alpha), has its own API conventions (`.title()` method instead of `.title` property, `xml_to_records()` instead of `parse_xml_to_array()`), and does not aim for exact pymarc compatibility. If you are building a new pipeline from scratch where raw throughput is the priority -- bulk ETL, large-scale cataloging analytics, or anything that touches millions of records -- mrrc is the fastest option available today. Just know that you are adopting a less mature library with a smaller surface area for XML and field-level manipulation.
