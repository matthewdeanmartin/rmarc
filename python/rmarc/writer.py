"""Rmarc Writer (pymarc compatible)."""

__all__ = [
    "Writer",
    "JSONWriter",
    "MARCWriter",
    "TextWriter",
    "XMLWriter",
]

import json
import xml.etree.ElementTree as ET
from typing import IO

from rmarc._compat import HAS_ORJSON, json_dumps
from rmarc.exceptions import WriteNeedsRecord
from rmarc.marcxml import record_to_xml_node
from rmarc.record import Record


class Writer:
    """Base Writer object."""

    def __init__(self, file_handle: IO) -> None:
        self.file_handle: IO | None = file_handle

    def write(self, record: Record) -> None:
        if not isinstance(record, Record):
            raise WriteNeedsRecord

    def close(self, close_fh: bool = True) -> None:
        if close_fh and self.file_handle:
            self.file_handle.close()
        self.file_handle = None


class JSONWriter(Writer):
    """A class for writing records as an array of MARC-in-JSON objects."""

    def __init__(self, file_handle: IO) -> None:
        super().__init__(file_handle)
        self.write_count = 0
        if self.file_handle:
            self.file_handle.write("[")

    def write(self, record: Record) -> None:
        Writer.write(self, record)
        if self.file_handle:
            if self.write_count > 0:
                self.file_handle.write(",")
            if HAS_ORJSON:
                self.file_handle.write(json_dumps(record.as_dict()))
            else:
                json.dump(record.as_dict(), self.file_handle, separators=(",", ":"))
            self.write_count += 1

    def close(self, close_fh: bool = True) -> None:
        if self.file_handle:
            self.file_handle.write("]")
        Writer.close(self, close_fh)


class MARCWriter(Writer):
    """A class for writing MARC21 records in transmission format."""

    def __init__(self, file_handle: IO) -> None:
        super().__init__(file_handle)

    def write(self, record: Record) -> None:
        Writer.write(self, record)
        if self.file_handle:
            self.file_handle.write(record.as_marc())


class TextWriter(Writer):
    """A class for writing records in prettified text MARCMaker format."""

    def __init__(self, file_handle: IO) -> None:
        super().__init__(file_handle)
        self.write_count = 0

    def write(self, record: Record) -> None:
        Writer.write(self, record)
        if self.file_handle:
            if self.write_count > 0:
                self.file_handle.write("\n")
            self.file_handle.write(str(record))
            self.write_count += 1


class XMLWriter(Writer):
    """A class for writing records as a MARCXML collection."""

    def __init__(self, file_handle: IO) -> None:
        super().__init__(file_handle)
        if self.file_handle:
            self.file_handle.write(b'<?xml version="1.0" encoding="UTF-8"?>')
            self.file_handle.write(b'<collection xmlns="http://www.loc.gov/MARC21/slim">')

    def write(self, record: Record) -> None:
        Writer.write(self, record)
        if self.file_handle:
            node = record_to_xml_node(record)
            self.file_handle.write(ET.tostring(node, encoding="utf-8"))

    def close(self, close_fh: bool = True) -> None:
        if self.file_handle:
            self.file_handle.write(b"</collection>")
        Writer.close(self, close_fh)
