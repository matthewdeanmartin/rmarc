# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

"""Pymarc Record."""

import json
import logging
import re
import typing
import unicodedata
import warnings
from re import Pattern

from pymarc.constants import (
    DIRECTORY_ENTRY_LEN,
    END_OF_FIELD,
    END_OF_RECORD,
    LEADER_LEN,
    SUBFIELD_INDICATOR,
)
from pymarc.exceptions import (
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
from pymarc.field import (
    Field,
    Indicators,
    RawField,
    Subfield,
    map_marc8_field,
)
from pymarc.leader import Leader
from pymarc.marc8 import marc8_to_unicode

isbn_regex: Pattern = re.compile(r"([0-9\-xX]+)")
logger = logging.getLogger("pymarc")


class Record:
    """A class for representing a MARC record.

    Each Record object is made up of multiple Field objects. You'll probably want to look
    at the docs for :class:`Field <pymarc.record.Field>` to see how to fully use a Record
    object.

    Basic usage:

    .. code-block:: python

        field = Field(
            tag = '245',
            indicators = Indicators('0','1'),
            subfields = [
                Subfield(code='a', value='The pragmatic programmer : '),
                Subfield(code='b', value='from journeyman to master /'),
                Subfield(code='c', value='Andrew Hunt, David Thomas.'),
            ])

        record.add_field(field)

    Or creating a record from a chunk of MARC in transmission format:

    .. code-block:: python

        record = Record(data=chunk)

    Or getting a record as serialized MARC21.

    .. code-block:: python

        raw = record.as_marc()

    You'll normally want to use a MARCReader object to iterate through
    MARC records in a file.
    """

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
        """Initialize a Record."""
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
        """Will return a prettified version of the record in MARCMaker format.

        See :func:`Field.__str__() <pymarc.record.Field.__str__>` for more information.
        """
        # join is significantly faster than concatenation
        text_list: list[str] = [f"=LDR  {self.leader}"]
        text_list.extend([str(field) for field in self.fields])
        text: str = "\n".join(text_list) + "\n"
        return text

    def get(self, tag: str, default: Field | None = None) -> Field | None:
        """Implements a dict-like get with a default value.

        If `tag` is not found, then the default value will be returned.
        The default value should be a Field instance.

        .. code-block:: python
            # returns None if 999 not in record.
            record.get('999')
            # returns the default if 999 not in record.
            record.get('999', Field(tag="999", indicators=Indicators(" ", " ")))


        """
        try:
            return self[tag]
        except KeyError:
            return default

    def __getitem__(self, tag: str) -> Field:
        """Allows a shorthand lookup by tag.

        Follows Python behavior and raises KeyError if `tag` is not in the record.

        .. code-block:: python

            record['245']
        """
        if tag not in self:
            raise KeyError

        fields: list[Field] = self.get_fields(tag)
        if not fields:
            raise KeyError

        return fields[0]

    def __contains__(self, tag: str) -> bool:
        """Allows a shorthand test of tag membership.

        .. code-block:: python

            '245' in record
        """
        # This is the fastest implementation.
        for f in self.fields:  # noqa: SIM110
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
        """Add pymarc.Field objects to a Record object.

        Optionally you can pass in multiple fields.
        """
        self.fields.extend(fields)

    def add_grouped_field(self, *fields) -> None:
        """Add pymarc.Field objects to a Record object and sort them "grouped".

        Which means, attempting to maintain a loose numeric order per the MARC standard
        for "Organization of the record" (http://www.loc.gov/marc/96principl.html).
        Optionally you can pass in multiple fields.
        """
        for f in fields:
            if not self.fields or not f.tag.isdigit():
                self.fields.append(f)
                continue
            self._sort_fields(f, "grouped")

    def add_ordered_field(self, *fields) -> None:
        """Add pymarc.Field objects to a Record object and sort them "ordered".

        Which means, attempting to maintain a strict numeric order.
        Optionally you can pass in multiple fields.
        """
        for f in fields:
            if not self.fields or not f.tag.isdigit():
                self.fields.append(f)
                continue
            self._sort_fields(f, "ordered")

    def _sort_fields(self, field: Field, mode: str) -> None:
        """Sort fields by `mode`."""
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
        """Remove one or more pymarc.Field objects from a Record object."""
        for f in fields:
            try:
                self.fields.remove(f)
            except ValueError:
                raise FieldNotFound from None

    def remove_fields(self, *tags) -> None:
        """Remove all the fields with the tags passed to the function.

        .. code-block:: python

            # remove all the fields marked with tags '200' or '899'.
            self.remove_fields('200', '899')
        """
        self.fields[:] = (field for field in self.fields if field.tag not in tags)

    @typing.overload
    def get_fields(self, *args: str) -> list[Field]: ...

    @typing.overload
    def get_fields(self, *args: list[str]) -> list[Field]: ...

    def get_fields(self, *args: str | list[str]) -> list[Field]:
        """Return a list of all the fields in a record tags matching `args`.

        .. code-block:: python

            title = record.get_fields('245')

        If no fields with the specified tag are found then an empty list is returned.
        If you are interested in more than one tag you can pass it as multiple arguments.

        .. code-block:: python

            subjects = record.get_fields('600', '610', '650')

        If no tag is passed in to get_fields() a list of all the fields will be
        returned.
        """
        if not args:
            return self.fields

        return [f for f in self.fields if f.tag in args]

    def get_linked_fields(self, field: Field) -> list[Field]:
        """Given a field that is not an 880, retrieve a list of any linked 880 fields."""
        num = field.linkage_occurrence_num()
        fields = self.get_fields("880")
        linked_fields = list(
            filter(lambda f: f.linkage_occurrence_num() == num, fields)
        )
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
        """Populate the object based on the `marc`` record in transmission format.

        The Record constructor actually uses decode_marc() behind the scenes when you
        pass in a chunk of MARC data to it.
        """
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

        # extract directory, base_address-1 is used since the
        # director ends with an END_OF_FIELD byte
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
            entry_data = marc[
                base_address + entry_offset : base_address
                + entry_offset
                + entry_length
                - 1
            ]
            # assume controlfields are numeric; replicates ruby-marc behavior
            if entry_tag < "010" and entry_tag.isdigit():
                if to_unicode:
                    field = Field(tag=entry_tag, data=entry_data.decode(encoding))
                else:
                    field = RawField(tag=entry_tag, data=entry_data)
            else:
                subfields = []
                subs = entry_data.split(SUBFIELD_INDICATOR.encode("ascii"))

                # The MARC spec requires there to be two indicators in a
                # field. However experience in the wild has shown that
                # indicators are sometimes missing, and sometimes there
                # are too many. Rather than throwing an exception because
                # we can't find what we want and rejecting the field, or
                # barfing on the whole record we'll try to use what we can
                # find. This means missing indicators will be recorded as
                # blank spaces, and any more than 2 are dropped on the floor.

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
        """Returns the record serialized as MARC21."""
        fields = b""
        directory = b""
        offset = 0

        if self.to_unicode:
            if isinstance(self.leader, Leader):
                self.leader.coding_scheme = "a"
            else:
                self.leader = self.leader[0:9] + "a" + self.leader[10:]

        # build the directory
        # each element of the directory includes the tag, the byte length of
        # the field and the offset from the base address where the field data
        # can be found
        encoding = "utf-8" if self.leader[9] == "a" or self.force_utf8 else "iso8859-1"

        for field in self.fields:
            if isinstance(field, RawField):
                field_data = field.as_marc()
            else:
                field_data = field.as_marc(encoding=encoding)
            fields += field_data
            if field.tag.isdigit():
                directory += f"{int(field.tag):03d}".encode(encoding)
            else:
                directory += f"{field.tag:>03}".encode(encoding)
            directory += f"{len(field_data):04d}{offset:05d}".encode(encoding)

            offset += len(field_data)

        # directory ends with an end of field
        directory += END_OF_FIELD.encode(encoding)

        # field data ends with an end of record
        fields += END_OF_RECORD.encode(encoding)

        # the base address where the directory ends and the field data begins
        base_address = LEADER_LEN + len(directory)

        # figure out the length of the record
        record_length = base_address + len(fields)

        # update the leader with the current record length and base address
        # the lengths are fixed width and zero padded
        strleader = f"{record_length:0>5}{self.leader[5:12]}{base_address:0>5}{self.leader[17:]}"
        leader = strleader.encode(encoding)

        return leader + directory + fields

    # alias for backwards compatibility
    as_marc21 = as_marc

    def as_dict(self) -> dict[str, object]:
        """Turn a MARC record into a dictionary, which is used for ``as_json``."""
        record: dict[str, object] = {"leader": str(self.leader), "fields": []}

        for field in self:
            if field.control_field:
                record["fields"].append({field.tag: field.data})  # type: ignore
            else:
                record["fields"].append(  # type: ignore
                    {
                        field.tag: {
                            "ind1": field.indicator1,
                            "ind2": field.indicator2,
                            "subfields": [{s.code: s.value} for s in field.subfields],
                        }
                    }
                )
        return record  # as dict

    def as_json(self, **kwargs) -> str:
        """Serialize a record as JSON.

        See:
        https://web.archive.org/web/20151112001548/http://dilettantes.code4lib.org/blog/2010/09/a-proposal-to-serialize-marc-in-json
        """
        return json.dumps(self.as_dict(), **kwargs)

    @property
    def title(self) -> str | None:
        """Returns the title of the record (245 $a and $b)."""
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
        """Returns the key title of the record (222 $a and $b)."""
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
        """Returns the first ISBN in the record or None if one is not present.

        The returned ISBN will be all numeric, except for an
        x/X which may occur in the checksum position.  Dashes and
        extraneous information will be automatically removed. If you need
        this information you'll want to look directly at the 020 field,
        e.g. record['020']['a']. Values that do not match the regex will not
        be returned.
        """
        isbn_field: Field | None = self.get("020")
        if not isbn_field:
            return None

        isbn_number: str | None = isbn_field.get("a")
        if not isbn_number:
            return None

        match = isbn_regex.search(isbn_number)  # type: ignore
        if match:
            return match.group(1).replace("-", "")

        return None

    @property
    def issn(self) -> str | None:
        """Returns the ISSN number [022]['a'] in the record or None."""
        field = self.get("022")
        return field.get("a") if (field and "a" in field) else None

    @property
    def issnl(self) -> str | None:
        """Returns the ISSN-L number [022]['l'] of the record or None."""
        field = self.get("022")
        return field["l"] if (field and "l" in field) else None

    @property
    def sudoc(self) -> str | None:
        """Returns a Superintendent of Documents (SuDoc) classification number.

        Note: More information can be found at the following URL:
        https://www.fdlp.gov/classification-guidelines/introduction-to-the-classification-guidelines
        """
        field = self.get("086")
        return field.format_field() if field else None

    @property
    def author(self) -> str | None:
        """Returns the author from field 100, 110 or 111."""
        field = self.get("100") or self.get("110") or self.get("111")
        return field.format_field() if field else None

    @property
    def uniformtitle(self) -> str | None:
        """Returns the uniform title from field 130 or 240."""
        field = self.get("130") or self.get("240")
        return field.format_field() if field else None

    @property
    def series(self) -> list[Field]:
        """Returns series fields.

        Note: 490 supersedes the 440 series statement which was both
        series statement and added entry. 8XX fields are added entries.
        """
        return self.get_fields("440", "490", "800", "810", "811", "830")

    @property
    def subjects(self) -> list[Field]:
        """Returns subjects fields.

        Note: Fields 690-699 are considered "local" added entry fields but
        occur with some frequency in OCLC and RLIN records.
        """
        # fmt: off
        return self.get_fields(
            "600", "610", "611", "630", "648", "650", "651", "653", "654", "655",
            "656", "657", "658", "662", "690", "691", "696", "697", "698", "699",
        )
        # fmt: on

    @property
    def addedentries(self) -> list[Field]:
        """Returns Added entries fields.

        Note: Fields 790-799 are considered "local" added entry fields but
        occur with some frequency in OCLC and RLIN records.
        """
        # fmt: off
        return self.get_fields(
            "700", "710", "711", "720", "730", "740", "752", "753", "754", "790",
            "791", "792", "793", "796", "797", "798", "799",
        )
        # fmt: on

    @property
    def location(self) -> list[Field]:
        """Returns location field (852)."""
        return self.get_fields("852")

    @property
    def notes(self) -> list[Field]:
        """Return notes fields (all 5xx fields)."""
        # fmt: off
        return self.get_fields(
            "500", "501", "502", "504", "505", "506", "507", "508", "510", "511",
            "513", "514", "515", "516", "518", "520", "521", "522", "524", "525",
            "526", "530", "533", "534", "535", "536", "538", "540", "541", "544",
            "545", "546", "547", "550", "552", "555", "556", "561", "562", "563",
            "565", "567", "580", "581", "583", "584", "585", "586", "590", "591",
            "592", "593", "594", "595", "596", "597", "598", "599",
        )
        # fmt: on

    @property
    def physicaldescription(self) -> list[Field]:
        """Return physical description fields (300)."""
        return self.get_fields("300")

    @property
    def publisher(self) -> str | None:
        """Return publisher from 260 or 264.

        Note: 264 field with second indicator '1' indicates publisher.
        """
        for f in self.get_fields("260", "264"):
            if f.tag == "260":
                return f.get("b")
            if f.tag == "264" and f.indicator2 == "1":
                return f.get("b")

        return None

    @property
    def pubyear(self) -> str | None:
        """Returns publication year from 260 or 264."""
        for f in self.get_fields("260", "264"):
            if f.tag == "260":
                return f.get("c")  # type: ignore
            if f.tag == "264" and f.indicator2 == "1":
                return f.get("c")  # type: ignore
        return None


def map_marc8_record(record: Record) -> Record:
    """Map MARC-8 record."""
    record.fields = [map_marc8_field(field) for field in record.fields]
    leader: list[str] = list(record.leader.leader)
    leader[9] = "a"  # see http://www.loc.gov/marc/specifications/speccharucs.html
    record.leader = Leader("".join(leader))
    return record


def normalize_subfield_code(subfield: bytes) -> tuple[str, int]:
    """Normalize subfield code."""
    skip_bytes: int = 1
    try:
        text_subfield = subfield.decode("utf-8")
        skip_bytes = len(text_subfield[0].encode("utf-8"))
    except UnicodeDecodeError:
        text_subfield = subfield.decode("latin-1")
    decomposed = unicodedata.normalize("NFKD", text_subfield)
    without_diacritics = decomposed.encode("ascii", "ignore").decode("ascii")
    return without_diacritics[0], skip_bytes
