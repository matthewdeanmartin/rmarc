"""Shared fixtures for benchmarks."""

import os

import pytest


@pytest.fixture(scope="session")
def test_dat():
    with open("test_pymarc/test.dat", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def one_record_bytes(test_dat):
    """Extract first record from test.dat."""
    length = int(test_dat[:5])
    return test_dat[:length]


@pytest.fixture(scope="session")
def marc8_lines():
    with open("test_pymarc/test_marc8.txt", "rb") as f:
        return [line.strip(b"\r\n") for line in f if line.strip(b"\r\n")]


@pytest.fixture(scope="session")
def medium_dat():
    path = "bench_data/medium.dat"
    if not os.path.exists(path):
        pytest.skip("Run bench/generate_data.py first")
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def large_dat_path():
    path = "bench_data/large.dat"
    if not os.path.exists(path):
        pytest.skip("Run bench/generate_data.py first")
    return path


@pytest.fixture(scope="session")
def one_json_bytes():
    with open("test_pymarc/one.json", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def batch_json_bytes():
    with open("test_pymarc/batch.json", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def batch_xml_bytes():
    with open("test_pymarc/batch.xml", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def one_record(one_record_bytes):
    from rmarc import Record

    return Record(one_record_bytes)
