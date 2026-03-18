# This file is part of rmarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

from rmarc import MARCReader, Record
from test_pymarc import fixture_path


def test_encode_decode():
    # get raw data from file
    with fixture_path("one.dat").open("rb") as fh:
        original = fh.read()

    # create a record object for the file
    with fixture_path("one.dat").open("rb") as fh:
        reader = MARCReader(fh)
        record = next(reader)
        assert record is not None
        # make sure original data is the same as
        # the record encoded as MARC
        raw = record.as_marc()
        assert original == raw


def test_encode_decode_alphatag():
    # get raw data from file containing non-numeric tags
    with fixture_path("alphatag.dat").open("rb") as fh:
        original = fh.read()

    # create a record object for the file
    with fixture_path("alphatag.dat").open("rb") as fh:
        reader = MARCReader(fh)
        record = next(reader)
        # make sure original data is the same as
        # the record encoded as MARC
        assert isinstance(record, Record)
        raw = record.as_marc()
        assert original == raw
