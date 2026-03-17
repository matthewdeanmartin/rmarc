# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

from pymarc import MARCReader, Record


def test_encode_decode():
    # get raw data from file
    with open("test/one.dat", "rb") as fh:
        original = fh.read()

    # create a record object for the file
    with open("test/one.dat", "rb") as fh:
        reader = MARCReader(fh)
        record = next(reader)
        assert record is not None
        # make sure original data is the same as
        # the record encoded as MARC
        raw = record.as_marc()
        assert original == raw


def test_encode_decode_alphatag():
    # get raw data from file containing non-numeric tags
    with open("test/alphatag.dat", "rb") as fh:
        original = fh.read()

    # create a record object for the file
    with open("test/alphatag.dat", "rb") as fh:
        reader = MARCReader(fh)
        record = next(reader)
        # make sure original data is the same as
        # the record encoded as MARC
        assert isinstance(record, Record)
        raw = record.as_marc()
        assert original == raw
