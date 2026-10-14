"""Opt-in buffering keeps per-record semantics; physical read-ahead is explicit."""

import codecs
from io import BufferedReader, BytesIO, RawIOBase, UnsupportedOperation
from pathlib import Path
from unittest.mock import patch

import pymarc
import pytest
import rmarc
from hypothesis import given, settings
from hypothesis import strategies as st


def encoded(value="one"):
    record = pymarc.Record()
    record.add_field(pymarc.Field("245", subfields=[pymarc.Subfield("a", value)]))
    return record.as_marc()


def snapshot(reader):
    try:
        record = next(reader)
        result = record.as_dict() if record is not None else None
    except StopIteration:
        result = "stop"
    error = reader.current_exception
    return result, reader.current_chunk, type(error).__name__, str(error)


class ReadOnlyStream:
    """A caller-owned binary source with no readinto or seek methods."""

    def __init__(self, data, short_read=None):
        self.stream = BytesIO(data)
        self.short_read = short_read
        self.calls = []

    def read(self, size=-1):
        self.calls.append(size)
        return self.stream.read(min(size, self.short_read) if self.short_read else size)

    def close(self):
        self.stream.close()


def test_default_preserves_source_and_read_sizes():
    chunk = encoded()
    source = ReadOnlyStream(chunk * 3)
    reader = rmarc.MARCReader(source)
    assert reader.file_handle is source
    assert next(reader).title == "one"
    assert source.calls == [5, len(chunk) - 5]
    assert source.stream.tell() == len(chunk)


@pytest.mark.parametrize("batch_bytes", [1, 5, 64, 256 * 1024])
def test_read_only_stream_is_supported_and_owned(batch_bytes):
    source = ReadOnlyStream(encoded() * 3)
    reader = rmarc.MARCReader(source, batch_bytes=batch_bytes)
    assert isinstance(reader.file_handle, BufferedReader)
    assert source.calls == []
    assert [record.title for record in reader] == ["one"] * 3
    assert not reader.file_handle.seekable()
    with pytest.raises(UnsupportedOperation):
        reader.file_handle.tell()
    reader.close()
    reader.close()
    assert source.stream.closed
    with pytest.raises(ValueError, match="closed"):
        next(reader)


def test_read_ahead_reduces_calls_but_keeps_logical_position():
    chunk = encoded()
    source = BytesIO(chunk * 3)
    reader = rmarc.MARCReader(source, batch_bytes=4096)
    assert next(reader).title == "one"
    assert source.tell() == len(chunk) * 3
    assert reader.file_handle.tell() == len(chunk)
    assert reader.current_chunk == chunk
    reader.file_handle.seek(0)
    assert next(reader).title == "one"
    reader.close()
    assert source.closed


def test_read_only_source_needs_one_read_for_many_records():
    source = ReadOnlyStream(encoded() * 20)
    reader = rmarc.MARCReader(source, batch_bytes=4096)
    for _ in range(20):
        assert next(reader) is not None
    assert source.calls == [4096]
    reader.close()


def test_raw_io_subclass_with_only_read_is_adapted():
    class Source(ReadOnlyStream, RawIOBase):
        pass

    source = Source(encoded() * 2)
    reader = rmarc.MARCReader(source, batch_bytes=64)
    assert [r.title for r in reader] == ["one", "one"]
    reader.close()


def test_buffering_does_not_bypass_custom_read_override():
    class TransformingStream(BytesIO):
        def read(self, size=-1):
            return super().read(size).replace(b"one", b"two")

    source = TransformingStream(encoded() * 2)
    reader = rmarc.MARCReader(source, batch_bytes=4096)
    assert [record.title for record in reader] == ["two", "two"]
    reader.close()


def test_record_larger_than_batch_is_not_truncated():
    value = "x" * 5000
    chunk = encoded(value)
    source = ReadOnlyStream(chunk * 3)
    reader = rmarc.MARCReader(source, batch_bytes=64)
    assert next(reader).title == value
    assert reader.current_chunk == chunk
    assert source.stream.tell() < len(chunk) * 2
    assert [r.title for r in reader] == [value, value]
    reader.close()


@pytest.mark.parametrize("header", [b"00000", b"00001", b"00004", b"-0010"])
def test_malformed_negative_read_sizes_follow_buffered_pymarc(header):
    data = header + encoded()[5:] + encoded("tail")
    expected = pymarc.MARCReader(BufferedReader(BytesIO(data)))
    actual = rmarc.MARCReader(data, batch_bytes=64)
    if header == b"00004":
        # Inherited read(-1) semantics consume the rest of the input.
        assert snapshot(actual) == snapshot(expected)
        assert actual.current_chunk == data
    else:
        with pytest.raises(ValueError) as reference:
            next(expected)
        with pytest.raises(ValueError) as result:
            next(actual)
        assert result.value.args == reference.value.args
        assert actual.current_chunk == expected.current_chunk == header
        assert actual.current_exception is expected.current_exception is None
    expected.close()
    actual.close()


def test_early_close_discards_unconsumed_bytes():
    source = ReadOnlyStream(encoded() * 20)
    reader = rmarc.MARCReader(source, batch_bytes=4096)
    next(reader)
    reader.close()
    assert source.calls == [4096]
    assert source.stream.closed
    with pytest.raises(ValueError, match="closed"):
        next(reader)


def test_decode_is_lazy_and_uses_current_options():
    calls = []

    def handler(error):
        calls.append(error.object)
        return "fixed", error.end

    codecs.register_error("rmarc_batch_test", handler)
    bad = encoded("X").replace(b"X", b"\xff")
    reader = rmarc.MARCReader(encoded() + bad + encoded(), batch_bytes=4096)
    first = next(reader)
    assert first.title == "one"
    assert calls == []
    assert reader.current_exception is None
    reader.utf8_handling = "rmarc_batch_test"
    assert next(reader).title == "fixed"
    assert calls == [b"\xff"]
    reader.to_unicode = False
    raw = next(reader)
    assert type(raw["245"]) is rmarc.RawField
    assert raw["245"]["a"] == b"one"
    assert first.get_fields() is first.fields
    assert type(first["245"]) is rmarc.Field
    first["245"].subfields.append(rmarc.Subfield("b", "subtitle"))
    assert first.title == "one subtitle"


@pytest.mark.parametrize("value", [-1, -4096])
def test_negative_batch_size_does_not_touch_source(value):
    source = ReadOnlyStream(encoded())
    with pytest.raises(ValueError, match="batch_bytes"):
        rmarc.MARCReader(source, batch_bytes=value)
    assert source.calls == []
    assert not source.stream.closed


@pytest.mark.parametrize("value", [1.5, "64", None])
def test_noninteger_batch_size_is_rejected(value):
    with pytest.raises(TypeError):
        rmarc.MARCReader(b"", batch_bytes=value)


def test_io_error_propagates_without_decoding_future_records():
    chunk = encoded()

    class FailingStream(ReadOnlyStream):
        def read(self, size=-1):
            if self.calls:
                raise OSError("source failed")
            return super().read(size)

    source = FailingStream(chunk * 2)
    reader = rmarc.MARCReader(source, batch_bytes=len(chunk))
    assert next(reader).title == "one"
    with pytest.raises(OSError, match="source failed"):
        next(reader)
    assert reader.current_exception is None
    reader.close()


@settings(max_examples=150, deadline=None)
@given(batch_bytes=st.integers(1, 2048), short_read=st.integers(1, 25), count=st.integers(1, 8))
def test_short_reads_are_accumulated(batch_bytes, short_read, count):
    data = encoded() * count
    source = ReadOnlyStream(data, short_read=short_read)
    reader = rmarc.MARCReader(source, batch_bytes=batch_bytes)
    assert [record.as_marc() for record in reader] == [encoded()] * count
    reader.close()


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
@settings(max_examples=150, deadline=None)
@given(
    batch_bytes=st.integers(1, 2048),
    values=st.lists(st.text(alphabet="abcé世界", max_size=30), min_size=1, max_size=8),
    damage=st.sampled_from(["none", "truncated", "bad_length", "bad_terminator", "bad_base", "invalid_utf8"]),
)
def test_record_and_error_sequence_matches_pymarc(native, batch_bytes, values, damage):
    chunks = [encoded(value) for value in values]
    damaged = encoded("X")
    if damage == "truncated":
        damaged = damaged[:-3]
    elif damage == "bad_length":
        damaged = b"abcde" + damaged[5:]
    elif damage == "bad_terminator":
        damaged = damaged[:-1] + b"!"
    elif damage == "bad_base":
        damaged = damaged[:12] + b"00000" + damaged[17:]
    elif damage == "invalid_utf8":
        damaged = damaged.replace(b"X", b"\xff")
    tail = b"" if damage == "truncated" else encoded("after error")
    data = b"".join(chunks) + damaged + tail
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        expected = pymarc.MARCReader(data)
        actual = rmarc.MARCReader(data, batch_bytes=batch_bytes)
        for _ in range(len(chunks) + 4):
            assert snapshot(actual) == snapshot(expected)
        actual.close()


@pytest.mark.parametrize("path", sorted(Path(__file__).parent.glob("*.dat")), ids=lambda p: p.name)
def test_existing_fixtures_match_buffered_pymarc(path):
    data = path.read_bytes()
    # Buffering a stream is also supported by pymarc without a new API.
    expected = pymarc.MARCReader(BufferedReader(BytesIO(data), buffer_size=257))
    actual = rmarc.MARCReader(data, batch_bytes=257)
    for _ in range(len(data) // 5 + 2):
        reference = snapshot(expected)
        assert snapshot(actual) == reference
        if reference[0] == "stop":
            break
    else:
        pytest.fail("reader did not terminate")
    expected.close()
    actual.close()
