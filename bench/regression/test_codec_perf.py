"""Local regression workloads. Timing is owned by pytest-benchmark."""

import hashlib
from pathlib import Path

import pytest
import rmarc
from rmarc import _rmarc


@pytest.fixture(scope="module")
def corpus():
    assert rmarc.record._HAS_RUST_CODEC, "Build the release extension before benchmarking"
    data = (Path(__file__).resolve().parents[2] / "test_pymarc/test.dat").read_bytes() * 100
    records = list(rmarc.MARCReader(data))
    assert len(records) == 1000
    assert all(record is not None for record in records)
    return data, records


@pytest.mark.parametrize("operation", ["decode", "decode_buffered", "encode", "roundtrip"])
def test_codec_throughput(benchmark, corpus, operation):
    data, records = corpus

    def decode():
        count = 0
        size = 256 * 1024 if operation == "decode_buffered" else 0
        for record in rmarc.MARCReader(data, batch_bytes=size):
            assert record is not None
            count += 1
        return count

    def encode():
        return sum(len(record.as_marc()) for record in records)

    def roundtrip():
        return sum(len(record.as_marc()) for record in rmarc.MARCReader(data))

    expected = len(records) if operation.startswith("decode") else encode()
    action = {"decode": decode, "decode_buffered": decode, "encode": encode, "roundtrip": roundtrip}[operation]
    benchmark.extra_info["extension_sha256"] = hashlib.sha256(Path(_rmarc.__file__).read_bytes()).hexdigest()
    assert benchmark.pedantic(action, rounds=15, warmup_rounds=3, iterations=3) == expected
