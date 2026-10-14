"""Malformed inputs must produce Python errors, never native panics."""

from contextlib import suppress

import pymarc
import pytest
import rmarc
from hypothesis import given, settings
from hypothesis import strategies as st


def encoded_record():
    record = rmarc.Record()
    record.add_field(rmarc.Field("001", data="small"))
    return record.as_marc()


@pytest.mark.parametrize("length,offset", [(0, 0), (9999, 0), (1, 99999), (9999, 99999)])
@pytest.mark.parametrize("batch_bytes", [0, 7, 256 * 1024])
def test_out_of_range_directory_matches_pymarc_and_preserves_next_record(length, offset, batch_bytes):
    good = encoded_record()
    bad = bytearray(good)
    bad[27:36] = f"{length:04d}{offset:05d}".encode("ascii")
    reader = rmarc.MARCReader(bytes(bad) + good, batch_bytes=batch_bytes)
    # pymarc deliberately uses forgiving Python slices here. Native bounds
    # checks must fall back without changing the public result.
    expected = next(pymarc.MARCReader(bytes(bad)))
    assert next(reader).as_dict() == expected.as_dict()
    assert reader.current_exception is None
    assert reader.current_chunk == bytes(bad)
    assert next(reader).as_marc() == good
    assert reader.current_exception is None
    with pytest.raises(StopIteration):
        next(reader)


@settings(max_examples=300, deadline=None)
@given(payload=st.binary(max_size=512))
def test_arbitrary_record_bytes_never_escape_as_native_panic(payload):
    # PyO3's PanicException inherits BaseException, not Exception. Catching only
    # normal Python exceptions intentionally leaves Rust panics as test failures.
    with suppress(Exception):
        rmarc.Record(data=payload)


@settings(max_examples=200, deadline=None)
@given(length=st.integers(0, 9999), offset=st.integers(0, 99999))
def test_directory_numbers_cannot_panic(length, offset):
    payload = bytearray(encoded_record())
    payload[27:36] = f"{length:04d}{offset:05d}".encode("ascii")
    with suppress(Exception):
        rmarc.Record(data=bytes(payload))
