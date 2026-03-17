"""Core benchmarks for rmarc performance tracking.

Run with:
    uv run pytest bench/ --benchmark-only
    uv run pytest bench/ --benchmark-save=baseline
    uv run pytest bench/ --benchmark-compare
"""


def test_bench_decode_single(benchmark, one_record_bytes):
    """Benchmark: parse a single MARC record from bytes."""
    from rmarc import Record

    benchmark(Record, one_record_bytes)


def test_bench_roundtrip_single(benchmark, one_record_bytes):
    """Benchmark: parse + serialize a single record."""
    from rmarc import Record

    def roundtrip():
        r = Record(one_record_bytes)
        return r.as_marc()

    benchmark(roundtrip)


def test_bench_read_iterate_small(benchmark, test_dat):
    """Benchmark: iterate all 10 records in test.dat."""
    from rmarc import MARCReader

    def iterate():
        count = 0
        for record in MARCReader(test_dat):
            if record:
                count += 1
        return count

    result = benchmark(iterate)
    assert result == 10


def test_bench_marc8_convert(benchmark, marc8_lines):
    """Benchmark: convert 1515 MARC-8 lines to Unicode."""
    from rmarc import marc8_to_unicode

    def convert_all():
        for line in marc8_lines:
            marc8_to_unicode(line)

    benchmark(convert_all)


def test_bench_field_access(benchmark, one_record_bytes):
    """Benchmark: access all field values in a parsed record."""
    from rmarc import Record

    record = Record(one_record_bytes)

    def access():
        for field in record.get_fields():
            _ = field.value()

    benchmark(access)


def test_bench_as_dict(benchmark, one_record_bytes):
    """Benchmark: convert a record to dict (used by as_json)."""
    from rmarc import Record

    record = Record(one_record_bytes)
    benchmark(record.as_dict)


def test_bench_as_json(benchmark, one_record_bytes):
    """Benchmark: serialize a record to JSON string."""
    from rmarc import Record

    record = Record(one_record_bytes)
    benchmark(record.as_json)


def test_bench_str(benchmark, one_record_bytes):
    """Benchmark: convert a record to MARCMaker string."""
    from rmarc import Record

    record = Record(one_record_bytes)
    benchmark(str, record)


def test_bench_read_iterate_medium(benchmark, medium_dat):
    """Benchmark: iterate 1,000 records."""
    from rmarc import MARCReader

    def iterate():
        count = 0
        for record in MARCReader(medium_dat):
            if record:
                count += 1
        return count

    result = benchmark(iterate)
    assert result == 1000


def test_bench_bulk_large(benchmark, large_dat_path):
    """Benchmark: iterate 100,000 records from file."""
    from rmarc import MARCReader

    def iterate():
        count = 0
        with open(large_dat_path, "rb") as fh:
            for record in MARCReader(fh):
                if record:
                    count += 1
        return count

    result = benchmark.pedantic(iterate, rounds=3, warmup_rounds=1)
    assert result == 100_000
