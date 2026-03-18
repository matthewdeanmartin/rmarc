"""Shared fixtures for benchmarks."""

import os
from pathlib import Path

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


@pytest.fixture(scope="session")
def contest_data_dir():
    path = Path("data")
    if not path.exists():
        pytest.skip("contest benchmark data not available")
    return path


@pytest.fixture(scope="session")
def contest_marc_path(contest_data_dir):
    path = contest_data_dir / "Computer.Files.2019.part01.utf8"
    if not path.exists():
        pytest.skip(f"contest MARC benchmark data not available: {path}")
    return path


@pytest.fixture(scope="session")
def contest_xml_path(contest_data_dir):
    path = contest_data_dir / "Computer.Files.2019.part01.xml"
    if not path.exists():
        pytest.skip(f"contest XML benchmark data not available: {path}")
    return path


def _count_marc_records(path: Path) -> int:
    count = 0
    with path.open("rb") as fh:
        while True:
            leader = fh.read(5)
            if not leader:
                return count
            if len(leader) != 5:
                raise ValueError(f"Incomplete MARC leader in {path}")
            record_length = int(leader)
            if record_length < 5:
                raise ValueError(f"Invalid MARC record length {record_length} in {path}")
            fh.seek(record_length - 5, os.SEEK_CUR)
            count += 1


@pytest.fixture(scope="session")
def contest_marc_expected_count(contest_marc_path):
    return _count_marc_records(contest_marc_path)


@pytest.fixture(scope="session")
def contest_xml_expected_count(contest_xml_path):
    from rmarc.marcxml import parse_xml_to_array

    return len(parse_xml_to_array(contest_xml_path))
