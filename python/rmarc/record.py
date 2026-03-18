"""Rmarc Record (pymarc compatible)."""

__all__ = [
    "Record",
    "map_marc8_record",
    "normalize_subfield_code",
]

import json
import logging

from rmarc._compat import HAS_ORJSON, json_dumps
import re
import unicodedata
import warnings
from re import Pattern

from rmarc.constants import DIRECTORY_ENTRY_LEN, END_OF_FIELD, END_OF_RECORD, LEADER_LEN, SUBFIELD_INDICATOR
from rmarc.exceptions import (
    BadSubfieldCodeWarning,
    BaseAddressInvalid,
    BaseAddressNotFound,
    FieldNotFound,
    MissingLinkedFields,
    NoFieldsFound,
    RecordDirectoryInvalid,
    RecordLeaderInvalid,
    TruncatedRecord,
)
from rmarc.field import Field, Indicators, RawField, Subfield, map_marc8_field
from rmarc.leader import Leader
from rmarc.marc8 import marc8_to_unicode

try:
    from rmarc._rmarc import decode_marc_raw as _decode_marc_raw
    from rmarc._rmarc import encode_marc_raw as _encode_marc_raw

    _HAS_RUST_CODEC = True
except ImportError:
    _HAS_RUST_CODEC = False

isbn_regex: Pattern = re.compile(r"([0-9\-xX]+)")
logger = logging.getLogger("pymarc")


class Record:
    """A class for representing a MARC record."""

    __slots__ = ("leader", "fields", "pos", "force_utf8", "to_unicode", "__pos")

    def __init__(
        self,
        data: str | bytes = "",
        fields: list[Field] | None = None,
        to_unicode: bool = True,
        force_utf8: bool = False,
        hide_utf8_warnings: bool = False,
        utf8_handling: str = "strict",
        leader: str = " " * LEADER_LEN,
        file_encoding: str = "iso8859-1",
    ) -> None:
        self.leader: Leader = Leader(leader[0:10] + "22" + leader[12:20] + "4500")
        self.fields: list[Field | RawField] = []
        self.pos: int = 0
        self.__pos: int = 0
        self.force_utf8: bool = force_utf8
        self.to_unicode: bool = to_unicode
        if fields:
            self.fields = fields
        elif len(data) > 0:
            self.decode_marc(
                data,
                to_unicode=to_unicode,
                force_utf8=force_utf8,
                hide_utf8_warnings=hide_utf8_warnings,
                utf8_handling=utf8_handling,
                encoding=file_encoding,
            )
        elif force_utf8:
            self.leader = Leader(self.leader[0:9] + "a" + self.leader[10:])

    def __str__(self) -> str:
        text_list: list[str] = [f"=LDR  {self.leader}"]
        text_list.extend([str(field) for field in self.fields])
        text: str = "\n".join(text_list) + "\n"
        return text

    def get(self, tag: str, default: Field | None = None) -> Field | None:
        try:
            return self[tag]
        except KeyError:
            return default

    def __getitem__(self, tag: str) -> Field:
        if tag not in self:
            raise KeyError

        fields: list[Field] = self.get_fields(tag)
        if not fields:
            raise KeyError

        return fields[0]

    def __contains__(self, tag: str) -> bool:
        for f in self.fields:
            if f.tag == tag:
                return True
        return False

    def __iter__(self):
        self.__pos = 0
        return self

    def __next__(self) -> Field:
        if self.__pos >= len(self.fields):
            raise StopIteration
        self.__pos += 1
        return self.fields[self.__pos - 1]

    def add_field(self, *fields):
        self.fields.extend(fields)

    def add_grouped_field(self, *fields) -> None:
        for f in fields:
            if not self.fields or not f.tag.isdigit():
                self.fields.append(f)
                continue
            self._sort_fields(f, "grouped")

    def add_ordered_field(self, *fields) -> None:
        for f in fields:
            if not self.fields or not f.tag.isdigit():
                self.fields.append(f)
                continue
            self._sort_fields(f, "ordered")

    def _sort_fields(self, field: Field, mode: str) -> None:
        tag = int(field.tag[0]) if mode == "grouped" else int(field.tag)

        for i, selff in enumerate(self.fields, 1):
            if not selff.tag.isdigit():
                self.fields.insert(i - 1, field)
                break

            last_tag = int(selff.tag[0]) if mode == "grouped" else int(selff.tag)

            if last_tag > tag:
                self.fields.insert(i - 1, field)
                break

            if len(self.fields) == i:
                self.fields.append(field)
                break

    def remove_field(self, *fields) -> None:
        for f in fields:
            try:
                self.fields.remove(f)
            except ValueError:
                raise FieldNotFound from None

    def remove_fields(self, *tags) -> None:
        self.fields[:] = (field for field in self.fields if field.tag not in tags)

    def get_fields(self, *args) -> list[Field]:
        if not args:
            return self.fields

        return [f for f in self.fields if f.tag in args]

    def get_linked_fields(self, field: Field) -> list[Field]:
        num = field.linkage_occurrence_num()
        fields = self.get_fields("880")
        linked_fields = list(filter(lambda f: f.linkage_occurrence_num() == num, fields))
        if num is not None and not linked_fields:
            raise MissingLinkedFields(field)
        return linked_fields

    def decode_marc(
        self,
        marc,
        to_unicode: bool = True,
        force_utf8: bool = False,
        hide_utf8_warnings: bool = False,
        utf8_handling: str = "strict",
        encoding: str = "iso8859-1",
    ) -> None:
        if _HAS_RUST_CODEC:
            self._decode_marc_rust(marc, to_unicode, force_utf8, hide_utf8_warnings, utf8_handling, encoding)
        else:
            self._decode_marc_python(marc, to_unicode, force_utf8, hide_utf8_warnings, utf8_handling, encoding)

    def _decode_marc_rust(
        self,
        marc,
        to_unicode: bool,
        force_utf8: bool,
        hide_utf8_warnings: bool,
        utf8_handling: str,
        encoding: str,
    ) -> None:
        """Fast path: Rust does byte-level parsing + encoding, Python wraps into objects."""
        # Validate leader first (needed for encoding detection)
        if len(marc) < LEADER_LEN:
            raise RecordLeaderInvalid

        leader_str = marc[0:LEADER_LEN].decode("ascii")
        if leader_str[9] == "a" or self.force_utf8:
            encoding = "utf-8"

        self.leader = Leader(leader_str)

        # Validate before calling Rust (to raise the right exception types)
        base_address = int(marc[12:17])
        if base_address <= 0:
            raise BaseAddressNotFound
        if base_address >= len(marc):
            raise BaseAddressInvalid
        if len(marc) < int(self.leader[:5]):
            raise TruncatedRecord

        # Rust does parsing + encoding conversion in one shot
        try:
            _leader, fields_raw = _decode_marc_raw(
                marc,
                to_unicode=to_unicode,
                force_utf8=force_utf8,
                encoding=encoding,
                utf8_handling=utf8_handling,
                quiet=hide_utf8_warnings,
            )
        except ValueError as e:
            msg = str(e)
            if "DirectoryInvalid" in msg:
                raise RecordDirectoryInvalid from None
            if "NoFieldsFound" in msg:
                raise NoFieldsFound from None
            if "InvalidUTF8" in msg:
                raise UnicodeDecodeError("utf-8", marc, 0, 1, msg) from None
            if "not valid ASCII" in msg:
                raise UnicodeDecodeError("ascii", b"", 0, 1, msg) from None
            raise

        # Convert Rust output into Python Field/RawField objects
        # Rust returns decoded strings for utf-8 and marc8/iso8859-1 cases,
        # but raw bytes for unknown encodings and to_unicode=False.
        # We need to decode raw bytes when to_unicode=True but encoding is unknown to Rust.
        needs_python_decode = to_unicode and encoding not in ("utf-8", "iso8859-1")
        FieldClass = Field if to_unicode else RawField
        fields = self.fields

        if not fields_raw:
            raise NoFieldsFound

        for tag, field_info in fields_raw:
            field_type = field_info[0]

            if field_type == "control":
                data_val = field_info[1]
                if needs_python_decode and isinstance(data_val, bytes):
                    data_val = data_val.decode(encoding)
                field = FieldClass.__new__(FieldClass)
                field.tag = tag
                field.data = data_val
                field.control_field = True
                field._indicators = None
                field.subfields = []
            else:
                raw_subfields = field_info[3]

                subfields = []
                for code_or_bytes, value in raw_subfields:
                    if isinstance(code_or_bytes, bytes):
                        # Non-ASCII subfield code — rare path
                        warnings.warn(
                            BadSubfieldCodeWarning(code_or_bytes + value),
                            stacklevel=2,
                        )
                        code, skip_bytes = normalize_subfield_code(code_or_bytes + value)
                        value = (code_or_bytes + value)[skip_bytes:]
                        if to_unicode:
                            if self.leader[9] == "a" or force_utf8:
                                value = value.decode("utf-8", utf8_handling)
                            elif encoding == "iso8859-1":
                                value = marc8_to_unicode(value, hide_utf8_warnings)
                            else:
                                value = value.decode(encoding)
                    else:
                        code = code_or_bytes
                        # Rust decoded the value for utf-8/marc8; decode here for other encodings
                        if needs_python_decode and isinstance(value, bytes):
                            value = value.decode(encoding)

                    subfields.append(Subfield(code=code, value=value))

                field = FieldClass.__new__(FieldClass)
                field.tag = tag
                field.data = None
                field.control_field = False
                field._indicators = Indicators(field_info[1], field_info[2])
                field.subfields = subfields

            fields.append(field)

    def _decode_marc_python(
        self,
        marc,
        to_unicode: bool,
        force_utf8: bool,
        hide_utf8_warnings: bool,
        utf8_handling: str,
        encoding: str,
    ) -> None:
        """Pure Python fallback for decode_marc."""
        # extract record leader
        leader = marc[0:LEADER_LEN].decode("ascii")

        if len(leader) != LEADER_LEN:
            raise RecordLeaderInvalid

        if leader[9] == "a" or self.force_utf8:
            encoding = "utf-8"

        self.leader = Leader(leader)

        # extract the byte offset where the record data starts
        base_address = int(marc[12:17])
        if base_address <= 0:
            raise BaseAddressNotFound
        if base_address >= len(marc):
            raise BaseAddressInvalid
        if len(marc) < int(self.leader[:5]):
            raise TruncatedRecord

        # extract directory
        directory = marc[LEADER_LEN : base_address - 1].decode("ascii")

        # determine the number of fields in record
        if len(directory) % DIRECTORY_ENTRY_LEN != 0:
            raise RecordDirectoryInvalid
        field_total: int = len(directory) // DIRECTORY_ENTRY_LEN

        # add fields to our record using directory offsets
        field_count: int = 0
        while field_count < field_total:
            entry_start = field_count * DIRECTORY_ENTRY_LEN
            entry_end = entry_start + DIRECTORY_ENTRY_LEN
            entry = directory[entry_start:entry_end]
            entry_tag = entry[0:3]
            entry_length = int(entry[3:7])
            entry_offset = int(entry[7:12])
            entry_data = marc[base_address + entry_offset : base_address + entry_offset + entry_length - 1]
            # assume controlfields are numeric; replicates ruby-marc behavior
            if entry_tag < "010" and entry_tag.isdigit():
                if to_unicode:
                    field = Field(tag=entry_tag, data=entry_data.decode(encoding))
                else:
                    field = RawField(tag=entry_tag, data=entry_data)
            else:
                subfields = []
                subs = entry_data.split(SUBFIELD_INDICATOR.encode("ascii"))

                subs[0] = subs[0].decode("ascii")
                if not subs[0]:
                    logger.warning("missing indicators: %s", entry_data)
                    first_indicator = second_indicator = " "
                elif len(subs[0]) == 1:
                    logger.warning("only 1 indicator found: %s", entry_data)
                    first_indicator = subs[0][0]
                    second_indicator = " "
                elif len(subs[0]) > 2:
                    logger.warning("more than 2 indicators found: %s", entry_data)
                    first_indicator = subs[0][0]
                    second_indicator = subs[0][1]
                else:
                    first_indicator = subs[0][0]
                    second_indicator = subs[0][1]

                for subfield in subs[1:]:
                    skip_bytes = 1
                    if not subfield:
                        continue
                    try:
                        code = subfield[0:1].decode("ascii")
                    except UnicodeDecodeError:
                        warnings.warn(BadSubfieldCodeWarning(subfield), stacklevel=2)
                        code, skip_bytes = normalize_subfield_code(subfield)
                    data = subfield[skip_bytes:]

                    if to_unicode:
                        if self.leader[9] == "a" or force_utf8:
                            data = data.decode("utf-8", utf8_handling)
                        elif encoding == "iso8859-1":
                            data = marc8_to_unicode(data, hide_utf8_warnings)
                        else:
                            data = data.decode(encoding)

                    coded = Subfield(code=code, value=data)
                    subfields.append(coded)

                if to_unicode:
                    field = Field(
                        tag=entry_tag,
                        indicators=Indicators(first_indicator, second_indicator),
                        subfields=subfields,
                    )
                else:
                    field = RawField(
                        tag=entry_tag,
                        indicators=Indicators(first_indicator, second_indicator),
                        subfields=subfields,
                    )
            self.add_field(field)
            field_count += 1

        if field_count == 0:
            raise NoFieldsFound

    def as_marc(self) -> bytes:
        if self.to_unicode:
            if isinstance(self.leader, Leader):
                self.leader.coding_scheme = "a"
            else:
                self.leader = self.leader[0:9] + "a" + self.leader[10:]

        encoding = "utf-8" if self.leader[9] == "a" or self.force_utf8 else "iso8859-1"

        # Encode all fields first (needed by both paths)
        field_pairs = []
        for field in self.fields:
            if isinstance(field, RawField):
                field_data = field.as_marc()
            else:
                field_data = field.as_marc(encoding=encoding)

            if field.tag.isdigit():
                tag_str = f"{int(field.tag):03d}"
            else:
                tag_str = f"{field.tag:>03}"
            field_pairs.append((tag_str, field_data))

        if _HAS_RUST_CODEC:
            return _encode_marc_raw(str(self.leader), field_pairs)

        # Python fallback
        fields = b""
        directory = b""
        offset = 0

        for tag_str, field_data in field_pairs:
            fields += field_data
            directory += tag_str.encode(encoding)
            directory += f"{len(field_data):04d}{offset:05d}".encode(encoding)
            offset += len(field_data)

        directory += END_OF_FIELD.encode(encoding)
        fields += END_OF_RECORD.encode(encoding)

        base_address = LEADER_LEN + len(directory)
        record_length = base_address + len(fields)

        strleader = f"{record_length:0>5}{self.leader[5:12]}{base_address:0>5}{self.leader[17:]}"
        leader = strleader.encode(encoding)

        return leader + directory + fields

    # alias for backwards compatibility
    as_marc21 = as_marc

    def as_dict(self) -> dict[str, object]:
        fields_list: list = []
        for field in self.fields:  # iterate list directly, avoids custom __iter__ overhead
            if field.control_field:
                fields_list.append({field.tag: field.data})
            else:
                fields_list.append(
                    {
                        field.tag: {
                            "ind1": field.indicator1,
                            "ind2": field.indicator2,
                            "subfields": [{s.code: s.value} for s in field.subfields],
                        }
                    }
                )
        return {"leader": str(self.leader), "fields": fields_list}

    def as_json(self, **kwargs) -> str:
        if HAS_ORJSON and not kwargs:
            return json_dumps(self.as_dict())
        return json.dumps(self.as_dict(), **kwargs)

    @property
    def title(self) -> str | None:
        title_field: Field | None = self.get("245")
        if not title_field:
            return None

        title: str | None = title_field.get("a")
        if title:
            subtitle = title_field.get("b")
            if subtitle:
                title += f" {subtitle}"
        return title

    @property
    def issn_title(self) -> str | None:
        title_field: Field | None = self.get("222")
        if not title_field:
            return None

        title: str | None = title_field.get("a")
        if title:
            subtitle = title_field.get("b")
            if subtitle:
                title += f" {subtitle}"
        return title

    @property
    def isbn(self) -> str | None:
        isbn_field: Field | None = self.get("020")
        if not isbn_field:
            return None

        isbn_number: str | None = isbn_field.get("a")
        if not isbn_number:
            return None

        match = isbn_regex.search(isbn_number)
        if match:
            return match.group(1).replace("-", "")

        return None

    @property
    def issn(self) -> str | None:
        field = self.get("022")
        return field.get("a") if (field and "a" in field) else None

    @property
    def issnl(self) -> str | None:
        field = self.get("022")
        return field["l"] if (field and "l" in field) else None

    @property
    def sudoc(self) -> str | None:
        field = self.get("086")
        return field.format_field() if field else None

    @property
    def author(self) -> str | None:
        field = self.get("100") or self.get("110") or self.get("111")
        return field.format_field() if field else None

    @property
    def uniformtitle(self) -> str | None:
        field = self.get("130") or self.get("240")
        return field.format_field() if field else None

    @property
    def series(self) -> list[Field]:
        return self.get_fields("440", "490", "800", "810", "811", "830")

    @property
    def subjects(self) -> list[Field]:
        return self.get_fields(
            "600",
            "610",
            "611",
            "630",
            "648",
            "650",
            "651",
            "653",
            "654",
            "655",
            "656",
            "657",
            "658",
            "662",
            "690",
            "691",
            "696",
            "697",
            "698",
            "699",
        )

    @property
    def addedentries(self) -> list[Field]:
        return self.get_fields(
            "700",
            "710",
            "711",
            "720",
            "730",
            "740",
            "752",
            "753",
            "754",
            "790",
            "791",
            "792",
            "793",
            "796",
            "797",
            "798",
            "799",
        )

    @property
    def location(self) -> list[Field]:
        return self.get_fields("852")

    @property
    def notes(self) -> list[Field]:
        return self.get_fields(
            "500",
            "501",
            "502",
            "504",
            "505",
            "506",
            "507",
            "508",
            "510",
            "511",
            "513",
            "514",
            "515",
            "516",
            "518",
            "520",
            "521",
            "522",
            "524",
            "525",
            "526",
            "530",
            "533",
            "534",
            "535",
            "536",
            "538",
            "540",
            "541",
            "544",
            "545",
            "546",
            "547",
            "550",
            "552",
            "555",
            "556",
            "561",
            "562",
            "563",
            "565",
            "567",
            "580",
            "581",
            "583",
            "584",
            "585",
            "586",
            "590",
            "591",
            "592",
            "593",
            "594",
            "595",
            "596",
            "597",
            "598",
            "599",
        )

    @property
    def physicaldescription(self) -> list[Field]:
        return self.get_fields("300")

    @property
    def publisher(self) -> str | None:
        for f in self.get_fields("260", "264"):
            if f.tag == "260":
                return f.get("b")
            if f.tag == "264" and f.indicator2 == "1":
                return f.get("b")

        return None

    @property
    def pubyear(self) -> str | None:
        for f in self.get_fields("260", "264"):
            if f.tag == "260":
                return f.get("c")
            if f.tag == "264" and f.indicator2 == "1":
                return f.get("c")
        return None


def map_marc8_record(record: Record) -> Record:
    record.fields = [map_marc8_field(field) for field in record.fields]
    leader: list[str] = list(record.leader.leader)
    leader[9] = "a"
    record.leader = Leader("".join(leader))
    return record


def normalize_subfield_code(subfield: bytes) -> tuple[str, int]:
    skip_bytes: int = 1
    try:
        text_subfield = subfield.decode("utf-8")
        skip_bytes = len(text_subfield[0].encode("utf-8"))
    except UnicodeDecodeError:
        text_subfield = subfield.decode("latin-1")
    decomposed = unicodedata.normalize("NFKD", text_subfield)
    without_diacritics = decomposed.encode("ascii", "ignore").decode("ascii")
    return without_diacritics[0], skip_bytes
