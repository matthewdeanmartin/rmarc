"""Ordinary read errors, disk-full writes and close errors, compared with pymarc."""

import errno
from io import BufferedReader, BytesIO, RawIOBase

import pymarc
import pytest
import rmarc


def record(module):
    result = module.Record()
    result.add_field(module.Field("001", data="identifier"))
    return result


class FailingSource(RawIOBase):
    """Return available bytes up to a failed disk/network read, then raise."""

    def __init__(self, data, fail_after):
        self.data = data
        self.position = 0
        self.fail_after = fail_after
        self.error = OSError(errno.EIO, "injected read failure")
        self.close_calls = 0

    def readable(self):
        return True

    def read(self, size=-1):
        if self.position >= self.fail_after:
            raise self.error
        end = min(self.fail_after, len(self.data), self.position + size if size >= 0 else len(self.data))
        chunk = self.data[self.position : end]
        self.position = end
        return chunk

    def readinto(self, buffer):
        chunk = self.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)

    def close(self):
        if not self.closed:
            self.close_calls += 1
        super().close()


@pytest.mark.parametrize("buffered", [False, True])
@pytest.mark.parametrize("failure_point", ["first_header", "first_body", "second_header", "second_body"])
def test_read_failure_preserves_error_and_reader_state(buffered, failure_point):
    encoded = record(pymarc).as_marc()
    offset = {"first_header": 0, "first_body": 5, "second_header": len(encoded), "second_body": len(encoded) + 5}[
        failure_point
    ]
    outcomes = []
    for module in (pymarc, rmarc):
        source = FailingSource(encoded * 2, offset)
        if buffered and module is pymarc:
            reader = module.MARCReader(BufferedReader(source, buffer_size=len(encoded)))
        elif buffered:
            reader = module.MARCReader(source, batch_bytes=len(encoded))
        else:
            reader = module.MARCReader(source)
        seen = []
        try:
            with pytest.raises(OSError) as caught:
                for item in reader:
                    seen.append(item.as_dict() if item is not None else None)
            assert caught.value is source.error
            # I/O errors propagate; current_exception is reserved for MARC errors.
            assert reader.current_exception is None
            outcomes.append((seen, reader.current_chunk, caught.value.args))
        finally:
            reader.close()
        assert source.closed
        assert source.close_calls == 1
    assert outcomes[0] == outcomes[1]


class FullDisk(BytesIO):
    def __init__(self, fail_after):
        super().__init__()
        self.fail_after = fail_after
        self.error = OSError(errno.ENOSPC, "injected disk full")

    def write(self, data):
        available = max(0, self.fail_after - self.tell())
        if len(data) > available:
            super().write(data[:available])
            raise self.error
        return super().write(data)


@pytest.mark.parametrize("complete_first_record", [False, True])
def test_disk_full_propagates_and_preserves_written_prefix(complete_first_record):
    encoded = record(pymarc).as_marc()
    limit = len(encoded) + 7 if complete_first_record else 0
    for module in (pymarc, rmarc):
        stream = FullDisk(limit)
        writer = module.MARCWriter(stream)
        with pytest.raises(OSError) as caught:
            writer.write(record(module))
            writer.write(record(module))
        assert caught.value is stream.error
        assert stream.getvalue() == (encoded * 2)[:limit]
        writer.close(close_fh=False)
        assert not stream.closed
        stream.close()


def test_writer_close_failure_is_not_hidden():
    class CloseFailure(BytesIO):
        def close(self):

            raise OSError(errno.EIO, "injected close failure")

    for module in (pymarc, rmarc):
        stream = CloseFailure()
        writer = module.MARCWriter(stream)
        try:
            writer.write(record(module))
            with pytest.raises(OSError, match="injected close failure"):
                writer.close()
            assert writer.file_handle is stream
        finally:
            BytesIO.close(stream)
