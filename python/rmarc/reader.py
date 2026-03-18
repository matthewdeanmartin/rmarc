"""Rmarc Reader (pymarc compatible)."""

__all__ = [
    "Reader",
    "MARCReader",
    "map_records",
    "JSONReader",
    "MARCMakerReader",
]

import json
import os
import sys
from collections.abc import Callable, Iterator
from io import BufferedReader, BytesIO, IOBase, StringIO
from typing import IO, BinaryIO

from rmarc._compat import json_loads
from rmarc.constants import END_OF_RECORD
from rmarc.exceptions import (
    EndOfRecordNotFound,
    FatalReaderError,
    PymarcException,
    RecordLengthInvalid,
    TruncatedRecord,
)
from rmarc.field import Field, Indicators, Subfield
from rmarc.leader import Leader
from rmarc.record import Record


class Reader:
    """A base class for all iterating readers in the rmarc package."""

    pass


class MARCReader(Reader):
    """An iterator class for reading a file of MARC21 records."""

    _current_chunk = None
    _current_exception = None

    file_handle: IO

    @property
    def current_chunk(self):
        return self._current_chunk

    @property
    def current_exception(self):
        return self._current_exception

    def __init__(
        self,
        marc_target: BinaryIO | bytes,
        to_unicode: bool = True,
        force_utf8: bool = False,
        hide_utf8_warnings: bool = False,
        utf8_handling: str = "strict",
        file_encoding: str = "iso8859-1",
        permissive: bool = False,
    ) -> None:
        super().__init__()
        self.to_unicode = to_unicode
        self.force_utf8 = force_utf8
        self.hide_utf8_warnings = hide_utf8_warnings
        self.utf8_handling = utf8_handling
        self.file_encoding = file_encoding
        self.permissive = permissive
        if isinstance(marc_target, bytes):
            self.file_handle = BytesIO(marc_target)
        else:
            self.file_handle = marc_target

    def close(self) -> None:
        self.file_handle.close()

    def __iter__(self):
        return self

    def __next__(self):
        if self._current_exception and isinstance(self._current_exception, FatalReaderError):
            raise StopIteration

        self._current_chunk = None
        self._current_exception = None

        self._current_chunk = first5 = self.file_handle.read(5)
        if not first5:
            raise StopIteration

        if len(first5) < 5:
            self._current_exception = TruncatedRecord()
            return None

        try:
            length = int(first5)
        except ValueError:
            self._current_exception = RecordLengthInvalid()
            return None

        chunk = self.file_handle.read(length - 5)
        chunk = first5 + chunk
        self._current_chunk = chunk

        if len(self._current_chunk) < length:
            self._current_exception = TruncatedRecord()
            return None

        if self._current_chunk[-1] != ord(END_OF_RECORD):
            self._current_exception = EndOfRecordNotFound()
            return None

        try:
            return Record(
                chunk,
                to_unicode=self.to_unicode,
                force_utf8=self.force_utf8,
                hide_utf8_warnings=self.hide_utf8_warnings,
                utf8_handling=self.utf8_handling,
                file_encoding=self.file_encoding,
            )
        except Exception as ex:
            self._current_exception = ex


def map_records(f: Callable, *files: BytesIO | BufferedReader) -> None:
    for file in files:
        list(map(f, MARCReader(file)))


class JSONReader(Reader):
    """JSON Reader."""

    file_handle: IOBase

    def __init__(
        self,
        marc_target: bytes | str,
        encoding: str = "utf-8",
        stream: bool = False,
    ) -> None:
        self.encoding = encoding
        if isinstance(marc_target, IOBase):
            self.file_handle = marc_target
        else:
            if isinstance(marc_target, str) and os.path.exists(marc_target):
                self.file_handle = open(marc_target, encoding=encoding)
            else:
                self.file_handle = StringIO(
                    marc_target if isinstance(marc_target, str) else marc_target.decode(encoding)
                )
        if stream:
            sys.stderr.write("Streaming not yet implemented, your data will be loaded into memory\n")
        self.records = json_loads(self.file_handle.read())

    def __iter__(self) -> Iterator[Record]:
        if hasattr(self.records, "__iter__") and not isinstance(self.records, dict):
            self.iter = iter(self.records)
        else:
            self.iter = iter([self.records])
        return self

    def __next__(self) -> Record:
        jobj = next(self.iter)
        rec = Record()
        rec.leader = Leader(jobj["leader"])
        fields_out = rec.fields
        for field_dict in jobj["fields"]:
            for k, v in field_dict.items():
                # Use __new__ to skip the Field constructor overhead; set slots directly.
                fld = Field.__new__(Field)
                try:
                    fld.tag = f"{int(k):03}"
                except ValueError:
                    fld.tag = k
                object.__setattr__(fld, "_Field__pos", 0)  # mangled __pos slot
                if isinstance(v, dict):
                    fld.control_field = False
                    fld.data = None
                    fld._indicators = Indicators(v["ind1"], v["ind2"])
                    fld.subfields = [Subfield(code=c, value=val) for sub in v["subfields"] for c, val in sub.items()]
                else:
                    fld.control_field = True
                    fld.data = v
                    fld._indicators = None
                    fld.subfields = []
                fields_out.append(fld)
                break  # each field_dict has exactly one key
        return rec


class MARCMakerReader(Reader):
    r"""MARCMaker Reader."""

    def __init__(self, target: bytes | str, encoding: str = "utf-8") -> None:
        file_handle: IOBase
        if isinstance(target, IOBase):
            file_handle = target
        else:
            if isinstance(target, str) and os.path.exists(target):
                file_handle = open(target, encoding=encoding)
            else:
                file_handle = StringIO(target if isinstance(target, str) else target.decode(encoding))
        file_content = file_handle.read()
        file_handle.close()
        self.records = list(file_content.split("\n\n"))
        self.iter = iter(self.records)

    def _parse_line(self, line: str) -> Leader | Field:
        if line[0] != "=":
            raise ValueError('Line should start with a "=".')
        if line[4:6] != "  ":
            raise ValueError("Tag should be separated from the rest of the field by two spaces.")
        tag = line[1:4]
        data = line[6:]
        if tag == "LDR":
            return Leader(data)
        elif tag < "010":
            return Field(tag, data=data)
        indicators = Indicators(data[0], data[1])
        subfields: list[Subfield] = [Subfield(subfield[:1], subfield[1:]) for subfield in data[3:].split("$")]
        return Field(tag, indicators=indicators, subfields=subfields)

    def __iter__(self):
        return self

    def __next__(self) -> Iterator:
        record_txt = next(self.iter)
        record = Record()
        for line in record_txt.splitlines():
            try:
                field = self._parse_line(line)
            except Exception as exc:
                raise PymarcException(f'Unable to parse line "{line}"') from exc
            if isinstance(field, Leader):
                record.leader = field
            else:
                record.add_field(field)
        return record
